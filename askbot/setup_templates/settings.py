## Django settings for ASKBOT enabled project.
import os.path
import logging
import sys
import askbot
import site

#this line is added so that we can import pre-packaged askbot dependencies
ASKBOT_ROOT = os.path.abspath(os.path.dirname(askbot.__file__))
site.addsitedir(os.path.join(ASKBOT_ROOT, 'deps'))

DEBUG = True  # set to True to enable debugging
TEMPLATE_DEBUG = False  # keep false when debugging jinja2 templates
INTERNAL_IPS = ('127.0.0.1',)
ALLOWED_HOSTS = ['*',]#change this for better security on your site

ADMINS = (
    ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DATABASE_ENGINE = 'postgresql_psycopg2' # only postgres (>8.3) and mysql are supported so far others have not been tested yet
DATABASE_NAME = ''             # Or path to database file if using sqlite3.
DATABASE_USER = ''             # Not used with sqlite3.
DATABASE_PASSWORD = ''         # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

#outgoing mail server settings
SERVER_EMAIL = ''
DEFAULT_FROM_EMAIL = ''
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_SUBJECT_PREFIX = ''
EMAIL_HOST=''
EMAIL_PORT=''
EMAIL_USE_TLS=False
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Chicago'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True
LANGUAGE_CODE = 'en'
LANGUAGES = (('en', 'English'),)

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(os.path.dirname(__file__), 'askbot', 'upfiles')
MEDIA_URL = '/upfiles/'#url to uploaded media
STATIC_URL = '/m/'#url to project static files

PROJECT_ROOT = os.path.dirname(__file__)
STATIC_ROOT = os.path.join(PROJECT_ROOT, 'static')#path to files collected by collectstatic

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = STATIC_URL + 'admin/'#must be this value

# Make up some unique string, and don't share it with anybody.
SECRET_KEY = 'sdljdfjkldsflsdjkhsjkldgjlsdgfs s '

# List of callables that know how to import templates from various sources.
TEMPLATES = (
    {
        'BACKEND': 'askbot.skins.template_backends.AskbotSkinTemplates',
    },
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
            ]
        }
    },
)

MIDDLEWARE_CLASSES = (
    #'django.middleware.gzip.GZipMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    ## Enable the following middleware if you want to enable
    ## language selection in the site settings.
    #'askbot.middleware.locale.LocaleMiddleware',
    #'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.common.CommonMiddleware',
    #'django.middleware.cache.FetchFromCacheMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    #'django.middleware.sqlprint.SqlPrintingMiddleware',

    #below is askbot stuff for this tuple
    'askbot.middleware.anon_user.ConnectToSessionMessagesMiddleware',
    'askbot.middleware.forum_mode.ForumModeMiddleware',
    'askbot.middleware.cancel.CancelActionMiddleware',
    'django.middleware.transaction.TransactionMiddleware',
    #'debug_toolbar.middleware.DebugToolbarMiddleware',
    'askbot.middleware.view_log.ViewLogMiddleware',
    'askbot.middleware.spaceless.SpacelessMiddleware',
    'askbot.middleware.csrf.CsrfViewMiddleware',
)

JINJA2_EXTENSIONS = (
    'compressor.contrib.jinja2ext.CompressorExtension',
)

COMPRESS_PRECOMPILERS = (
    ('text/less', 'lessc {infile} {outfile}'),
)


ROOT_URLCONF = os.path.basename(os.path.dirname(__file__)) + '.urls'


INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',

    #all of these are needed for the askbot
    'django.contrib.admin',
    'django.contrib.humanize',
    'django.contrib.sitemaps',
    'django.contrib.messages',
    'compressor',
    #'debug_toolbar',
    #'haystack',
    'askbot',
    'askbot.deps.django_authopenid',
    #'askbot.importers.stackexchange', #se loader
    'askbot.deps.livesettings',
    'keyedcache',
    'robots',
    'django_countries',
    'djcelery',
    'djkombu',
    'followit',
    'tinymce',
    #'avatar',#experimental use git clone git://github.com/ericflo/django-avatar.git$

    'compressor',
)


#setup memcached for production use!
# See http://docs.djangoproject.com/en/1.8/topics/cache/ for details.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'askbot',
        'TIMEOUT': 6000,
        # Chose a unique KEY_PREFIX to avoid clashes with other applications
        # using the same cache (e.g. a shared memcache instance).
        'KEY_PREFIX': 'askbot',
    }
}

#sets a special timeout for livesettings if you want to make them different
LIVESETTINGS_CACHE_TIMEOUT = CACHES['default']['TIMEOUT']
CACHE_MIDDLEWARE_ANONYMOUS_ONLY = True
CACHE_MIDDLEWARE_SECONDS = 600
#If you use memcache you may want to uncomment the following line to enable memcached based sessions
#SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'askbot.deps.django_authopenid.backends.AuthBackend',
)

#logging settings
LOG_FILENAME = 'askbot.log'
logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), 'log', LOG_FILENAME),
    level=logging.CRITICAL,
    format='%(pathname)s TIME: %(asctime)s MSG: %(filename)s:%(funcName)s:%(lineno)d %(message)s',
)

###########################
#
#   this will allow running your forum with url like http://site.com/forum
#
#   ASKBOT_URL = 'forum/'
#
ASKBOT_URL = '' #no leading slash, default = '' empty string
_ = lambda v:v #fake translation function for the login url
LOGIN_URL = '/%s%s%s' % (ASKBOT_URL, _('account/'), _('signin/'))
LOGIN_REDIRECT_URL = ASKBOT_URL #adjust if needed
#note - it is important that upload dir url is NOT translated!!!
#also, this url must not have the leading slash
ALLOW_UNICODE_SLUGS = False

#Celery Settings
BROKER_TRANSPORT = "djkombu.transport.DatabaseTransport"
CELERY_ALWAYS_EAGER = True

import djcelery
djcelery.setup_loader()

STATICFILES_DIRS = (
    ('default/media', os.path.join(ASKBOT_ROOT, 'media')),
)
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

RECAPTCHA_USE_SSL = True

#HAYSTACK_SETTINGS
ENABLE_HAYSTACK_SEARCH = False
#Uncomment for multilingual setup:
#HAYSTACK_ROUTERS = ['askbot.search.haystack.routers.LanguageRouter',]

#Uncomment if you use haystack
#More info in http://django-haystack.readthedocs.org/en/latest/settings.html
#HAYSTACK_CONNECTIONS = {
#            'default': {
#                        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
#            }
#}

#delayed notifications, time in seconds, 15 mins by default
NOTIFICATION_DELAY_TIME = 60 * 15

GROUP_MESSAGING = {
    'BASE_URL_GETTER_FUNCTION': 'askbot.models.user_get_profile_url',
    'BASE_URL_PARAMS': {'section': 'messages', 'sort': 'inbox'}
}

COMPRESS_JS_FILTERS = []
COMPRESS_PARSER = 'compressor.parser.HtmlParser'
JINJA2_EXTENSIONS = ('compressor.contrib.jinja2ext.CompressorExtension',)

VERIFIER_EXPIRE_DAYS = 3
AVATAR_AUTO_GENERATE_SIZES = (16, 32, 48, 128)

SESSION_SERIALIZER = 'django.contrib.sessions.serializers.PickleSerializer'
