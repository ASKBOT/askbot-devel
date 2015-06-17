import os.path
from django.template.loader import BaseLoader
from django.template import RequestContext
from django.template import TemplateDoesNotExist
from django.http import HttpResponse
from django.utils import translation
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from coffin.common import CoffinEnvironment
from jinja2 import loaders as jinja_loaders
from jinja2.exceptions import TemplateNotFound
from jinja2.utils import open_if_exists
from askbot.conf import settings as askbot_settings
from askbot.skins import utils
from askbot.utils.translation import get_language, HAS_ASKBOT_LOCALE_MIDDLEWARE

from coffin import template
template.add_to_builtins('askbot.templatetags.extra_filters_jinja')

#module for skinning askbot
#via ASKBOT_DEFAULT_SKIN configureation variable (not django setting)

#note - Django template loaders use method django.utils._os.safe_join
#to work on unicode file paths
#here it is ignored because it is assumed that we won't use unicode paths
ASKBOT_SKIN_COLLECTION_DIR = os.path.dirname(__file__)

class MultilingualEnvironment(CoffinEnvironment):
    def set_language(self, language_code):
        """hooks up translation objects from django to jinja2
        environment.
        note: not so sure about thread safety here
        """
        trans = translation.trans_real.translation(language_code)
        self.install_gettext_translations(trans)


JINJA2_TEMPLATES_HELP_TEXT = """JINJA2_TEMPLATES setting must be tuple
where the items can be either of the two forms:
* '<app name>' (string)
* tuple ('<app name>', ('<dir1>', '<dir2>', ...))
  of app name and a tuple of directories.

For example:

JINJA2_TEMPLATES = (
    'askbot',
    ('askbot_audit', (
            '/home/joe/templates',
            '/home/joe/base_templates',
        )
    )
)

Above, for the app 'askbot' the templates will be loaded
only from the app directory: askbot/templates

For the second app 'askbot_audit' templates will be loaded from
three locations in this order:
1) /home/joe/templates
2) /home/joe/templates/base_templates
3) and finally - from the app directory:
   askbot_audit/templates
"""


class AppDirectoryEnvironment(MultilingualEnvironment):
    """Jinja2 environment which loads the templates as the
    django's app directories loader

    Directory locations depend on the JINJA2_TEMPLATES setting.
    """

    def get_app_setup_info(self, setup_item):
        if isinstance(setup_item, basestring):
            return setup_item, list()
        elif isinstance(setup_item, (list, tuple)):
            dir_list = setup_item[1]
            if len(setup_item) != 2 or not isinstance(dir_list, (list, tuple)):
                raise ImproperlyConfigured(JINJA2_TEMPLATES_HELP_TEXT)
            return setup_item, dir_list


    def get_app_template_dir(self, app_name):
        """returns path to directory `templates` within the app directory
        """
        assert(app_name in django_settings.INSTALLED_APPS)
        from django.utils.importlib import import_module
        try:
            mod = import_module(app_name)
        except ImportError as e:
            raise ImproperlyConfigured('ImportError %s: %s' % (app_name, e.args[0]))
        return os.path.join(os.path.dirname(mod.__file__), 'templates')

    def get_all_template_dirs(self):
        template_dirs = list()
        for app_setup_item in django_settings.JINJA2_TEMPLATES:

            app_name, app_dirs = self.get_app_setup_info(app_setup_item)

            #append custom app dirs first
            template_dirs.extend(app_dirs)

            #after that append the default app templates dir
            app_template_dir = self.get_app_template_dir(app_name)
            template_dirs.append(app_template_dir)

        return template_dirs

    def _get_loaders(self):
        template_dirs = self.get_all_template_dirs()
        return [jinja_loaders.FileSystemLoader(template_dirs)]


class SkinEnvironment(MultilingualEnvironment):
    """Jinja template environment
    that loads templates from askbot skins
    """

    def __init__(self, *args, **kwargs):
        """save the skin path and initialize the
        Coffin Environment
        """
        self.skin = kwargs.pop('skin')
        super(SkinEnvironment, self).__init__(*args, **kwargs)

    def _get_loaders(self):
        """this method is not used
        over-ridden function _get_loaders that creates
        the loader for the skin templates
        """
        loaders = list()
        skin_dirs = utils.get_available_skins(selected = self.skin).values()
        template_dirs = [os.path.join(skin_dir, 'templates') for skin_dir in skin_dirs]
        loaders.append(jinja_loaders.FileSystemLoader(template_dirs))
        return loaders


def load_skins(language_code):
    skins = dict()
    for skin_name in utils.get_available_skins():
        skin_code = skin_name + '-' + language_code
        skins[skin_code] = SkinEnvironment(
                                skin = skin_name,
                                extensions=['jinja2.ext.i18n',],
                                globals={'settings': askbot_settings}
                            )
        skins[skin_code].set_language(language_code)
        #from askbot.templatetags import extra_filters_jinja as filters
        #skins[skin_name].filters['media'] = filters.media
    return skins

def get_app_dir_env(language_code):
    env = AppDirectoryEnvironment(
                            extensions=['jinja2.ext.i18n',],
                            globals={'settings': askbot_settings}
                        )
    env.set_language(language_code)
    return env

LOADERS = django_settings.TEMPLATE_LOADERS
SKINS = dict()
if 'askbot.skins.loaders.Loader' in LOADERS:
    if getattr(django_settings, 'ASKBOT_MULTILINGUAL', False) or\
            HAS_ASKBOT_LOCALE_MIDDLEWARE:
        for lang in dict(django_settings.LANGUAGES).keys():
            SKINS.update(load_skins(lang))
    else:
        SKINS = load_skins(django_settings.LANGUAGE_CODE)

APP_DIR_ENVS = dict()
if 'askbot.skins.loaders.JinjaAppDirectoryLoader' in LOADERS:
    if getattr(django_settings, 'ASKBOT_MULTILINGUAL', False) or\
            HAS_ASKBOT_LOCALE_MIDDLEWARE:
        for lang in dict(django_settings.LANGUAGES).keys():
            APP_DIR_ENVS[lang] = get_app_dir_env(lang)
    else:
        lang = django_settings.LANGUAGE_CODE
        APP_DIR_ENVS[lang] = get_app_dir_env(lang)

def get_skin():
    """retreives the skin environment
    for a given request (request var is not used at this time)"""
    skin_name = askbot_settings.ASKBOT_DEFAULT_SKIN
    skin_name += '-' + get_language()

    try:
        return SKINS[skin_name]
    except KeyError:
        msg_fmt = 'skin "%s" not found, check value of "ASKBOT_EXTRA_SKINS_DIR"'
        raise ImproperlyConfigured(msg_fmt % skin_name)

def get_askbot_template(template):
    """
    retreives template for the skin
    request variable will be used in the future to set
    template according to the user preference or admins preference

    request variable is used to localize the skin if possible
    """
    skin = get_skin()
    return skin.get_template(template)

def render_into_skin_as_string(template, data, request):
    context = RequestContext(request, data)
    template = get_askbot_template(template)
    return template.render(context)

def render_text_into_skin(text, data, request):
    context = RequestContext(request, data)
    skin = get_skin()
    template = skin.from_string(text)
    return template.render(context)

class Loader(BaseLoader):
    """skins template loader for Django > 1.2
    todo: verify that this actually follows django's convention correctly
    """
    is_usable = True

    def load_template(self, template_name, template_dirs=None):
        try:
            return get_askbot_template(template_name), template_name
        except TemplateNotFound:
            raise TemplateDoesNotExist

class JinjaAppDirectoryLoader(BaseLoader):
    """Optional Jinja2 template loader to support apps using
    Jinja2 templates.

    The loader must be placed before the django template loaders
    in the `TEMPLATE_LOADERS` setting and two more conditions
    must be met:

    1) Loaders requires to explicitly mark apps as using Jinja2
    templates, via the setting `JINJA2_TEMPLATES` (formatted
    the same way as the `INSTALLED_APPS` setting).

    2) Templates must be within the app directory's templates/appname/
    directory. For example, template XYZ_home.html must be in directory
    XYZ_app/templates/XYZ_app/, where the root directory
    is the app module directory itself.
    """
    is_usable = True

    def load_template(self, template_name, template_dirs=None):
        bits = template_name.split(os.path.sep)

        #setting JINJA2_TEMPLATES is list of apps using Jinja2 templates
        jinja2_apps = getattr(django_settings, 'JINJA2_TEMPLATES', None)
        if jinja2_apps != None and bits[0] not in jinja2_apps:
            raise TemplateDoesNotExist

        try:
            env = APP_DIR_ENVS[get_language()]
            return env.get_template(template_name), template_name
        except TemplateNotFound:
            raise TemplateDoesNotExist
