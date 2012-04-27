## Django settings for ASKBOT enabled project.
import os.path
import logging
import sys
import askbot
import site

#this line is added so that we can import pre-packaged askbot dependencies
ASKBOT_ROOT = os.path.abspath(os.path.dirname(askbot.__file__))
site.addsitedir(os.path.join(ASKBOT_ROOT, 'deps'))

DEBUG = True#set to True to enable debugging
TEMPLATE_DEBUG = False#keep false when debugging jinja2 templates
INTERNAL_IPS = ('127.0.0.1',)

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

#incoming mail settings
#after filling out these settings - please
#go to the site's live settings and enable the feature
#"Email settings" -> "allow asking by email"
#
#   WARNING: command post_emailed_questions DELETES all
#            emails from the mailbox each time
#            do not use your personal mail box here!!!
#
IMAP_HOST = ''
IMAP_HOST_USER = ''
IMAP_HOST_PASSWORD = ''
IMAP_PORT = ''
IMAP_USE_TLS = False

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
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
    #below is askbot stuff for this tuple
    #'askbot.skins.loaders.load_template_source', #changed due to bug 97
    'askbot.skins.loaders.filesystem_load_template_source',
    #'django.template.loaders.eggs.load_template_source',
)


MIDDLEWARE_CLASSES = (
    #'django.middleware.gzip.GZipMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
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
)


ROOT_URLCONF = os.path.basename(os.path.dirname(__file__)) + '.urls'


#UPLOAD SETTINGS
FILE_UPLOAD_TEMP_DIR = os.path.join(
                                os.path.dirname(__file__),
                                'tmp'
                            ).replace('\\','/')

FILE_UPLOAD_HANDLERS = (
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
)
ASKBOT_ALLOWED_UPLOAD_FILE_TYPES = ('.jpg', '.jpeg', '.gif', '.bmp', '.png', '.tiff')
ASKBOT_MAX_UPLOAD_FILE_SIZE = 1024 * 1024 #result in bytes
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'


#TEMPLATE_DIRS = (,) #template have no effect in askbot, use the variable below
#ASKBOT_EXTRA_SKINS_DIR = #path to your private skin collection
#take a look here http://askbot.org/en/question/207/

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.request',
    'askbot.context.application_settings',
    #'django.core.context_processors.i18n',
    'askbot.user_messages.context_processors.user_messages',#must be before auth
    'django.core.context_processors.auth', #this is required for admin
    'django.core.context_processors.csrf', #necessary for csrf protection
)


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
    #'debug_toolbar',
    'askbot',
    'askbot.deps.django_authopenid',
    #'askbot.importers.stackexchange', #se loader
    'south',
    'askbot.deps.livesettings',
    'keyedcache',
    'robots',
    'django_countries',
    'djcelery',
    'djkombu',
    'followit',
    #'avatar',#experimental use git clone git://github.com/ericflo/django-avatar.git$
)


#setup memcached for production use!
#see http://docs.djangoproject.com/en/1.1/topics/cache/ for details
CACHE_BACKEND = 'locmem://'
#needed for django-keyedcache
CACHE_TIMEOUT = 6000
CACHE_PREFIX = 'askbot' #make this unique
CACHE_MIDDLEWARE_ANONYMOUS_ONLY = True
#If you use memcache you may want to uncomment the following line to enable memcached based sessions
#SESSION_ENGINE = 'django.contrib.sessions.backends.cache_db'

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
ASKBOT_TRANSLATE_URL = True #translate specific URLs
_ = lambda v:v #fake translation function for the login url
LOGIN_URL = '/%s%s%s' % (ASKBOT_URL,_('account/'),_('signin/'))
LOGIN_REDIRECT_URL = ASKBOT_URL #adjust if needed
#note - it is important that upload dir url is NOT translated!!!
#also, this url must not have the leading slash
ALLOW_UNICODE_SLUGS = False
ASKBOT_USE_STACKEXCHANGE_URLS = False #mimic url scheme of stackexchange

#Celery Settings
BROKER_TRANSPORT = "djkombu.transport.DatabaseTransport"
CELERY_ALWAYS_EAGER = True

import djcelery
djcelery.setup_loader()

CSRF_COOKIE_NAME = 'askbot_csrf'
#enter domain name here - e.g. example.com
#CSRF_COOKIE_DOMAIN = ''

STATICFILES_DIRS = ( os.path.join(ASKBOT_ROOT, 'skins'),)

RECAPTCHA_USE_SSL = True
