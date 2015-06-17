from .util import get_the_only_login_provider
from askbot.utils import forms
from django.conf import settings as django_settings
from django.core.urlresolvers import reverse
from .forms import LoginForm

def get_after_login_url(request):
    """returns url where user should go after successful login"""
    #next_url is first priority value of "next"
    #second priority - LOGIN_REDIRECT_URL
    #third priority - current page
    login_redirect = getattr(django_settings, 'LOGIN_REDIRECT_URL', None)
    if login_redirect in (None, django_settings.ASKBOT_URL):
        #after login stay on current page
        default_next = request.path
    else:
        #after login go to the special page
        default_next = login_redirect
    return forms.get_next_url(request, default_next)

def login_context(request):
    """context necessary for the login functionality
    """
    next_url = get_after_login_url(request)
    login_form = LoginForm(initial={'next': next_url})
    return {
        'on_login_page': (request.path == reverse('user_signin')),
        'unique_login_provider': get_the_only_login_provider(),
        'login_form': login_form
    }
