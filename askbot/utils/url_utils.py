"""utilities to work with the urls"""
import importlib
import sys
import urllib.parse
from django.urls import reverse, re_path
from django.conf import settings as django_settings
from django.urls import clear_url_caches
from django.utils import translation

def reload_urlconf():
    """Reloads the urlconf file and clears the url caches"""
    clear_url_caches()
    urlconf = django_settings.ROOT_URLCONF
    if urlconf in sys.modules:
        importlib.reload(sys.modules[urlconf])

def reverse_i18n(lang, *args, **kwargs):
    """reverses url in requested language"""
    assert lang is not None
    current_lang = translation.get_language()
    translation.activate(lang)
    i18n_url = reverse(*args, **kwargs)
    translation.activate(current_lang)
    return i18n_url

def service_url(*args, **kwargs):
    """adds the service prefix to the url"""
    pattern = args[0]
    if pattern[0] == '^':
        pattern = pattern[1:]

    prefix = django_settings.ASKBOT_SERVICE_URL_PREFIX
    pattern = prefix + pattern
    new_args = list(args)
    new_args[0] = pattern
    return re_path(*new_args, **kwargs)

def strip_path(input_url):
    """srips path, params and hash fragments of the url"""
    purl = urllib.parse.urlparse(input_url)
    return urllib.parse.urlunparse(
        urllib.parse.ParseResult(
            purl.scheme,
            purl.netloc,
            '', '', '', ''
        )
    )

def append_trailing_slash(urlpath):
    """if path is empty - returns slash
    if not and path does not end with the slash
    appends it
    """
    if urlpath == '':
        return '/'
    if not urlpath.endswith('/'):
        return urlpath + '/'
    return urlpath

def urls_equal(url1, url2, ignore_trailing_slash=False):
    """True, if urls are equal"""
    purl1 = urllib.parse.urlparse(url1)
    purl2 = urllib.parse.urlparse(url2)
    if purl1.scheme != purl2.scheme:
        return False

    if purl1.netloc != purl2.netloc:
        return False

    if ignore_trailing_slash is True:
        normfunc = append_trailing_slash
    else:
        normfunc = lambda v: v

    if normfunc(purl1.path) != normfunc(purl2.path):
        return False

    #test remaining items in the parsed url
    return purl1[3:] == purl2[3:]

def get_login_url():
    """returns internal login url if
    django_authopenid is used, or
    the corresponding django setting
    """
    if 'askbot.deps.django_authopenid' in django_settings.INSTALLED_APPS:
        return getattr(django_settings, 'ASKBOT_LOGIN_URL', reverse('user_signin'))
    return django_settings.LOGIN_URL

def get_logout_url():
    """returns internal logout url
    if django_authopenid is used or
    the django setting"""
    if 'askbot.deps.django_authopenid' in django_settings.INSTALLED_APPS:
        return reverse('user_signout')
    return django_settings.LOGOUT_URL

def get_logout_redirect_url():
    """returns internal logout redirect url,
    or django_settings.LOGOUT_REDIRECT_URL if it exists
    or url to the main page"""
    if hasattr(django_settings, 'LOGOUT_REDIRECT_URL'):
        return django_settings.LOGOUT_REDIRECT_URL
    return reverse('index')
