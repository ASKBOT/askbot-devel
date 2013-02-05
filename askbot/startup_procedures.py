"""tests to be performed
in the beginning of models/__init__.py

the purpose of this module is to validate deployment of askbot

question: why not run these from askbot/__init__.py?

the main function is run_startup_tests
"""
import askbot
import django
import os
import re
import south
import sys
import urllib
from django.db import transaction, connection
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from askbot.utils.loading import load_module
from askbot.utils.functions import enumerate_string_list
from askbot.utils.url_utils import urls_equal
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
    print >> sys.stderr, line

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

def try_import(module_name, pypi_package_name, short_message = False):
    """tries importing a module and advises to install
    A corresponding Python package in the case import fails"""
    try:
        load_module(module_name)
    except ImportError, error:
        message = 'Error: ' + unicode(error)
        message += '\n\nPlease run: >pip install %s' % pypi_package_name
        if short_message == False:
            message += '\n\nTo install all the dependencies at once, type:'
            message += '\npip install -r askbot_requirements.txt'
        message += '\n\nType ^C to quit.'
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
    old_loaders = (
        'askbot.skins.loaders.load_template_source',
        'askbot.skins.loaders.filesystem_load_template_source',
    )
    errors = list()
    for loader in old_loaders:
        if loader in django_settings.TEMPLATE_LOADERS:
            errors.append(
                'remove "%s" from the TEMPLATE_LOADERS setting' % loader
            )

    current_loader = 'askbot.skins.loaders.Loader'
    if current_loader not in django_settings.TEMPLATE_LOADERS:
        errors.append(
            'add "%s" to the beginning of the TEMPLATE_LOADERS' % current_loader
        )
    elif django_settings.TEMPLATE_LOADERS[0] != current_loader:
        errors.append(
            '"%s" must be the first element of TEMPLATE_LOADERS' % current_loader
        )
        
    print_errors(errors)

def test_celery():
    """Tests celery settings
    todo: we are testing two things here
    that correct name is used for the setting
    and that a valid value is chosen
    """
    broker_backend = getattr(django_settings, 'BROKER_BACKEND', None)
    broker_transport = getattr(django_settings, 'BROKER_TRANSPORT', None)
    delay_time = getattr(django_settings, 'NOTIFICATION_DELAY_TIME', None)
    delay_setting_info = 'The delay is in seconds - used to throttle ' + \
                    'instant notifications note that this delay will work only if ' + \
                    'celery daemon is running Please search about ' + \
                    '"celery daemon setup" for details'

    if delay_time is None:
        raise AskbotConfigError(
            '\nPlease add to your settings.py\n' + \
            'NOTIFICATION_DELAY_TIME = 60*15\n' + \
            delay_setting_info
        )
    else:
        if not isinstance(delay_time, int):
            raise AskbotConfigError(
                '\nNOTIFICATION_DELAY_TIME setting must have a numeric value\n' + \
                delay_setting_info
            )


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


def test_new_skins():
    """tests that there are no directories in the `askbot/skins`
    because we've moved skin files a few levels up"""
    askbot_root = askbot.get_install_directory()
    for item in os.listdir(os.path.join(askbot_root, 'skins')):
        item_path = os.path.join(askbot_root, 'skins', item)
        if os.path.isdir(item_path):
            raise AskbotConfigError(
                ('Time to move skin files from %s.\n'
                'Now we have `askbot/templates` and `askbot/media`') % item_path
            )

def test_staticfiles():
    """tests configuration of the staticfiles app"""
    errors = list()
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

    # django_settings.STATICFILES_DIRS can have strings or tuples
    staticfiles_dirs = [d[1] if isinstance(d, tuple) else d
                        for d in django_settings.STATICFILES_DIRS]

    default_skin_tuple = None
    askbot_root = askbot.get_install_directory()
    old_default_skin_dir = os.path.abspath(os.path.join(askbot_root, 'skins'))
    for dir_entry in django_settings.STATICFILES_DIRS:
        if isinstance(dir_entry, tuple):
            if dir_entry[0] == 'default/media':
                default_skin_tuple = dir_entry
        elif isinstance(dir_entry, str):
            if os.path.abspath(dir_entry) == old_default_skin_dir:
                errors.append(
                    'Remove from STATICFILES_DIRS in your settings.py file:\n' + dir_entry
                )

    askbot_root = os.path.dirname(askbot.__file__)
    default_skin_media_dir = os.path.abspath(os.path.join(askbot_root, 'media'))
    if default_skin_tuple:
        media_dir = default_skin_tuple[1]
        if default_skin_media_dir != os.path.abspath(media_dir):
            errors.append(
                'Add to STATICFILES_DIRS the following entry: '
                "('default/media', os.path.join(ASKBOT_ROOT, 'media')),"
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


def test_avatar():
    """if "avatar" is in the installed apps,
    checks that the module is actually installed"""
    if 'avatar' in django_settings.INSTALLED_APPS:
        try_import('Image', 'PIL', short_message = True)
        try_import(
            'avatar',
            '-e git+git://github.com/ericflo/django-avatar.git#egg=avatar',
            short_message = True
        )

def test_haystack():
    if 'haystack' in django_settings.INSTALLED_APPS:
        try_import('haystack', 'django-haystack', short_message = True)
        if getattr(django_settings, 'ENABLE_HAYSTACK_SEARCH', False):
            errors = list()
            if not hasattr(django_settings, 'HAYSTACK_SEARCH_ENGINE'):
                message = "Please HAYSTACK_SEARCH_ENGINE to an appropriate value, value 'simple' can be used for basic testing"
                errors.append(message)
            if not hasattr(django_settings, 'HAYSTACK_SITECONF'):
                message = 'Please add HAYSTACK_SITECONF = "askbot.search.haystack"'
                errors.append(message)
            footer = 'Please refer to haystack documentation at http://django-haystack.readthedocs.org/en/v1.2.7/settings.html#haystack-search-engine'
            print_errors(errors, footer=footer)

def test_custom_user_profile_tab():
    setting_name = 'ASKBOT_CUSTOM_USER_PROFILE_TAB'
    tab_settings = getattr(django_settings, setting_name, None)
    if tab_settings:
        if not isinstance(tab_settings, dict):
            print "Setting %s must be a dictionary!!!" % setting_name

        name = tab_settings.get('NAME', None)
        slug = tab_settings.get('SLUG', None)
        func_name = tab_settings.get('CONTENT_GENERATOR', None)

        errors = list()
        if (name is None) or (not(isinstance(name, basestring))):
            errors.append("%s['NAME'] must be a string" % setting_name)
        if (slug is None) or (not(isinstance(slug, str))):
            errors.append("%s['SLUG'] must be an ASCII string" % setting_name)

        if urllib.quote_plus(slug) != slug:
            errors.append(
                "%s['SLUG'] must be url safe, make it simple" % setting_name
            )

        try:
            func = load_module(func_name)
        except ImportError:
            errors.append("%s['CONTENT_GENERATOR'] must be a dotted path to a function" % setting_name)
        header = 'Custom user profile tab is configured incorrectly in your settings.py file'
        footer = 'Please carefully read about adding a custom user profile tab.'
        print_errors(errors, header = header, footer = footer)

def get_tinymce_sample_config():
    """returns the sample configuration for TinyMCE
    as string"""
    askbot_root = askbot.get_install_directory()
    file_path = os.path.join(
                    askbot_root, 'setup_templates', 'tinymce_sample_config.py'
                )
    config_file = open(file_path, 'r')
    sample_config = config_file.read()
    config_file.close()
    return sample_config

def test_tinymce():
    """tests the tinymce editor setup"""
    errors = list()
    if 'tinymce' not in django_settings.INSTALLED_APPS:
        errors.append("add 'tinymce', to the INSTALLED_APPS")

    required_attrs = (
        'TINYMCE_COMPRESSOR',
        'TINYMCE_JS_ROOT',
        'TINYMCE_URL',
        'TINYMCE_DEFAULT_CONFIG'
    )

    missing_attrs = list()
    for attr in required_attrs:
        if not hasattr(django_settings, attr):
            missing_attrs.append(attr)

    if missing_attrs:
        errors.append('add missing settings: %s' % ', '.join(missing_attrs))

    #check compressor setting
    compressor_on = getattr(django_settings, 'TINYMCE_COMPRESSOR', False)
    if compressor_on is False:
        errors.append('add line: TINYMCE_COMPRESSOR = True')
        #todo: add pointer to instructions on how to debug tinymce:
        #1) add ('tiny_mce', os.path.join(ASKBOT_ROOT, 'media/js/tinymce')),
        #   to STATIFILES_DIRS
        #2) add this to the main urlconf:
        #    (
        #        r'^m/(?P<path>.*)$',
        #        'django.views.static.serve',
        #        {'document_root': static_root}
        #    ),
        #3) set `TINYMCE_COMPRESSOR = False`
        #4) set DEBUG = False
        #then - tinymce compressing will be disabled and it will
        #be possible to debug custom tinymce plugins that are used with askbot


    config = getattr(django_settings, 'TINYMCE_DEFAULT_CONFIG', None)
    if config:
        if 'convert_urls' in config:
            if config['convert_urls'] is not False:
                message = "set 'convert_urls':False in TINYMCE_DEFAULT_CONFIG"
                errors.append(message)
        else:
            message = "add to TINYMCE_DEFAULT_CONFIG\n'convert_urls': False,"
            errors.append(message)


    #check js root setting - before version 0.7.44 we used to have
    #"common" skin and after we combined it into the default
    js_root = getattr(django_settings, 'TINYMCE_JS_ROOT', '')
    old_relative_js_path = 'common/media/js/tinymce/'
    relative_js_path = 'default/media/js/tinymce/'
    expected_js_root = os.path.join(django_settings.STATIC_ROOT, relative_js_path)
    old_expected_js_root = os.path.join(django_settings.STATIC_ROOT, old_relative_js_path)
    if os.path.normpath(js_root) != os.path.normpath(expected_js_root):
        error_tpl = "add line: TINYMCE_JS_ROOT = os.path.join(STATIC_ROOT, '%s')"
        if os.path.normpath(js_root) == os.path.normpath(old_expected_js_root):
            error_tpl += '\nNote: we have moved files from "common" into "default"'
        errors.append(error_tpl % relative_js_path)

    #check url setting
    url = getattr(django_settings, 'TINYMCE_URL', '')
    expected_url = django_settings.STATIC_URL + relative_js_path
    old_expected_url = django_settings.STATIC_URL + old_relative_js_path
    if urls_equal(url, expected_url) is False:
        error_tpl = "add line: TINYMCE_URL = STATIC_URL + '%s'"
        if urls_equal(url, old_expected_url):
            error_tpl += '\nNote: we have moved files from "common" into "default"'
        errors.append(error_tpl % relative_js_path)

    if errors:
        header = 'Please add the tynymce editor configuration ' + \
            'to your settings.py file.'
        footer = 'You might want to use this sample configuration ' + \
                'as template:\n\n' + get_tinymce_sample_config()
        print_errors(errors, header=header, footer=footer)

def test_longerusername():
    """tests proper installation of the "longerusername" app
    """
    errors = list()
    if 'longerusername' not in django_settings.INSTALLED_APPS:
        errors.append(
            "add 'longerusername', as the first item in the INSTALLED_APPS"
        )
    else:
        index = django_settings.INSTALLED_APPS.index('longerusername')
        if index != 0:
            message = "move 'longerusername', to the beginning of INSTALLED_APPS"
            raise AskbotConfigError(message)

    if errors:
        errors.append('run "python manage.py migrate longerusername"')
        print_errors(errors)

def test_template_context_processors():
    """makes sure that all necessary template context processors
    are in the settings.py"""

    required_processors = [
        'django.core.context_processors.request',
        'askbot.context.application_settings',
        'askbot.user_messages.context_processors.user_messages',
        'django.core.context_processors.csrf',
    ]
    old_auth_processor = 'django.core.context_processors.auth'
    new_auth_processor = 'django.contrib.auth.context_processors.auth'

    invalid_processors = list()
    if django.VERSION[1] <= 3:
        required_processors.append(old_auth_processor)
        if new_auth_processor in django_settings.TEMPLATE_CONTEXT_PROCESSORS:
            invalid_processors.append(new_auth_processor)
    elif django.VERSION[1] > 3:
        required_processors.append(new_auth_processor)
        if old_auth_processor in django_settings.TEMPLATE_CONTEXT_PROCESSORS:
            invalid_processors.append(old_auth_processor)
            
    missing_processors = list()
    for processor in required_processors:
        if processor not in django_settings.TEMPLATE_CONTEXT_PROCESSORS:
            missing_processors.append(processor)

    errors = list()
    if invalid_processors:
        message = 'remove from TEMPLATE_CONTEXT_PROCESSORS in settings.py:\n'
        message += format_as_text_tuple_entries(invalid_processors)
        errors.append(message)

    if missing_processors:
        message = 'add to TEMPLATE_CONTEXT_PROCESSORS in settings.py:\n'
        message += format_as_text_tuple_entries(missing_processors)
        errors.append(message)

    print_errors(errors)


def test_cache_backend():
    """prints a warning if cache backend is disabled or per-process"""
    if django.VERSION[1] > 2:
        backend = django_settings.CACHES['default']['BACKEND']
    else:
        backend = django_settings.CACHE_BACKEND

    errors = list()
    if backend.strip() == '' or 'dummy' in backend:
        message = """Please enable at least a "locmem" cache (for a single process server).
If you need to run > 1 server process, set up some production caching system,
such as redis or memcached"""
        errors.append(message)

    if 'locmem' in backend:
        message = """WARNING!!! You are using a 'locmem' (local memory) caching backend,
which is OK for a low volume site running on a single-process server.
For a multi-process configuration it is neccessary to have a production
cache system, such as redis or memcached.

With local memory caching and multi-process setup you might intermittently
see outdated content on your site.
"""
        askbot_warning(message)


def test_group_messaging():
    """tests correctness of the "group_messaging" app configuration"""
    errors = list()
    if 'group_messaging' not in django_settings.INSTALLED_APPS:
        errors.append("add to the INSTALLED_APPS:\n'group_messaging'")

    settings_sample = ("GROUP_MESSAGING = {\n"
    "    'BASE_URL_GETTER_FUNCTION': 'askbot.models.user_get_profile_url',\n"
    "    'BASE_URL_PARAMS': {'section': 'messages', 'sort': 'inbox'}\n"
    "}")

    settings = getattr(django_settings, 'GROUP_MESSAGING', {})
    if settings:
        url_params = settings.get('BASE_URL_PARAMS', {})
        have_wrong_params = not (
                        url_params.get('section', None) == 'messages' and \
                        url_params.get('sort', None) == 'inbox'
                    )
        url_getter = settings.get('BASE_URL_GETTER_FUNCTION', None)
        if url_getter != 'askbot.models.user_get_profile_url' or have_wrong_params:
            errors.append(
                "make setting 'GROUP_MESSAGING to be exactly:\n" + settings_sample
            )
            
        url_params = settings.get('BASE_URL_PARAMS', None)
    else:
        errors.append('add this to your settings.py:\n' + settings_sample)

    if errors:
        print_errors(errors)


def test_secret_key():
    key = django_settings.SECRET_KEY
    if key.strip() == '':
        print_errors(['please create a random SECRET_KEY setting',])
    elif key == 'sdljdfjkldsflsdjkhsjkldgjlsdgfs s ':
        print_errors([
            'Please change your SECRET_KEY setting, the current is not secure'
        ])


def test_multilingual():
    is_multilang = getattr(django_settings, 'ASKBOT_MULTILINGUAL', False)

    errors = list()

    if is_multilang:
        middleware = 'django.middleware.locale.LocaleMiddleware' 
        if middleware not in django_settings.MIDDLEWARE_CLASSES:
            errors.append(
                "add 'django.middleware.locale.LocaleMiddleware' to your MIDDLEWARE_CLASSES "
                "if you want a multilingual setup"
            )

    django_version = django.VERSION
    if is_multilang and django_version[0] == 1 and django_version[1] < 4:
        errors.append('ASKBOT_MULTILINGUAL=True works only with django >= 1.4')

    trans_url = getattr(django_settings, 'ASKBOT_TRANSLATE_URL', False)
    if is_multilang and trans_url:
        errors.append(
            'Please set ASKBOT_TRANSLATE_URL to False, the "True" option '
            'is currently not supported due to a bug in django'
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
    test_template_context_processors()
    test_tinymce()
    test_staticfiles()
    test_new_skins()
    test_longerusername()
    test_avatar()
    test_group_messaging()
    test_multilingual()
    test_haystack()
    test_cache_backend()
    test_secret_key()
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
        },
        'RECAPTCHA_USE_SSL': {
            'value': True,
            'message': 'Please add: RECAPTCHA_USE_SSL = True'
        },
        'HAYSTACK_SITECONF': {
            'value': 'askbot.search.haystack',
            'message': 'Please add: HAYSTACK_SITECONF = "askbot.search.haystack"'
        }
    })
    settings_tester.run()
    test_media_url()
    if 'manage.py test' in ' '.join(sys.argv):
        test_settings_for_test_runner()
    test_custom_user_profile_tab()

@transaction.commit_manually
def run():
    """runs all the startup procedures"""
    try:
        run_startup_tests()
    except AskbotConfigError, error:
        transaction.rollback()
        raise
    try:
        from askbot.models import badges
        badges.init_badges()
        transaction.commit()
    except Exception, error:
        transaction.rollback()
        raise
