from django.core.urlresolvers import reverse
from django.conf import settings

def get_login_url():
    """returns internal login url if
    django_authopenid is used, or 
    the corresponding django setting
    """
    if 'askbot.deps.django_authopenid' in settings.INSTALLED_APPS:
        return reverse('user_signin')
    else:
        return settings.LOGIN_URL

def get_logout_url():
    """returns internal logout url
    if django_authopenid is used or
    the django setting"""
    if 'askbot.deps.django_authopenid' in settings.INSTALLED_APPS:
        return reverse('user_signout')
    else:
        return settings.LOGOUT_URL

def get_logout_redirect_url():
    """returns internal logout redirect url,
    or settings.LOGOUT_REDIRECT_URL if it exists
    or url to the main page"""
    if 'askbot.deps.django_authopenid' in settings.INSTALLED_APPS:
        return reverse('logout')
    elif hasattr(settings, 'LOGOUT_REDIRECT_URL'):
        return settings.LOGOUT_REDIRECT_URL
    else:
        return reverse('index')
