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

class SkinEnvironment(CoffinEnvironment):
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

    def set_language(self, language_code):
        """hooks up translation objects from django to jinja2
        environment.
        note: not so sure about thread safety here
        """
        trans = translation.trans_real.translation(language_code)
        self.install_gettext_translations(trans)

    def get_extra_css_link(self):
        """returns either the link tag (to be inserted in the html head element)
        or empty string - depending on the existence of file
        SKIN_PATH/media/style/extra.css
        """
        url = None

        if django_settings.ASKBOT_CSS_DEVEL is True:
            url = utils.get_media_url('style/extra.less', ignore_missing=True)
            rel = "stylesheet/less"
            link_type = "text/less"

        #second try - if there is no extra.less in devel mode - try css
        if url is None:
            url = utils.get_media_url('style/extra.css', ignore_missing=True)
            rel = "stylesheet"
            link_type = "text/css"

        if url is not None:
            return '<link href="%s" rel="%s" type="%s" />' % \
                (url, rel, link_type)

        return ''

def load_skins(language_code):
    skins = dict()
    for skin_name in utils.get_available_skins():
        skin_code = skin_name + '-' + language_code
        skins[skin_code] = SkinEnvironment(
                                skin = skin_name,
                                extensions=['jinja2.ext.i18n',]
                            )
        skins[skin_code].set_language(language_code)
        #from askbot.templatetags import extra_filters_jinja as filters
        #skins[skin_name].filters['media'] = filters.media
    return skins

SKINS = dict()
if getattr(django_settings, 'ASKBOT_MULTILINGUAL', False) or\
        HAS_ASKBOT_LOCALE_MIDDLEWARE:
    for lang in dict(django_settings.LANGUAGES).keys():
        SKINS.update(load_skins(lang))
else:
    SKINS = load_skins(django_settings.LANGUAGE_CODE)

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
    def load_template(self, template_name, template_dirs = None):
        try:
            return get_askbot_template(template_name), template_name
        except TemplateNotFound:
            raise TemplateDoesNotExist
