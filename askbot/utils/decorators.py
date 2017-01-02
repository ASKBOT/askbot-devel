import hotshot
import time
import os
import functools
import inspect
import logging
from django.conf import settings
from django.core import exceptions as django_exceptions
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.http import HttpResponseRedirect
import simplejson
from django.utils import timezone
from django.utils.translation import ugettext as _
from django.utils.encoding import smart_str
from askbot import exceptions as askbot_exceptions
from askbot.conf import settings as askbot_settings
from askbot.utils import url_utils
from askbot.utils.html import site_url
from askbot.utils.akismet_utils import akismet_check_spam


def auto_now_timestamp(func):
    """decorator that will automatically set
    argument named timestamp to the "now" value if timestamp == None

    if there is no timestamp argument, then exception is raised
    """
    @functools.wraps(func)
    def decorating_func(*arg, **kwarg):
        timestamp = kwarg.get('timestamp', None)
        if timestamp is None:
            kwarg['timestamp'] = timezone.now()
        return func(*arg, **kwarg)
    return decorating_func


def ajax_login_required(view_func):
    @functools.wraps(view_func)
    def wrap(request, *args, **kwargs):
        if request.user.is_authenticated():
            return view_func(request, *args, **kwargs)
        else:
            json = simplejson.dumps({'login_required':True})
            return HttpResponseForbidden(json, content_type='application/json')
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
            if data is None:
                data = {}
        except Exception, e:
            #todo: also check field called "message"
            if hasattr(e, 'messages'):
                if len(e.messages) > 1:
                    message = u'<ul>' + \
                        u''.join(
                            map(lambda v: u'<li>%s</li>' % v, e.messages)
                        ) + \
                        u'</ul>'
                else:
                    message = e.messages[0]
            else:
                message = unicode(e)
            if message == '':
                message = _('Oops, apologies - there was some error')
            logging.debug(message)
            data = {
                'message': message,
                'success': 0
            }
            return HttpResponse(simplejson.dumps(data), content_type='application/json')

        if isinstance(data, HttpResponse):#is this used?
            data.content_type = 'application/json'
            return data
        else:
            data['success'] = 1
            json = simplejson.dumps(data)
            return HttpResponse(json, content_type='application/json')
    return wrapper

def check_authorization_to_post(func_or_message):
    message = _('Please login to post')
    if not inspect.isfunction(func_or_message):
        message = func_or_message

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_anonymous():
                #todo: expand for handling ajax responses
                if askbot_settings.ALLOW_POSTING_BEFORE_LOGGING_IN == False:
                    request.user.message_set.create(message=unicode(message))
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
    # TODO: remove use of this decorator in favor of explicit calls
    # from within view functions

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):

            if askbot_settings.USE_AKISMET and request.method == "POST":
                if field not in request.POST:
                    raise Http404

                comment = smart_str(request.POST[field])
                if akismet_check_spam(comment, request):
                    logging.debug(
                        'Spam detected in %s post at: %s',
                        request.user.username,
                        timezone.now()
                    )
                    spam_message = _(
                        'Spam was detected on your post, sorry '
                        'for if this is a mistake'
                    )
                    if request.is_ajax():
                        return HttpResponseForbidden(
                                spam_message,
                                content_type="application/json"
                            )
                    else:
                        request.user.message_set.create(message=spam_message)
                        return HttpResponseRedirect(reverse('index'))

            return view_func(request, *args, **kwargs)
        return wrapper

    return decorator

def moderators_only(view_func):
    @functools.wraps(view_func)
    def decorator(request, *args, **kwargs):
        if request.user.is_anonymous():
            raise django_exceptions.PermissionDenied()
        if not request.user.is_administrator_or_moderator():
            raise django_exceptions.PermissionDenied(
            _('This function is limited to moderators and administrators')
        )
        return view_func(request, *args, **kwargs)
    return decorator


def admins_only(view_func):
    @functools.wraps(view_func)
    def decorator(request, *args, **kwargs):
        if request.user.is_anonymous():
            raise django_exceptions.PermissionDenied()
        if not request.user.is_administrator():
            raise django_exceptions.PermissionDenied(
            _('This function is limited to administrators')
        )
        return view_func(request, *args, **kwargs)
    return decorator


def reject_forbidden_phrases(func):
    """apply to functions that make posts
    assuming kwargs (all optional):
        title, tags, body_text, ip_addr

    assumes that first of *args is User

    todo: this might be factored out into
    moderation module
    """

    @functools.wraps(func)
    def wrapped(*args, **kwargs):

        user = args[0]
        if not user.is_administrator_or_moderator():
            text_bits = list()
            if 'title' in kwargs:
                text_bits.append(kwargs['title'])
            if 'tags' in kwargs:
                text_bits.append(kwargs['tags'])
            if 'body_text' in kwargs:
                text_bits.append(kwargs['body_text'])

            combined_text = ' '.join(text_bits)
            from askbot.utils.markup import find_forbidden_phrase
            from askbot import signals
            phrase = find_forbidden_phrase(combined_text)
            if phrase:
                signals.spam_rejected.send(None,
                    spam=phrase,
                    text=combined_text,
                    user=user,
                    ip_addr=kwargs.get('ip_addr', 'unknown')
                )
                raise ValueError #cause 500
        return func(*args, **kwargs)

    return wrapped
