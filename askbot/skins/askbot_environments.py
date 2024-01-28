# We copy and therefore duplicate a lot of code from other askbot.skins
# modules and rid ourselves of Coffin along the way.

# It appears that the orginal Askbot code keeps one jinja2.Environment for
# each skin and known language around and picks the correct environment(TM) on
# every call to from_string, get_template and load_template. I have not the
# faintest idea if that is a wise thing to do. For now we will simply mimic
# this behaviour.

from jinja2 import Environment

from django.utils import translation
from django.core.exceptions import ImproperlyConfigured

from askbot.conf import settings as askbot_settings
from askbot.utils.translation import get_language

# probably just copy/paste this file contents here
import askbot.skins.template_backends

class MultilingualEnvironment(Environment):
    def __init__(self, *args, **kwargs):
        lang_code = kwargs.pop('language_code', None) # atm I don't see this ever becoming None
        super().__init__(*args, **kwargs)
        # The following caused problems before. Reverting to call set_language() explicitly
        # if lang_code is not None:
        #     self.set_language(lang_code)

    def set_language(self, language_code):
        """hooks up translation objects from django to jinja2
        environment.
        note: not so sure about thread safety here
        """
        self._language_code = language_code
        trans = translation.trans_real.translation(language_code)
        self.install_gettext_translations(trans)

class SkinEnvironment(MultilingualEnvironment):
    """Jinja template environment
    that loads templates from askbot skins
    """

    # we use this over the SKINS variable in the original code
    siblings = dict()

    def __init__(self, *args, **kwargs):
        """save the skin path and initialize the
        Jinja2 Environment
        """
        skin_name = kwargs.pop('skin')
        lang_code = kwargs.get('language_code', None) # atm I don't see this ever becoming None

        this_sibling_key = [ skin_name ]
        if lang_code is not None:
            this_sibling_key.append(lang_code)

        key = self.build_sibling_key(this_sibling_key)
        self.__class__.siblings[key] = self

        super().__init__(*args, **kwargs)

    @classmethod
    def build_sibling_key(cls, parts):
        return "-".join(parts)

    @classmethod
    def get_skin(cls):
        """retreives the skin environment
        for a given request (request var is not used at this time)"""
        key = cls.build_sibling_key([askbot_settings.ASKBOT_DEFAULT_SKIN,
                                     get_language()])
        try:
            return cls.siblings[key]
        except KeyError:
            msg_fmt = 'skin "%s" not found, check value of "ASKBOT_EXTRA_SKINS_DIR"'
            raise ImproperlyConfigured(msg_fmt % askbot_settings.ASKBOT_DEFAULT_SKIN)

    # the Jinja2 backend will use these
    # Making these classmethods seems sensible as these first pick an
    # environment instance and then have them do the work, but there is no
    # real merrit in it
    @classmethod
    def from_string(cls, template_code):
        env = cls.get_skin()
        return super(SkinEnvironment,env).from_string(template_code)

    @classmethod
    def get_template(cls, template_name, parent=None, globals=None):
        env = cls.get_skin()
        return super(SkinEnvironment,env).get_template(template_name, parent, globals)
