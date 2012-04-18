"""tests to be performed
in the beginning of models/__init__.py

the purpose of this module is to validate deployment of askbot

question: why not run these from askbot/__init__.py?

the main function is run_startup_tests
"""
import sys
import os
from django.db import transaction
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
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
        'askbot.middleware.forum_mode.ForumModeMiddleware',
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

def try_import(module_name, pypi_package_name):
    """tries importing a module and advises to install
    A corresponding Python package in the case import fails"""
    try:
        load_module(module_name)
    except ImportError, error:
        message = 'Error: ' + unicode(error) 
        message += '\n\nPlease run: >pip install %s' % pypi_package_name
        message += '\n\nTo install all the dependencies at once, type:'
        message += '\npip install -r askbot_requirements.txt\n'
        message += '\nType ^C to quit.'
        raise ImproperlyConfigured(message)

def test_modules():
    """tests presence of required modules"""
    from askbot import REQUIREMENTS
    for module_name, pip_path in REQUIREMENTS.items():
        try_import(module_name, pip_path)

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

def test_tracking():
    """tests whether the necessary peices of the
    `django-tracking` app are registered in the `settings.py`
    """
    if 'tracking.middleware.BannedIPMiddleware' not in \
            django_settings.MIDDLEWARE_CLASSES:
        raise ImproperlyConfigured(PREAMBLE +
                "\nplease add line\n"
                "'tracking.middleware.BannedIPMiddleware',\n"
                "to the beginning of MIDDLEWARE_CLASSES in your "
                "settings.py file"
            )
    if 'tracking' not in django_settings.INSTALLED_APPS:
        raise ImproperlyConfigured(PREAMBLE +
                "\nplease add line\n"
                "'tracking',\n"
                "to your settings.py file"
            )



def test_template_loader():
    """Sends a warning if you have an old style template
    loader that used to send a warning"""
    old_template_loader = 'askbot.skins.loaders.load_template_source'
    if old_template_loader in django_settings.TEMPLATE_LOADERS:
        raise ImproperlyConfigured(PREAMBLE + \
                "\nPlease change: \n"
                "'askbot.skins.loaders.load_template_source', to\n"
                "'askbot.skins.loaders.filesystem_load_template_source',\n"
                "in the TEMPLATE_LOADERS of your settings.py file"
        )

def test_celery():
    """Tests celery settings
    todo: we are testing two things here
    that correct name is used for the setting
    and that a valid value is chosen
    """
    broker_backend = getattr(django_settings, 'BROKER_BACKEND', None)
    broker_transport = getattr(django_settings, 'BROKER_TRANSPORT', None)

    if broker_backend is None:
        if broker_transport is None:
            raise ImproperlyConfigured(PREAMBLE + \
                "\nPlease add\n"
                'BROKER_TRANSPORT = "djkombu.transport.DatabaseTransport"\n'
                "or other valid value to your settings.py file"
            )
        else:
            #todo: check that broker transport setting is valid
            return

    if broker_backend != broker_transport:
        raise ImproperlyConfigured(PREAMBLE + \
            "\nPlease rename setting BROKER_BACKEND to BROKER_TRANSPORT\n"
            "in your settings.py file\n"
            "If you have both in your settings.py - then\n"
            "delete the BROKER_BACKEND setting and leave the BROKER_TRANSPORT"
        )

    if hasattr(django_settings, 'BROKER_BACKEND') and not hasattr(django_settings, 'BROKER_TRANSPORT'):
        raise ImproperlyConfigured(PREAMBLE + \
            "\nPlease rename setting BROKER_BACKEND to BROKER_TRANSPORT\n"
            "in your settings.py file"
        )

class SettingsTester(object):
    """class to test contents of the settings.py file"""

    def __init__(self, requirements = None):
        """loads the settings module and inits some variables
        parameter `requirements` is a dictionary with keys
        as setting names and values - another dictionary, which
        has keys (optional, if noted and required otherwise)::

        * required_value (optional)
        * error_message
        """
        self.settings = load_module(os.environ['DJANGO_SETTINGS_MODULE'])
        self.messages = list()
        self.requirements = requirements


    def test_setting(self, name, value = None, message = None):
        """if setting does is not present or if the value != required_value,
        adds an error message
        """
        if not hasattr(self.settings, name):
            self.messages.append(message)
        elif value and getattr(self.settings, name) != value:
            self.messages.append(message)

    def run(self):
        for setting_name in self.requirements:
            self.test_setting(
                setting_name,
                **self.requirements[setting_name]
            )
        if len(self.messages) != 0:
            raise ImproperlyConfigured(
                PREAMBLE + 
                '\n\nTime to do some maintenance of your settings.py:\n\n* ' + 
                '\n\n* '.join(self.messages)
            )

def run_startup_tests():
    """function that runs
    all startup tests, mainly checking settings config so far
    """

    #todo: refactor this when another test arrives
    test_template_loader()
    test_encoding()
    test_modules()
    test_askbot_url()
    #test_postgres()
    test_middleware()
    test_tracking()
    test_celery()
    settings_tester = SettingsTester({
        'CACHE_MIDDLEWARE_ANONYMOUS_ONLY': {
            'value': True,
            'message': "add line CACHE_MIDDLEWARE_ANONYMOUS_ONLY = True"
        },
        'USE_I18N': {
            'value': True,
            'message': 'Please set USE_I18N = True and\n'
                'set the LANGUAGE_CODE parameter correctly'
        },
        'LOGIN_REDIRECT_URL': {
            'message': 'add setting LOGIN_REDIRECT_URL - an url\n'
                'where you want to send users after they log in\n'
                'a reasonable default is\n'
                'LOGIN_REDIRECT_URL = ASKBOT_URL'
        }
    })
    settings_tester.run()

@transaction.commit_manually
def run():
    """runs all the startup procedures"""
    try:
        run_startup_tests()
    except ImproperlyConfigured, error:
        transaction.rollback()
        print error
        sys.exit(1)
    try:
        from askbot.models import badges
        badges.init_badges()
        transaction.commit()
    except Exception, error:
        print error
        transaction.rollback()
