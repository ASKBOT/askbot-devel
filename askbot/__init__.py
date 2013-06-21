"""
:synopsis: the Django Q&A forum application

Functions in the askbot module perform various
basic actions on behalf of the forum application
"""
import os
import platform

VERSION = (0, 7, 48)

#keys are module names used by python imports,
#values - the package qualifier to use for pip
REQUIREMENTS = {
    'akismet': 'akismet',
    'django': 'django>=1.3.1,<1.5',
    'compressor': 'django-compressor==1.2',
    'jinja2': 'Jinja2',
    'coffin': 'Coffin>=0.3',
    'south': 'South>=0.7.1',
    'oauth2': 'oauth2',
    'markdown2': 'markdown2',
    'html5lib': 'html5lib==0.90',
    'keyedcache': 'django-keyedcache',
    'threaded_multihost': 'django-threaded-multihost',
    'robots': 'django-robots',
    'sanction': 'sanction',
    'unidecode': 'unidecode',
    'django_countries': 'django-countries==1.0.5',
    'djcelery': 'django-celery==3.0.11',
    'djkombu': 'django-kombu==0.9.4',
    'followit': 'django-followit',
    'recaptcha_works': 'django-recaptcha-works',
    'openid': 'python-openid',
    'pystache': 'pystache==0.3.1',
    'pytz': 'pytz',
    'tinymce': 'django-tinymce==1.5.1b2',
    'longerusername': 'longerusername',
    'bs4': 'beautifulsoup4',
    'picklefield': 'django-picklefield==0.3.0',
}

if platform.system() != 'Windows':
    REQUIREMENTS['lamson'] = 'Lamson'

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
