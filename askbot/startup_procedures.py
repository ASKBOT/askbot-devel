"""tests to be performed
in the beginning of models/__init__.py

the purpose of this module is to validate deployment of askbot

question: why not run these from askbot/__init__.py?

the main function is run_startup_tests
"""
import sys
from django.db import transaction
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from askbot.models import badges
from askbot.utils.loading import load_module

PREAMBLE = """\n
************************
*                      *
*   Askbot self-test   *
*                      *
************************"""

def askbot_warning(line):
    """prints a warning with the nice header, but does not quit"""
    print >> sys.stderr, PREAMBLE + '\n' + line

def format_as_text_tuple_entries(items):
    """prints out as entries or tuple containing strings
    ready for copy-pasting into say django settings file"""
    return "    '%s'," % "',\n    '".join(items)

#todo:
#
# *validate emails in settings.py
def test_askbot_url():
    """Tests the ASKBOT_URL setting for the 
    well-formedness and raises the ImproperlyConfigured
    exception, if the setting is not good.
    """
    url = django_settings.ASKBOT_URL
    if url != '':

        if isinstance(url, str) or isinstance(url, unicode):
            pass
        else:
            msg = 'setting ASKBOT_URL must be of string or unicode type'
            raise ImproperlyConfigured(msg)

        if url == '/':
            msg = 'value "/" for ASKBOT_URL is invalid. '+ \
                'Please, either make ASKBOT_URL an empty string ' + \
                'or a non-empty path, ending with "/" but not ' + \
                'starting with "/", for example: "forum/"'
            raise ImproperlyConfigured(msg)
        else:
            try:
                assert(url.endswith('/'))
            except AssertionError:
                msg = 'if ASKBOT_URL setting is not empty, ' + \
                        'it must end with /'
                raise ImproperlyConfigured(msg)
            try:
                assert(not url.startswith('/'))
            except AssertionError:
                msg = 'if ASKBOT_URL setting is not empty, ' + \
                        'it must not start with /'

def test_middleware():
    """Checks that all required middleware classes are
    installed in the django settings.py file. If that is not the
    case - raises an ImproperlyConfigured exception.
    """
    required_middleware = (
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'askbot.middleware.anon_user.ConnectToSessionMessagesMiddleware',
        'askbot.middleware.pagesize.QuestionsPageSizeMiddleware',
        'askbot.middleware.cancel.CancelActionMiddleware',
        'django.middleware.transaction.TransactionMiddleware',
        'askbot.middleware.view_log.ViewLogMiddleware',
    )
    if 'debug_toolbar' in django_settings.INSTALLED_APPS:
        required_middleware += (
            'debug_toolbar.middleware.DebugToolbarMiddleware',
        )

    installed_middleware_set = set(django_settings.MIDDLEWARE_CLASSES)
    missing_middleware_set = set(required_middleware) - installed_middleware_set

    if missing_middleware_set:
        error_message = """\n\nPlease add the following middleware (listed after this message)
to the MIDDLEWARE_CLASSES variable in your site settings.py file. 
The order the middleware records may be important, please take a look at the example in 
https://github.com/ASKBOT/askbot-devel/blob/master/askbot/setup_templates/settings.py:\n\n"""
        middleware_text = format_as_text_tuple_entries(missing_middleware_set)
        raise ImproperlyConfigured(PREAMBLE + error_message + middleware_text)


    #middleware that was used in the past an now removed
    canceled_middleware = (
        'askbot.deps.recaptcha_django.middleware.ReCaptchaMiddleware',
    )
    #'debug_toolbar.middleware.DebugToolbarMiddleware',

    remove_middleware_set = set(canceled_middleware) \
                                & installed_middleware_set
    if remove_middleware_set:
        error_message = """\n\nPlease remove the following middleware entries from
the list of MIDDLEWARE_CLASSES in your settings.py - these are not used any more:\n\n"""
        middleware_text = format_as_text_tuple_entries(remove_middleware_set)
        raise ImproperlyConfigured(PREAMBLE + error_message + middleware_text)

            

def test_i18n():
    """askbot requires use of USE_I18N setting"""
    if getattr(django_settings, 'USE_I18N', False) == False:
        raise ImproperlyConfigured(
            'Please set USE_I18N = True in settings.py and '
            'set the LANGUAGE_CODE parameter correctly '
            'it is very important for askbot.'
        )

def try_import(module_name, pypi_package_name):
    """tries importing a module and advises to install 
    A corresponding Python package in the case import fails"""
    try:
        load_module(module_name)
    except ImportError, error:
        message = unicode(error) + ' run\npip install %s' % pypi_package_name
        message += '\nTo install all the dependencies at once, type:'
        message += '\npip install -r askbot_requirements.txt\n'
        raise ImproperlyConfigured(message)

def test_modules():
    """tests presence of required modules"""
    try_import('akismet', 'akismet')
    try_import('recaptcha_works', 'django-recaptcha-works')

def test_postgres():
    """Checks for the postgres buggy driver, version 2.4.2"""
    if hasattr(django_settings, 'DATABASE_ENGINE'):
        if django_settings.DATABASE_ENGINE in ('postgresql_psycopg2',):
            try:
                import psycopg2
                version = psycopg2.__version__.split(' ')[0].split('.')
                if version == ['2', '4', '2']:
                    raise ImproperlyConfigured(
                        'Please install psycopg2 version 2.4.1,\n version 2.4.2 has a bug'
                    )
                elif version > ['2', '4', '2']:
                    pass #don't know what to do
                else:
                    pass #everythin is ok
            except ImportError:
                #Using mysql not a problem
                pass
        else:
            pass #using other thing than postgres
    else:
        pass #TODO: test new django dictionary databases

def test_encoding():
    """prints warning if encoding error is not UTF-8"""
    if hasattr(sys.stdout, 'encoding'):
        if sys.stdout.encoding != 'UTF-8':
            askbot_warning(
                'Your output encoding is not UTF-8, there may be '
                'issues with the software when anything is printed '
                'to the terminal or log files'
            )

def run_startup_tests():
    """function that runs
    all startup tests, mainly checking settings config so far
    """

    #todo: refactor this when another test arrives
    test_encoding()
    test_modules()
    test_askbot_url()
    test_i18n()
    test_postgres()
    test_middleware()

@transaction.commit_manually
def run():
    """runs all the startup procedures"""
    run_startup_tests()
    try:
        badges.init_badges()
        transaction.commit()
    except Exception, error:
        print error
        transaction.rollback()
