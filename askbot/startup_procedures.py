"""tests to be performed
in the beginning of models/__init__.py

the purpose of this module is to validate deployment of askbot

question: why not run these from askbot/__init__.py?

the main function is run_startup_tests
"""

from askbot.conf.static_settings import settings as django_settings
import askbot
import django
import os
import importlib
import re
import sys
import urllib.request, urllib.parse, urllib.error
from urllib.parse import urlparse
from django.db import connection
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from askbot.utils.loading import load_function, load_module
from askbot.utils.functions import enumerate_string_list
from askbot.utils.url_utils import urls_equal

PREAMBLE = """\n
************************
*                      *
*   Askbot self-test   *
*                      *
************************\n
"""

FOOTER = """\n
If necessary, type ^C (Ctrl-C) to stop the program
(to disable the self-test add ASKBOT_SELF_TEST = False).
"""


class AskbotConfigError(ImproperlyConfigured):
    """Prints an error with a preamble and possibly a footer"""
    def __init__(self, error_message):
        msg = PREAMBLE + error_message
        if sys.__stdin__.isatty():
            #print footer only when askbot is run from the shell
            msg += FOOTER
            super(AskbotConfigError, self).__init__(msg)


def domain_is_bad():
    from askbot.conf import settings as askbot_settings
    parsed = urlparse(askbot_settings.APP_URL)
    if parsed.netloc == '':
        return True
    if parsed.scheme not in ('http', 'https'):
        return True
    return False


def askbot_warning(line):
    """prints a warning with the nice header, but does not quit"""
    print(str(line).encode('utf-8'), file=sys.stderr)


def print_errors(error_messages, header=None, footer=None):
    """if there is one or more error messages,
    raise ``class:AskbotConfigError`` with the human readable
    contents of the message
    * ``header`` - text to show above messages
    * ``footer`` - text to show below messages
    """
    if not error_messages:
        return
    if len(error_messages) > 1:
        error_messages = enumerate_string_list(error_messages)

    message = ''
    if header:
        message += header + '\n'
    message += 'Please attend to the following:\n\n'
    message += '\n\n'.join(error_messages)
    if footer:
        message += '\n\n' + footer

    raise AskbotConfigError(message)


def format_as_text_tuple_entries(items):
    """prints out as entries or tuple containing strings
    ready for copy-pasting into say django settings file"""
    return "    '%s'," % "',\n    '".join(items)


# TODO: *validate emails in settings.py
def test_askbot_url():
    """Tests the ASKBOT_URL setting for the
    well-formedness and raises the :class:`AskbotConfigError`
    exception, if the setting is not good.
    """
    url = django_settings.ASKBOT_URL
    if url != '':

        if not isinstance(url, str):
            msg = 'setting ASKBOT_URL must be of string or unicode type'
            raise AskbotConfigError(msg)

        if url == '/':
            msg = 'value "/" for ASKBOT_URL is invalid. ' + \
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


def test_jinja2():
    """tests Jinja2 settings"""
    compressor_ext = 'compressor.contrib.jinja2ext.CompressorExtension'
    ext_list = getattr(django_settings, 'JINJA2_EXTENSIONS', None)
    errors = list()
    if ext_list is None:
        errors.append(
            "Please add the following line to your settings.py:\n"
            "JINJA2_EXTENSIONS = ('%s',)" % compressor_ext
        )
    elif compressor_ext not in ext_list:
        errors.append(
            "Please add to the JINJA2_EXTENSIONS list an item:\n"
            "'%s'," % compressor_ext
        )

    print_errors(errors)


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
        #'django.middleware.transaction.TransactionMiddleware',
    ]
    #if 'debug_toolbar' in django_settings.INSTALLED_APPS:
    #    required_middleware.append(
    #        'debug_toolbar.middleware.DebugToolbarMiddleware',
    #    )
    required_middleware.extend([
        'askbot.middleware.view_log.ViewLogMiddleware',
    ])
    found_middleware = [x for x in django_settings.MIDDLEWARE
                        if x in required_middleware]
    if found_middleware != required_middleware:
        # either middleware is out of order or it's missing an item
        missing_middleware_set = set(required_middleware) - set(found_middleware)
        middleware_text = ''
        if missing_middleware_set:
            error_message = """\n\nPlease add the following middleware (listed after this message)
to the MIDDLEWARE variable in your site settings.py file.
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


    # middleware that was used in the past an now removed
    canceled_middleware = [
        'askbot.deps.recaptcha_django.middleware.ReCaptchaMiddleware'
    ]

    invalid_middleware = [x for x in canceled_middleware
                          if x in django_settings.MIDDLEWARE]
    if invalid_middleware:
        error_message = """\n\nPlease remove the following middleware entries from
the list of MIDDLEWARE in your settings.py - these are not used any more:\n\n"""
        middleware_text = format_as_text_tuple_entries(invalid_middleware)
        raise AskbotConfigError(error_message + middleware_text)

def try_import(module_name, pypi_package_name, show_requirements_message=True,
    extra_message=None):
    """tries importing a module and advises to install
    A corresponding Python package in the case import fails"""
    try:
        load_module(module_name)
    except ImportError as error:
        message = 'Error: ' + str(error)
        message += '\n\nPlease run: >pip install %s' % pypi_package_name
        if show_requirements_message:
            message += '\n\nTo install all the dependencies at once, type:'
            message += '\npip install -r askbot_requirements.txt'
        if extra_message:
            message += '\n' + extra_message
        message += '\n\nType ^C to quit.'
        raise AskbotConfigError(message)


def unparse_requirement(req):
    line = req.name
    if req.specs:
        specs = ['%s%s' % spec for spec in req.specs]
        line += ','.join(specs)
    if req.extras:
        line += ' [%s]' % ','.join(req.extras)
    return line

def assert_version_matches(mod_ver, op, spec_ver):
    """Asserts that version strings match the op"""
    if op == '==':
        assert mod_ver == spec_ver
    elif op == '>':
        assert mod_ver > spec_ver
    elif op == '<':
        assert mod_ver < spec_ver
    elif op == '<=':
        assert mod_ver <= spec_ver
    elif op == '>=':
        assert mod_ver >= spec_ver


def test_specs(req):
    """Check if the dependency described by `req` value
    is satisfied by the current python environment"""

    def map_int(data_list):
        """Returns list where strings are replaced
        with integers, where possible and where it is
        not possible to convert string into integer,
        the original string is kept."""
        result = list()
        for item in data_list:
            try:
                int_item = int(item)
                result.append(int_item)
            except:
                result.append(item)
        return result

    if not req.specs:
        return
    mod_ver = importlib.metadata.version(req.name)
    mod_ver = map_int(mod_ver.split('.'))
    try:
        for spec in req.specs:
            op = spec[0]
            spec_ver = map_int(spec[1].split('.'))
            if op not in ('==', '>', '<', '<=', '>='):
                raise ValueError('Unsupported pip dependency version operator %s' % op)

            try:
                assert_version_matches(mod_ver, op, spec_ver)
            except TypeError:
                mod_ver = [str(item) for item in mod_ver]
                spec_ver = [str(item) for item in spec_ver]
                assert_version_matches(mod_ver, op, spec_ver)

    except AssertionError:
        data = {
            'name': req.name,
            'need_spec': unparse_requirement(req),
            'mod_ver': '.'.join([str(v) for v in mod_ver])
        }
        message = """Unsupported version of module {name},
found version {mod_ver}, {need_spec} required.
please run:
> pip uninstall '{name}' && pip install '{need_spec}'""".format(**data)
        raise AskbotConfigError(message)


def get_req_name_from_spec(spec):
    spec = spec.replace('>', '=').replace('<', '=')
    bits = spec.split('=')
    return bits[0]


def find_mod_name(req_name):
    from askbot import REQUIREMENTS
    req2mod = dict([(get_req_name_from_spec(v), k)
                    for (k, v) in list(REQUIREMENTS.items())])
    return req2mod[req_name]


def test_modules():
    """tests presence of required modules"""
    from askbot import REQUIREMENTS
    # flatten requirements into file-like string
    req_text = '\n'.join(list(REQUIREMENTS.values()))
    import requirements
    parsed_requirements = requirements.parse(req_text)
    for req in parsed_requirements:
        pip_path = unparse_requirement(req)
        mod_name = find_mod_name(req.name)
        try_import(mod_name, pip_path)
        test_specs(req)


def test_postgres():
    """Checks for the postgres buggy driver, version 2.4.2"""
    if 'postgresql_psycopg2' in askbot.get_database_engine_name():
        import psycopg2
        version = psycopg2.__version__.split(' ')[0].split('.')
        if version == ['2', '4', '2']:
            raise AskbotConfigError(
                'Please install psycopg2 version 2.4.1,\n version 2.4.2 has a bug')
        elif version > ['2', '4', '2']:
            pass  # don't know what to do
        else:
            pass  # everythin is ok


def test_template_settings():
    """Sends a warning if you have an old style template
    loader that used to send a warning"""
    errors = list()
    try:
        jinja2_apps = getattr(django_settings, 'JINJA2_TEMPLATES')
    except AttributeError:
        errors.append("add to settings.py:\nJINJA2_TEMPLATES = ('captcha',)")
    else:
        if 'captcha' not in jinja2_apps:
            errors.append("add to JINJA2_TEMPLATES in settings.py\n    'captcha',")
    print_errors(errors)


def test_celery():
    """Tests celery settings
    todo: we are testing two things here
    that correct name is used for the setting
    and that a valid value is chosen
    """
    delay_time = getattr(django_settings, 'NOTIFICATION_DELAY_TIME', None)
    delay_setting_info = 'The delay is in seconds - used to throttle ' + \
        'instant notifications note that this delay will work only if ' + \
        'celery daemon is running Please search about ' + \
        '"celery daemon setup" for details'

    if delay_time is None:
        raise AskbotConfigError(
            '\nPlease add to your settings.py\n' +
            'NOTIFICATION_DELAY_TIME = 60*15\n' +
            delay_setting_info
        )
    elif not isinstance(delay_time, int):
        raise AskbotConfigError(
            '\nNOTIFICATION_DELAY_TIME setting must have a numeric value\n' + \
            delay_setting_info
        )


def test_compressor():
    """test settings for django compressor"""
    errors = list()

    js_filters = getattr(django_settings, 'COMPRESS_JS_FILTERS', [])
    if js_filters:
        errors.append(
            'Askbot does not yet support js minification, please add to your settings.py:\n'
            'COMPRESS_JS_FILTERS = []'
        )

    if 'compressor' not in django_settings.INSTALLED_APPS:
        errors.append(
            'add to the INSTALLED_APPS the following entry:\n'
            "    'compressor',"
        )
    print_errors(errors)


def test_media_url():
    """makes sure that setting `MEDIA_URL`
    has leading slash"""
    media_url = django_settings.MEDIA_URL
    # TODO: add proper url validation to MEDIA_URL setting
    if not (media_url.startswith('/') or media_url.startswith('http')):
        raise AskbotConfigError(
            "\nMEDIA_URL parameter must be a unique url on the site\n"
            "and must start with a slash - e.g. /media/ or http(s)://"
        )


class SettingsTester(object):
    """class to test contents of the settings.py file"""

    def __init__(self, requirements=None):
        """loads the settings module and inits some variables
        parameter `requirements` is a dictionary with keys
        as setting names and values - another dictionary, which
        has keys (optional, if noted and required otherwise)::

        * required_value (optional)
        * error_message
        """
        settings_module = os.environ['DJANGO_SETTINGS_MODULE']
        self.settings = load_module(settings_module)
        self.messages = list()
        self.requirements = requirements

    def test_setting(self, name, value=None, message=None,
                     test_for_absence=False, replace_hint=None):
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
            self.test_setting(setting_name, **self.requirements[setting_name])
        if self.messages:
            raise AskbotConfigError(
                '\n\nTime to do some maintenance of your settings.py:\n\n* ' +
                '\n\n* '.join(self.messages)
            )


def test_new_skins():
    """tests that there are no directories in the `askbot/skins`
    because we've moved skin files a few levels up"""
    askbot_root = askbot.get_install_directory()
    for item in os.listdir(os.path.join(askbot_root, 'skins')):
        if item == '__pycache__':
            continue
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
        # a simple check for the url
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

    extra_skins_dir = django_settings.ASKBOT_EXTRA_SKINS_DIR
    if extra_skins_dir is not None:
        if not os.path.isdir(extra_skins_dir):
            errors.append(
                'Directory specified with setting ASKBOT_EXTRA_SKINS_DIR '
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
            # static root is needed only for local storoge of
            # the static files
            raise AskbotConfigError(
                'Specify the static files directory '
                'with setting STATIC_ROOT'
            )

    if errors:
        errors.append(
            'Run command (after fixing the above errors)\n'
            '    python manage.py collectstatic\n'
        )

    required_finders = (
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'compressor.finders.CompressorFinder',
    )

    finders = django_settings.STATICFILES_FINDERS

    missing_finders = list()
    for finder in required_finders:
        if finder not in finders:
            missing_finders.append(finder)

    if missing_finders:
        errors.append(
            'Please make sure that the following items are \n' +
            'part of the STATICFILES_FINDERS tuple, create this tuple, if it is missing:\n' +
            '    "' + '",\n    "'.join(missing_finders) + '",\n'
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
    # TODO: maybe use the same steps to clean domain name
    csrf_cookie_domain = django_settings.CSRF_COOKIE_DOMAIN
    if csrf_cookie_domain is None or str(csrf_cookie_domain.strip()) == '':
        raise AskbotConfigError(
            'Please add settings CSRF_COOKIE_DOMAN and CSRF_COOKIE_NAME '
            'settings - both are required. '
            'CSRF_COOKIE_DOMAIN must match the domain name of yor site, '
            'without the http(s):// prefix and without the port number.\n'
            'Examples: \n'
            "    CSRF_COOKIE_DOMAIN = '127.0.0.1'\n"
            "    CSRF_COOKIE_DOMAIN = 'example.com'\n")
    if csrf_cookie_domain == 'localhost':
        raise AskbotConfigError(
            'Please do not use value "localhost" for the setting '
            'CSRF_COOKIE_DOMAIN\n'
            'instead use 127.0.0.1, a real IP '
            'address or domain name.'
            '\nThe value must match the network location you type in the '
            'web browser to reach your site.')
    if re.match(r'https?://', csrf_cookie_domain):
        raise AskbotConfigError(
            'please remove http(s):// prefix in the CSRF_COOKIE_DOMAIN '
            'setting'
        )
    if ':' in csrf_cookie_domain:
        raise AskbotConfigError(
            'Please do not use port number in the CSRF_COOKIE_DOMAIN '
            'setting')


def test_settings_for_test_runner():
    """makes sure that debug toolbar is disabled when running tests"""
    errors = list()
    if 'debug_toolbar' in django_settings.INSTALLED_APPS:
        errors.append(
            'When testing - remove debug_toolbar from INSTALLED_APPS')
    if 'debug_toolbar.middleware.DebugToolbarMiddleware' in \
        django_settings.MIDDLEWARE:
        errors.append(
            'When testing - remove debug_toolbar.middleware.DebugToolbarMiddleware '
            'from MIDDLEWARE')
    print_errors(errors)


def test_avatar():
    """if "avatar" is in the installed apps,
    checks that the module is actually installed"""
    if 'avatar' in django_settings.INSTALLED_APPS:
        try_import('avatar', 'django-avatar', show_requirements_message=False)


def test_haystack():
    if 'haystack' in django_settings.INSTALLED_APPS:
        try_import('haystack', 'django-haystack', show_requirements_message=False)
        if getattr(django_settings, 'ENABLE_HAYSTACK_SEARCH', False):
            errors = list()
            if not hasattr(django_settings, 'HAYSTACK_CONNECTIONS'):
                message = "Please HAYSTACK_CONNECTIONS to an appropriate value, value 'simple' can be used for basic testing sample:\n"
                message += """HAYSTACK_CONNECTIONS = {
                    'default': {
                    'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',

                    }"""
                errors.append(message)

            if askbot.is_multilingual():
                if not hasattr(django_settings, "HAYSTACK_ROUTERS"):
                    message = "Please add HAYSTACK_ROUTERS = ['askbot.search.haystack.routers.LanguageRouter',] to settings.py"
                    errors.append(message)
                elif 'askbot.search.haystack.routers.LanguageRouter' not in \
                        getattr(django_settings, 'HAYSTACK_ROUTERS'):
                    message = "'askbot.search.haystack.routers.LanguageRouter' to HAYSTACK_ROUTERS as first element in settings.py"
                    errors.append(message)

            if getattr(django_settings, 'HAYSTACK_SIGNAL_PROCESSOR',
                       '').endswith('AskbotCelerySignalProcessor'):
                try_import('celery_haystack', 'celery-haystack', show_requirements_message=False)

            footer = 'Please refer to haystack documentation at https://django-haystack.readthedocs.org/en/latest/settings.html'
            print_errors(errors, footer=footer)


def test_custom_user_profile_tab():
    setting_name = 'ASKBOT_CUSTOM_USER_PROFILE_TAB'
    tab_settings = getattr(django_settings, setting_name)
    if tab_settings:
        if not isinstance(tab_settings, dict):
            print("Setting %s must be a dictionary!!!" % setting_name)

        name = tab_settings.get('NAME', None)
        slug = tab_settings.get('SLUG', None)
        func_name = tab_settings.get('CONTEXT_GENERATOR', None)

        errors = list()
        if (name is None) or (not(isinstance(name, str))):
            errors.append("%s['NAME'] must be a string" % setting_name)
        if (slug is None) or (not(isinstance(slug, str))):
            errors.append("%s['SLUG'] must be an ASCII string" % setting_name)

        if urllib.parse.quote_plus(slug) != slug:
            errors.append(
                "%s['SLUG'] must be url safe, make it simple" % setting_name)

        try:
            func = load_function(func_name)
        except ImportError:
            errors.append("%s['CONTEXT_GENERATOR'] must be a dotted path to a function" % setting_name)
        header = 'Custom user profile tab is configured incorrectly in your settings.py file'
        footer = 'Please carefully read about adding a custom user profile tab.'
        print_errors(errors, header=header, footer=footer)


def test_longerusername():
    """tests proper installation of the "longerusername" app
    """
    errors = list()
    if 'longerusername' not in django_settings.INSTALLED_APPS:
        errors.append(
            "add 'longerusername', as the first item in the INSTALLED_APPS")
    else:
        index = django_settings.INSTALLED_APPS.index('longerusername')
        if index != 0:
            message = "move 'longerusername', to the beginning of INSTALLED_APPS"
            raise AskbotConfigError(message)

    if errors:
        errors.append('run "python manage.py migrate longerusername"')
        print_errors(errors)


def test_cache_backend():
    """prints a warning if cache backend is disabled or per-process"""
    # test that cache actually works
    errors = list()

    test_value = 'test value %s' % timezone.now()
    cache.set('askbot-cache-test', test_value)
    if cache.get('askbot-cache-test') != test_value:
        errors.append(
            'Cache server is unavailable.\n'
            'Check your CACHE... settings and make sure that '
            'the cache backend is working properly.')
    print_errors(errors)

    backend = django_settings.CACHES['default']['BACKEND']

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
    if 'askbot.deps.group_messaging' not in django_settings.INSTALLED_APPS:
        errors.append("add to the INSTALLED_APPS:\n'askbot.deps.group_messaging',")

    if 'group_messaging' in django_settings.INSTALLED_APPS:
        errors.append("remove from the INSTALLED_APPS:\n'group_messaging',")

    settings_sample = ("GROUP_MESSAGING = {\n"
    "    'BASE_URL_GETTER_FUNCTION': 'askbot.models.user_get_profile_url',\n"
    "    'BASE_URL_PARAMS': {'section': 'messages', 'sort': 'inbox'}\n"
    "}")

    settings = getattr(django_settings, 'GROUP_MESSAGING', {})
    if settings:
        url_params = settings.get('BASE_URL_PARAMS', {})
        have_wrong_params = not (
            url_params.get('section', None) == 'messages' and
            url_params.get('sort', None) == 'inbox')
        url_getter = settings.get('BASE_URL_GETTER_FUNCTION', None)
        if url_getter != 'askbot.models.user_get_profile_url' or have_wrong_params:
            errors.append(
                "make setting 'GROUP_MESSAGING to be exactly:\n" + settings_sample)

        url_params = settings.get('BASE_URL_PARAMS', None)
    else:
        errors.append('add this to your settings.py:\n' + settings_sample)

    if errors:
        print_errors(errors)


def test_secret_key():
    key = django_settings.SECRET_KEY
    if key.strip() == '':
        print_errors(['please create a random SECRET_KEY setting'])
    elif key == 'sdljdfjkldsflsdjkhsjkldgjlsdgfs s ':
        print_errors([
            'Please change your SECRET_KEY setting, the current is not secure'
        ])


def test_locale_middlewares():
    django_locale_middleware = 'django.middleware.locale.LocaleMiddleware'
    askbot_locale_middleware = 'askbot.middleware.locale.LocaleMiddleware'
    errors = list()

    if askbot.is_multilingual():
        if askbot_locale_middleware in django_settings.MIDDLEWARE:
            errors.append("Please remove '%s' from your MIDDLEWARE" % askbot_locale_middleware)
        if django_locale_middleware not in django_settings.MIDDLEWARE:
            errors.append("Please add '%s' to your MIDDLEWARE" % django_locale_middleware)

    print_errors(errors)


def test_recaptcha():
    errors = list()
    if 'captcha' not in django_settings.INSTALLED_APPS:
        errors.append("Please add to the INSTALLED_APPS:\n    'captcha',")

    try:
        nocaptcha = getattr(django_settings, 'NOCAPTCHA')
    except AttributeError:
        errors.append('Please add to settings.py:\nNOCAPTCHA = True')
    else:
        if not nocaptcha:
            errors.append('Please modify settings.py with:\nNOCAPTCHA = True')
    print_errors(errors)


def test_lang_mode():
    legacy_multilang = getattr(django_settings, 'ASKBOT_MULTILINGUAL', None)
    errors = list()
    if legacy_multilang is not None:
        if legacy_multilang:
            errors.append("""replace ASKBOT_MULTILINGUAL = True with either:
ASKBOT_LANGUAGE_MODE = 'url-lang' or
ASKBOT_LANGUAGE_MODE = 'user-lang'""")
        else:
            errors.append("""replace ASKBOT_MULTILINGUAL = True with either:
ASKBOT_LANGUAGE_MODE = 'single-lang' or just delete the setting""")
        print_errors(errors)

    mode = django_settings.ASKBOT_LANGUAGE_MODE
    if mode and mode not in ('single-lang', 'url-lang', 'user-lang'):
        errors.append("""ASKBOT_LANGUAGE_MODE must be one of:
'single-lang', 'url-lang', 'user-lang'""")

    if mode == 'url-lang':
        middleware = 'django.middleware.locale.LocaleMiddleware'
        if middleware not in django_settings.MIDDLEWARE:
            errors.append(
                "add 'django.middleware.locale.LocaleMiddleware' to your MIDDLEWARE "
                "if you want a multilingual setup"
            )

    trans_url = django_settings.ASKBOT_TRANSLATE_URL
    if mode in ('url-lang', 'user-lang') and trans_url == True:
        errors.append(
            'Please set ASKBOT_TRANSLATE_URL to False, the "True" option '
            'is currently not supported due to a bug in django'
        )

    print_errors(errors)


def test_messages_framework():
    if 'django.contrib.messages' not in django_settings.INSTALLED_APPS:
        errors = ('Add to the INSTALLED_APPS section of your settings.py:\n "django.contrib.messages"', )
        print_errors(errors)


def test_service_url_prefix():
    errors = list()
    prefix = django_settings.ASKBOT_SERVICE_URL_PREFIX
    message = 'Service url prefix must have > 1 letters and must end with /'
    if prefix:
        if len(prefix) == 1 or (not prefix.endswith('/')):
            print_errors((message,))


def test_versions():
    """inform of version incompatibilities, where possible"""
    errors = list()
    py_ver = sys.version_info

    dj_ver = django.VERSION
    upgrade_msg = 'About upgrades, please read http://askbot.org/doc/upgrade.html'
    if dj_ver < (3, 0) or dj_ver >= (5, 0):
        errors.append('This version of Askbot supports django 3.x - 4.x ' + upgrade_msg)
    elif py_ver[:3] < (3, 6, 0):
        errors.append('Askbot requires Python 3.6 - 3.12')
    elif py_ver[:3] >= (3, 13, 0):
        errors.append(
            'Askbot was not tested with Python > 3.12.x\n'
            'Try adding ASKBOT_SELF_TEST = False to the settings.py\n'
            'to test if your version of Python works and please let us know.'
        )

    print_errors(errors)


def run_startup_tests():
    """function that runs
    all startup tests, mainly checking settings config so far
    """
    # this is first because it gives good info on what to install
    try_import('requirements', 'requirements-parser')
    test_modules()

    if 'test' in sys.argv:
        extra_message="""Lamson modules are required for running tests
and for making posts by email"""
        try_import('django_lamson', 'django-lamson',
            show_requirements_message=False,
            extra_message=extra_message)

    # TODO: refactor this when another test arrives
    test_versions()
    test_lang_mode()
    test_askbot_url()
    test_avatar()
    test_cache_backend()
    test_celery()
    test_compressor()
    test_custom_user_profile_tab()
    #test_group_messaging()
    test_haystack()
    test_jinja2()
    #test_longerusername()
    test_new_skins()
    test_media_url()
    #test_postgres()
    test_messages_framework()
    test_middleware()
    test_locale_middlewares()
    #test_csrf_cookie_domain()
    test_recaptcha()
    test_secret_key()
    test_service_url_prefix()
    test_staticfiles()
    test_template_settings()
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
        'NOCAPTCHA': {
            'value': True,
            'message': 'Please add: NOCAPTCHA = True'
        },
    })
    settings_tester.run()
    if 'manage.py test' in ' '.join(sys.argv):
        test_settings_for_test_runner()


def run():
    try:
        if django_settings.ASKBOT_SELF_TEST:
            run_startup_tests()
    except AskbotConfigError as error:
        print(error)
        sys.exit(1)
    # close DB and cache connections to prevent issues in prefork mode
    connection.close()
    if hasattr(cache, 'close'):
        cache.close()
