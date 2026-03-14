import time
import os
import functools
import inspect
import logging
from django.conf import settings
from django.core import exceptions as django_exceptions
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.http import HttpResponseRedirect
import json
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.encoding import smart_str
from askbot import exceptions as askbot_exceptions
from askbot.conf import settings as askbot_settings
from askbot.utils import url_utils
from askbot.utils.html import site_url
from askbot.utils.http import is_ajax
from askbot.utils.functions import encode_jwt


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
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        else:
            content = json.dumps({'login_required':True})
            return HttpResponseForbidden(content, content_type='application/json')
    return wrap


def anonymous_forbidden(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_anonymous:
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
        if not is_ajax(request):
            raise Http404
        try:
            data = view_func(request, *args, **kwargs)
            if data is None:
                data = {}
        except Exception as e: # pylint: disable=broad-except
            #todo: also check field called "message"
            if hasattr(e, 'messages'):
                if len(e.messages) > 1:
                    message = '<ul>' + \
                        ''.join(
                            ['<li>%s</li>' % v for v in e.messages]
                        ) + \
                        '</ul>'
                else:
                    message = e.messages[0]
            else:
                message = str(e)
            if message == '':
                message = _('Oops, apologies - there was some error')
            logging.debug(message)
            data = {
                'message': message,
                'success': 0
            }
            return HttpResponse(json.dumps(data), content_type='application/json')

        if isinstance(data, HttpResponse):#is this used?
            data.content_type = 'application/json'
            return data
        else:
            data['success'] = 1
            content = json.dumps(data)
            return HttpResponse(content, content_type='application/json')
    return wrapper

def check_authorization_to_post(func_or_message):
    message = _('Please login to post')
    if not inspect.isfunction(func_or_message):
        message = func_or_message

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_anonymous:
                #todo: expand for handling ajax responses
                if askbot_settings.ALLOW_POSTING_BEFORE_LOGGING_IN == False:
                    request.user.message_set.create(message=message)
                    params = 'next=%s' % encode_jwt({'next_url': request.path})
                    return HttpResponseRedirect(url_utils.get_login_url() + '?' + params)
            return view_func(request, *args, **kwargs)
        return wrapper

    if inspect.isfunction(func_or_message):
        return decorator(func_or_message)
    else:
        return decorator


def moderators_only(view_func):
    @functools.wraps(view_func)
    def decorator(request, *args, **kwargs):
        if request.user.is_anonymous:
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
        if request.user.is_anonymous:
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
