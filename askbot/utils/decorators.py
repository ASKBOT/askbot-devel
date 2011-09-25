import hotshot
import time
import os
import datetime
import functools
import inspect
import logging
from django.conf import settings
from django.core import exceptions as django_exceptions
from django.core.urlresolvers import reverse
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.http import HttpResponseRedirect
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.utils.encoding import smart_str
from askbot import exceptions as askbot_exceptions
from askbot.conf import settings as askbot_settings
from askbot.utils import url_utils
from askbot import get_version

def auto_now_timestamp(func):
    """decorator that will automatically set
    argument named timestamp to the "now" value if timestamp == None

    if there is no timestamp argument, then exception is raised
    """
    @functools.wraps(func)
    def decorated_func(*arg, **kwarg):
        timestamp = kwarg.get('timestamp', None)
        if timestamp is None:
            kwarg['timestamp'] = datetime.datetime.now()
        return func(*arg, **kwarg)
    return decorated_func


def ajax_login_required(view_func):
    @functools.wraps(view_func)
    def wrap(request, *args, **kwargs):
        if request.user.is_authenticated():
            return view_func(request, *args, **kwargs)
        else:
            json = simplejson.dumps({'login_required':True})
            return HttpResponseForbidden(json, mimetype='application/json')
    return wrap


def anonymous_forbidden(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_anonymous():
            raise askbot_exceptions.LoginRequired()
        return view_func(request, *args, **kwargs)
    return wrapper


def get_only(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.method != 'GET':
            raise django_exceptions.PermissionDenied(
                'request method %s is not supported for this function' % \
                request.method
            )
        return view_func(request, *args, **kwargs)
    return wrapper


def post_only(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.method != 'POST':
            raise django_exceptions.PermissionDenied(
                'request method %s is not supported for this function' % \
                request.method
            )
        return view_func(request, *args, **kwargs)
    return wrapper

def ajax_only(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.is_ajax():
            raise Http404
        try:
            data = view_func(request, *args, **kwargs)
        except Exception, e:
            message = unicode(e)
            if message == '':
                message = _('Oops, apologies - there was some error')
            logging.debug(message)
            data = {
                'message': message,
                'success': 0
            }
            return HttpResponse(simplejson.dumps(data), mimetype='application/json')

        if isinstance(data, HttpResponse):#is this used?
            data.mimetype = 'application/json'
            return data
        else:
            data['success'] = 1
            json = simplejson.dumps(data)
            return HttpResponse(json, mimetype='application/json')
    return wrapper

def check_authorization_to_post(func_or_message):

    message = _('Please login to post')
    if not inspect.isfunction(func_or_message):
        message = unicode(func_or_message)

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_anonymous():
                #todo: expand for handling ajax responses
                if askbot_settings.ALLOW_POSTING_BEFORE_LOGGING_IN == False:
                    request.user.message_set.create(message = message)
                    params = 'next=%s' % request.path
                    return HttpResponseRedirect(url_utils.get_login_url() + '?' + params)
            return view_func(request, *args, **kwargs)
        return wrapper

    if inspect.isfunction(func_or_message):
        return decorator(func_or_message)
    else:
        return decorator

try:
    PROFILE_LOG_BASE = settings.PROFILE_LOG_BASE
except:
    PROFILE_LOG_BASE = "/tmp"

def profile(log_file):
    """Profile some callable.

    This decorator uses the hotshot profiler to profile some callable (like
    a view function or method) and dumps the profile data somewhere sensible
    for later processing and examination.

    It takes one argument, the profile log name. If it's a relative path, it
    places it under the PROFILE_LOG_BASE. It also inserts a time stamp into the 
    file name, such that 'my_view.prof' become 'my_view-20100211T170321.prof', 
    where the time stamp is in UTC. This makes it easy to run and compare 
    multiple trials.     

    http://code.djangoproject.com/wiki/ProfilingDjango
    """

    if not os.path.isabs(log_file):
        log_file = os.path.join(PROFILE_LOG_BASE, log_file)

    def _outer(f):
        def _inner(*args, **kwargs):
            # Add a timestamp to the profile output when the callable
            # is actually called.
            (base, ext) = os.path.splitext(log_file)
            base = base + "-" + time.strftime("%Y%m%dT%H%M%S", time.gmtime())
            final_log_file = base + ext

            prof = hotshot.Profile(final_log_file)
            try:
                ret = prof.runcall(f, *args, **kwargs)
            finally:
                prof.close()
            return ret

        return _inner
    return _outer

def check_spam(field):
    '''Decorator to check if there is spam in the form'''

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):

            if askbot_settings.USE_AKISMET and askbot_settings.AKISMET_API_KEY == "":
                raise ImproperlyConfigured('You have not set AKISMET_API_KEY')

            if askbot_settings.USE_AKISMET and request.method == "POST":
                comment = smart_str(request.POST[field])
                data = {'user_ip': request.META["REMOTE_ADDR"],
                        'user_agent': request.environ['HTTP_USER_AGENT'],
                        'comment_author': smart_str(request.user.username),
                        }
                if request.user.is_authenticated():
                    data.update({'comment_author_email': request.user.email})

                from akismet import Akismet
                api = Akismet(
                    askbot_settings.AKISMET_API_KEY, 
                    smart_str(askbot_settings.APP_URL), 
                    "Askbot/%s" % get_version()
                )

                if api.comment_check(comment, data, build_data=False):
                    logging.debug(
                        'Spam detected in %s post at: %s',
                        request.user.username,
                        datetime.datetime.now()
                    )
                    spam_message = _(
                        'Spam was detected on your post, sorry '
                        'for if this is a mistake'
                    )
                    if request.is_ajax():
                        return HttpResponseForbidden(
                                spam_message, 
                                mimetype="application/json"
                            )
                    else:
                        request.user.message_set.create(message=spam_message)
                        return HttpResponseRedirect(reverse('index'))

            return view_func(request, *args, **kwargs)
        return wrapper

    return decorator
