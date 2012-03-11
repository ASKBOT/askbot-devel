"""tests to be performed
in the beginning of models/__init__.py

the purpose of this module is to validate deployment of askbot

question: why not run these from askbot/__init__.py?

the main function is run_startup_tests
"""
import sys
import os
import re
import askbot
from django.db import transaction
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from askbot.utils.loading import load_module
from askbot.utils.functions import enumerate_string_list
from urlparse import urlparse

PREAMBLE = """\n
************************
*                      *
*   Askbot self-test   *
*                      *
************************\n
"""

FOOTER = """\n
If necessary, type ^C (Ctrl-C) to stop the program.
"""

class AskbotConfigError(ImproperlyConfigured):
    """Prints an error with a preamble and possibly a footer"""
    def __init__(self, error_message):
        msg = PREAMBLE + error_message
        if sys.__stdin__.isatty():
            #print footer only when askbot is run from the shell
            msg += FOOTER
            super(AskbotConfigError, self).__init__(msg)

def askbot_warning(line):
    """prints a warning with the nice header, but does not quit"""
    print >> sys.stderr, PREAMBLE + '\n' + line

def print_errors(error_messages, header = None, footer = None):
    """if there is one or more error messages,
    raise ``class:AskbotConfigError`` with the human readable
    contents of the message
    * ``header`` - text to show above messages
    * ``footer`` - text to show below messages
    """
    if len(error_messages) == 0:
        return
    if len(error_messages) > 1:
        error_messages = enumerate_string_list(error_messages)

    message = ''
    if header: message += header + '\n'
    message += 'Please attend to the following:\n\n'
    message += '\n\n'.join(error_messages)
    if footer:
        message += '\n\n' + footer
    raise AskbotConfigError(message)

def format_as_text_tuple_entries(items):
    """prints out as entries or tuple containing strings
    ready for copy-pasting into say django settings file"""
    return "    '%s'," % "',\n    '".join(items)

#todo:
#
# *validate emails in settings.py
def test_askbot_url():
    """Tests the ASKBOT_URL setting for the
    well-formedness and raises the :class:`AskbotConfigError`
    exception, if the setting is not good.
    """
    url = django_settings.ASKBOT_URL
    if url != '':

        if isinstance(url, str) or isinstance(url, unicode):
            pass
        else:
            msg = 'setting ASKBOT_URL must be of string or unicode type'
            raise AskbotConfigError(msg)

        if url == '/':
            msg = 'value "/" for ASKBOT_URL is invalid. '+ \
                'Please, either make ASKBOT_URL an empty string ' + \
                'or a non-empty path, ending with "/" but not ' + \
                'starting with "/", for example: "forum/"'
            raise AskbotConfigError(msg)
        else:
            try:
                assert(url.endswith('/'))
            except AssertionError:
                msg = 'if ASKBOT_URL setting is not empty, ' + \
                        'it must end with /'
                raise AskbotConfigError(msg)
            try:
                assert(not url.startswith('/'))
            except AssertionError:
                msg = 'if ASKBOT_URL setting is not empty, ' + \
                        'it must not start with /'

def test_middleware():
    """Checks that all required middleware classes are
    installed in the django settings.py file. If that is not the
    case - raises an AskbotConfigError exception.
    """
    required_middleware = [
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'askbot.middleware.anon_user.ConnectToSessionMessagesMiddleware',
        'askbot.middleware.forum_mode.ForumModeMiddleware',
        'askbot.middleware.cancel.CancelActionMiddleware',
        'django.middleware.transaction.TransactionMiddleware',
    ]
    if 'debug_toolbar' in django_settings.INSTALLED_APPS:
        required_middleware.append(
            'debug_toolbar.middleware.DebugToolbarMiddleware',
        )
    required_middleware.extend([
        'askbot.middleware.view_log.ViewLogMiddleware',
        'askbot.middleware.spaceless.SpacelessMiddleware',
    ])
    found_middleware = [x for x in django_settings.MIDDLEWARE_CLASSES
                            if x in required_middleware]
    if found_middleware != required_middleware:
        # either middleware is out of order or it's missing an item
        missing_middleware_set = set(required_middleware) - set(found_middleware)
        middleware_text = ''
        if missing_middleware_set:
            error_message = """\n\nPlease add the following middleware (listed after this message)
to the MIDDLEWARE_CLASSES variable in your site settings.py file.
The order the middleware records is important, please take a look at the example in
https://github.com/ASKBOT/askbot-devel/blob/master/askbot/setup_templates/settings.py:\n\n"""
            middleware_text = format_as_text_tuple_entries(missing_middleware_set)
        else:
            # middleware is out of order
            error_message = """\n\nPlease check the order of middleware closely.
The order the middleware records is important, please take a look at the example in
https://github.com/ASKBOT/askbot-devel/blob/master/askbot/setup_templates/settings.py
for the correct order.\n\n"""
        raise AskbotConfigError(error_message + middleware_text)


    #middleware that was used in the past an now removed
    canceled_middleware = [
        'askbot.deps.recaptcha_django.middleware.ReCaptchaMiddleware'
    ]

    invalid_middleware = [x for x in canceled_middleware
                            if x in django_settings.MIDDLEWARE_CLASSES]
    if invalid_middleware:
        error_message = """\n\nPlease remove the following middleware entries from
the list of MIDDLEWARE_CLASSES in your settings.py - these are not used any more:\n\n"""
        middleware_text = format_as_text_tuple_entries(invalid_middleware)
        raise AskbotConfigError(error_message + middleware_text)

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
        raise AskbotConfigError(message)

def test_modules():
    """tests presence of required modules"""
    from askbot import REQUIREMENTS
    for module_name, pip_path in REQUIREMENTS.items():
        try_import(module_name, pip_path)

def test_postgres():
    """Checks for the postgres buggy driver, version 2.4.2"""
    if 'postgresql_psycopg2' in askbot.get_database_engine_name():
        import psycopg2
        version = psycopg2.__version__.split(' ')[0].split('.')
        if version == ['2', '4', '2']:
            raise AskbotConfigError(
                'Please install psycopg2 version 2.4.1,\n version 2.4.2 has a bug'
            )
        elif version > ['2', '4', '2']:
            pass #don't know what to do
        else:
            pass #everythin is ok

def test_encoding():
    """prints warning if encoding error is not UTF-8"""
    if hasattr(sys.stdout, 'encoding'):
        if sys.stdout.encoding != 'UTF-8':
            askbot_warning(
                'Your output encoding is not UTF-8, there may be '
                'issues with the software when anything is printed '
                'to the terminal or log files'
            )

def test_template_loader():
    """Sends a warning if you have an old style template
    loader that used to send a warning"""
    old_template_loader = 'askbot.skins.loaders.load_template_source'
    if old_template_loader in django_settings.TEMPLATE_LOADERS:
        raise AskbotConfigError(
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
            raise AskbotConfigError(
                "\nPlease add\n"
                'BROKER_TRANSPORT = "djkombu.transport.DatabaseTransport"\n'
                "or other valid value to your settings.py file"
            )
        else:
            #todo: check that broker transport setting is valid
            return

    if broker_backend != broker_transport:
        raise AskbotConfigError(
            "\nPlease rename setting BROKER_BACKEND to BROKER_TRANSPORT\n"
            "in your settings.py file\n"
            "If you have both in your settings.py - then\n"
            "delete the BROKER_BACKEND setting and leave the BROKER_TRANSPORT"
        )

    if hasattr(django_settings, 'BROKER_BACKEND') and not hasattr(django_settings, 'BROKER_TRANSPORT'):
        raise AskbotConfigError(
            "\nPlease rename setting BROKER_BACKEND to BROKER_TRANSPORT\n"
            "in your settings.py file"
        )

def test_media_url():
    """makes sure that setting `MEDIA_URL`
    has leading slash"""
    media_url = django_settings.MEDIA_URL
    #todo: add proper url validation to MEDIA_URL setting
    if not (media_url.startswith('/') or media_url.startswith('http')):
        raise AskbotConfigError(
            "\nMEDIA_URL parameter must be a unique url on the site\n"
            "and must start with a slash - e.g. /media/ or http(s)://"
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


    def test_setting(self, name,
            value = None, message = None,
            test_for_absence = False,
            replace_hint = None
        ):
        """if setting does is not present or if the value != required_value,
        adds an error message
        """
        if test_for_absence:
            if hasattr(self.settings, name):
                if replace_hint:
                    value = getattr(self.settings, name)
                    message += replace_hint % value
                self.messages.append(message)
        else:
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
            raise AskbotConfigError(
                '\n\nTime to do some maintenance of your settings.py:\n\n* ' + 
                '\n\n* '.join(self.messages)
            )
            
def test_staticfiles():
    """tests configuration of the staticfiles app"""
    errors = list()
    import django
    django_version = django.VERSION
    if django_version[0] == 1 and django_version[1] < 3:
        staticfiles_app_name = 'staticfiles'
        wrong_staticfiles_app_name = 'django.contrib.staticfiles'
        try_import('staticfiles', 'django-staticfiles')
        import staticfiles
        if staticfiles.__version__[0] != 1:
            raise AskbotConfigError(
                'Please use the newest available version of '
                'django-staticfiles app, type\n'
                'pip install --upgrade django-staticfiles'
            )
        if not hasattr(django_settings, 'STATICFILES_STORAGE'):
            raise AskbotConfigError(
                'Configure STATICFILES_STORAGE setting as desired, '
                'a reasonable default is\n'
                "STATICFILES_STORAGE = 'staticfiles.storage.StaticFilesStorage'"
            )
    else:
        staticfiles_app_name = 'django.contrib.staticfiles'
        wrong_staticfiles_app_name = 'staticfiles'

    if staticfiles_app_name not in django_settings.INSTALLED_APPS:
        errors.append(
            'Add to the INSTALLED_APPS section of your settings.py:\n'
            "    '%s'," % staticfiles_app_name
        )
    if wrong_staticfiles_app_name in django_settings.INSTALLED_APPS:
        errors.append(
            'Remove from the INSTALLED_APPS section of your settings.py:\n'
            "    '%s'," % wrong_staticfiles_app_name
        )
    static_url = django_settings.STATIC_URL or ''
    if static_url is None or str(static_url).strip() == '':
        errors.append(
            'Add STATIC_URL setting to your settings.py file. '
            'The setting must be a url at which static files ' 
            'are accessible.'
        )
    url = urlparse(static_url).path
    if not (url.startswith('/') and url.endswith('/')):
        #a simple check for the url
        errors.append(
            'Path in the STATIC_URL must start and end with the /.'
        )
    if django_settings.ADMIN_MEDIA_PREFIX != static_url + 'admin/':
        errors.append(
            'Set ADMIN_MEDIA_PREFIX as: \n'
            "    ADMIN_MEDIA_PREFIX = STATIC_URL + 'admin/'"
        )

    askbot_root = os.path.dirname(askbot.__file__)
    skin_dir = os.path.abspath(os.path.join(askbot_root, 'skins'))

    # django_settings.STATICFILES_DIRS can have strings or tuples
    staticfiles_dirs = [d[1] if isinstance(d, tuple) else d
                        for d in django_settings.STATICFILES_DIRS]
    if skin_dir not in map(os.path.abspath, staticfiles_dirs):
        errors.append(
            'Add to STATICFILES_DIRS list of your settings.py file:\n'
            "    '%s'," % skin_dir
        )
    extra_skins_dir = getattr(django_settings, 'ASKBOT_EXTRA_SKINS_DIR', None)
    if extra_skins_dir is not None:
        if not os.path.isdir(extra_skins_dir):
            errors.append(
                'Directory specified with settning ASKBOT_EXTRA_SKINS_DIR '
                'must exist and contain your custom skins for askbot.'
            )
        if extra_skins_dir not in staticfiles_dirs:
            errors.append(
                'Add ASKBOT_EXTRA_SKINS_DIR to STATICFILES_DIRS entry in '
                'your settings.py file.\n'
                'NOTE: it might be necessary to move the line with '
                'ASKBOT_EXTRA_SKINS_DIR just above STATICFILES_DIRS.'
            )

    if django_settings.STATICFILES_STORAGE == \
        'django.contrib.staticfiles.storage.StaticFilesStorage':
        if os.path.dirname(django_settings.STATIC_ROOT) == '':
            #static root is needed only for local storoge of
            #the static files
            raise AskbotConfigError(
                'Specify the static files directory '
                'with setting STATIC_ROOT'
            )

    if errors:
        errors.append(
            'Run command (after fixing the above errors)\n'
            '    python manage.py collectstatic\n'
        )

            
    print_errors(errors)
    if django_settings.STATICFILES_STORAGE == \
        'django.contrib.staticfiles.storage.StaticFilesStorage':

        if not os.path.isdir(django_settings.STATIC_ROOT):
            askbot_warning(
                'Please run command\n\n'
                '    python manage.py collectstatic'

            )

def test_csrf_cookie_domain():
    """makes sure that csrf cookie domain setting is acceptable"""
    #todo: maybe use the same steps to clean domain name
    csrf_cookie_domain = django_settings.CSRF_COOKIE_DOMAIN
    if csrf_cookie_domain is None or str(csrf_cookie_domain.strip()) == '':
        raise AskbotConfigError(
            'Please add settings CSRF_COOKIE_DOMAN and CSRF_COOKIE_NAME '
            'settings - both are required. '
            'CSRF_COOKIE_DOMAIN must match the domain name of yor site, '
            'without the http(s):// prefix and without the port number.\n'
            'Examples: \n'
            "    CSRF_COOKIE_DOMAIN = '127.0.0.1'\n"
            "    CSRF_COOKIE_DOMAIN = 'example.com'\n"
        )
    if csrf_cookie_domain == 'localhost':
        raise AskbotConfigError(
            'Please do not use value "localhost" for the setting '
            'CSRF_COOKIE_DOMAIN\n'
            'instead use 127.0.0.1, a real IP '
            'address or domain name.'
            '\nThe value must match the network location you type in the '
            'web browser to reach your site.'
        )
    if re.match(r'https?://', csrf_cookie_domain):
        raise AskbotConfigError(
            'please remove http(s):// prefix in the CSRF_COOKIE_DOMAIN '
            'setting'
        )
    if ':' in csrf_cookie_domain:
        raise AskbotConfigError(
            'Please do not use port number in the CSRF_COOKIE_DOMAIN '
            'setting'
        )

def test_settings_for_test_runner():
    """makes sure that debug toolbar is disabled when running tests"""
    errors = list()
    if 'debug_toolbar' in django_settings.INSTALLED_APPS:
        errors.append(
            'When testing - remove debug_toolbar from INSTALLED_APPS'
        )
    if 'debug_toolbar.middleware.DebugToolbarMiddleware' in \
        django_settings.MIDDLEWARE_CLASSES:
        errors.append(
            'When testing - remove debug_toolbar.middleware.DebugToolbarMiddleware '
            'from MIDDLEWARE_CLASSES'
        )
    print_errors(errors)
    

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
    test_celery()
    #test_csrf_cookie_domain()
    test_staticfiles()
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
        },
        'ASKBOT_FILE_UPLOAD_DIR': {
            'test_for_absence': True,
            'message': 'Please replace setting ASKBOT_FILE_UPLOAD_DIR ',
            'replace_hint': "with MEDIA_ROOT = '%s'"
        },
        'ASKBOT_UPLOADED_FILES_URL': {
            'test_for_absence': True,
            'message': 'Please replace setting ASKBOT_UPLOADED_FILES_URL ',
            'replace_hint': "with MEDIA_URL = '/%s'"
        }
    })
    settings_tester.run()
    test_media_url()
    if 'manage.py test' in ' '.join(sys.argv):
        test_settings_for_test_runner()

@transaction.commit_manually
def run():
    """runs all the startup procedures"""
    try:
        run_startup_tests()
    except AskbotConfigError, error:
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
