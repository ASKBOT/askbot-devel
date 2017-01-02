"""
:synopsis: the Django Q&A forum application

Functions in the askbot module perform various
basic actions on behalf of the forum application
"""
import os
import platform

VERSION = (0, 10, 2)

default_app_config = 'askbot.apps.AskbotConfig'

#keys are module names used by python imports,
#values - the package qualifier to use for pip
REQUIREMENTS = {
    'akismet': 'akismet<=0.2.0',
    'avatar': 'django-avatar==2.2.1',
    'bs4': 'beautifulsoup4<=4.4.1',
    'coffin': 'Coffin>=0.3,<=0.3.8',
    'compressor': 'django-compressor>=1.3,<=1.5',
    'django': 'django>=1.8,<1.9',
    'django_countries': 'django-countries==3.3',
    'djcelery': 'django-celery>=3.0.11,<=3.1.17',
    'celery': 'celery==3.1.18',
    'djkombu': 'django-kombu==0.9.4',
    'followit': 'django-followit==0.2.1',
    'html5lib': 'html5lib==0.9999999',
    'jinja2': 'Jinja2==2.8',
    'jsonfield': 'jsonfield<=1.0.3',
    'jwt': 'pyjwt<=1.4.0',
    'keyedcache': 'django-keyedcache<=1.5.1',
    'markdown2': 'markdown2<=2.3.1',
    'mock': 'mock==1.0.1',
    'oauth2': 'oauth2<=1.9.0.post1',
    'openid': 'python-openid<=2.2.5',
    'picklefield': 'django-picklefield==0.3.0',
    'pystache': 'pystache==0.3.1',
    'pytz': 'pytz<=2016.4',
    'captcha': 'django-recaptcha>=1.0.3,<=1.0.5',
    'cas': 'python-cas==1.1.0',
    'requirements': 'requirements-parser==0.1.0',
    'robots': 'django-robots==1.1',
    'regex': 'regex',
    'sanction': 'sanction==0.3.1',
    'simplejson': 'simplejson<=3.8.2',
    'south': 'South>=0.7.1,<=1.0.2',
    'threaded_multihost': 'django-threaded-multihost<=1.4-1',
    'tinymce': 'django-tinymce==1.5.3',
    'unidecode': 'unidecode<=0.4.19',
    #'stopforumspam': 'stopforumspam'
}

if platform.system() != 'Windows':
    REQUIREMENTS['lamson'] = 'Lamson<=1.3.4'

#necessary for interoperability of django and coffin
try:
    from askbot import patches
    from askbot.deployment.assertions import assert_package_compatibility
    assert_package_compatibility()
    patches.patch_django()
    patches.patch_coffin()  # must go after django
except ImportError:
    pass


def get_install_directory():
    """returns path to directory
    where code of the askbot django application
    is installed
    """
    return os.path.dirname(__file__)


def get_path_to(relative_path):
    """returns absolute path to a file
    relative to ``askbot`` directory
    ``relative_path`` must use only forward slashes
    and must not start with a slash
    """
    root_dir = get_install_directory()
    assert(relative_path[0] != 0)
    path_bits = relative_path.split('/')
    return os.path.join(root_dir, *path_bits)


def get_version():
    """returns version of the askbot app
    this version is meaningful for pypi only
    """
    return '.'.join([str(subversion) for subversion in VERSION])


def get_database_engine_name():
    """returns name of the database engine,
    independently of the version of django
    - for django >=1.2 looks into ``settings.DATABASES['default']``,
    (i.e. assumes that askbot uses database named 'default')
    , and for django 1.1 and below returns settings.DATABASE_ENGINE
    """
    import django
    from django.conf import settings as django_settings
    major_version = django.VERSION[0]
    minor_version = django.VERSION[1]
    if major_version == 1:
        if minor_version > 1:
            return django_settings.DATABASES['default']['ENGINE']
        else:
            return django_settings.DATABASE_ENGINE


def get_lang_mode():
    from django.conf import settings as django_settings
    return getattr(django_settings, 'ASKBOT_LANGUAGE_MODE', 'single-lang')


def is_multilingual():
    return get_lang_mode() != 'single-lang'
