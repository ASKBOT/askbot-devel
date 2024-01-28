"""
contains :class:`ForumModeMiddleware`, which is
enabling support of closed forum mode
"""
from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _
from django.conf import settings
from django.urls import resolve
from askbot.conf import settings as askbot_settings
from askbot.utils import url_utils
from askbot.utils.functions import encode_jwt
from askbot.utils.views import is_askbot_view
import urllib.request, urllib.parse, urllib.error

ALLOWED_VIEWS = (
    'askbot.views.meta.config_variable',
)


def is_view_allowed(func):
    """True, if view is allowed to access
    by the special rule
    """
    if hasattr(func, '__name__'):
        view_path = func.__module__ + '.' + func.__name__
    elif hasattr(func, '__class__'):
        view_path = func.__module__ + '.' + func.__class__.__name__
    else:
        view_path = ''

    return view_path in ALLOWED_VIEWS

class ForumModeMiddleware:
    """protects forum views is the closed forum mode"""

    def __init__(self, get_response=None): # i think get_reponse is never None. If it's not another middleware it's the view, I think
        if get_response is None:
            get_response = lambda x:x
        self.get_response = get_response

    def __call__(self, request):
        response  = self.process_request(request)
        if response is None:
            response = self.get_response(request) # i think this simply chains all middleware
        return response

    def process_request(self, request):
        """when askbot is in the closed mode
        it will let through only authenticated users.
        All others will be redirected to the login url.
        """
        if (askbot_settings.ASKBOT_CLOSED_FORUM_MODE
                and request.user.is_anonymous):
            resolver_match = resolve(request.path)
            if not is_askbot_view(resolver_match.func):
                return None

            internal_ips = getattr(settings, 'ASKBOT_INTERNAL_IPS', None)
            if internal_ips and request.META.get('REMOTE_ADDR') in internal_ips:
                return None

            if is_view_allowed(resolver_match.func):
                return None

            if is_askbot_view(resolver_match.func):
                request.user.message_set.create(
                    _('Please log in to use %s') % \
                    askbot_settings.APP_SHORT_NAME
                )
                redirect_url = '{}?next={}'.format(
                    url_utils.get_login_url(),
                    encode_jwt({'next_url': request.get_full_path()})
                )
                return HttpResponseRedirect(redirect_url)
        return None
