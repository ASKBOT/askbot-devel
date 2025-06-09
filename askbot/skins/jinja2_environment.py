# The reason for this module to be is the factory function just before EOF

# It appears that the orginal Askbot code keeps one jinja2.Environment for
# each skin and known language around and picks the correct environment(TM) on
# every call to from_string, get_template and load_template. I have not the
# faintest idea if that is a wise thing to do. For now we will simply mimic
# this behaviour in factory()

from copy import deepcopy
from django.conf import settings as django_settings

import askbot
from askbot import const
from askbot.conf import settings as askbot_settings
from askbot.skins import utils
from askbot.skins.askbot_environments import SkinEnvironment
from askbot.templatetags.textwrap import TextWrapExtension
from askbot.templatetags.premail import PremailerExtension
from askbot.utils.functions import encode_jwt
from askbot.utils.translation import HAS_ASKBOT_LOCALE_MIDDLEWARE
from askbot.utils.translation import get_language

# since we dropped Coffin we cannot add filters to jinja like the original code
# did. The people who brought us Coffin also brought us django-jinja which
# now does the magic.
# For now, we do not want to root django_jinja as deeply into askbot as Coffin
# used to be.

from django_jinja import library as Library
from django_jinja.builtins import DEFAULT_EXTENSIONS
import django_jinja.backend

# django_jinja is also past its time, but we will keep it around for a
# little longer. so we adapt its default behaviour to slowly but steadly
# release Askbot

if 'jinja2.ext.i18n' not in DEFAULT_EXTENSIONS:
    DEFAULT_EXTENSIONS.append('jinja2.ext.i18n')

DEFAULT_EXTENSIONS.append(TextWrapExtension)
DEFAULT_EXTENSIONS.append(PremailerExtension)

try:
    DEFAULT_EXTENSIONS.remove('django_jinja.builtins.extensions.CsrfExtension')
except ValueError:
    pass

# this looks like a hack because it is one. We keep it as a separate
# function to remind us that it ultimately must go
def load_templatetags():
  sib_zero  = list(SkinEnvironment.siblings.keys())[0]
  dummy = django_jinja.backend.Jinja2.__new__(django_jinja.backend.Jinja2)
  dummy.env = SkinEnvironment.siblings[sib_zero]

  # this loads the templatetags modules
  django_jinja.backend.Jinja2._initialize_thirdparty(dummy)

  for sibling in SkinEnvironment.siblings:
    Library._update_env(SkinEnvironment.siblings[sibling])


# Django calls this function, because we provide it (i.e. its path) in
# settings.py as ["OPTIONS"]["environment"] parameter to Django's
# jinja2.Jinja2 template backend.
#
# This is the one entrypoint where we impose our thoughts and feelings about
# templates, skins and whatnots on the framework.
def factory(**options):
    # JINJA2_EXTENSIONS was a thing in Coffin. We keep it around because it
    # may be used in Askbot. Should think about deprecating its use.
    options["extensions"] = DEFAULT_EXTENSIONS \
                          + list(django_settings.JINJA2_EXTENSIONS)
    askbot_globals = {'settings': askbot_settings,
                      'hasattr' : hasattr,
                      'ADMIN_TAGS_CATEGORY_ROOT': const.ADMIN_TAGS_CATEGORY_ROOT,
                      'encode_jwt': encode_jwt}

    mother_of_all_loaders = options.pop('loader')

    skins = utils.get_available_skins()
    if askbot.is_multilingual() or HAS_ASKBOT_LOCALE_MIDDLEWARE:
        languages = list(dict(django_settings.LANGUAGES).keys())
    else:
        languages = [ django_settings.LANGUAGE_CODE ]

    # create an environment for each skin and language we might serve
    # Jinja2 Environments know a concept called "overlays" which cries for
    # consideration here. It may greatly simplify loading templatetags ...
    all_combinations = [ (name,lang) for name in skins for lang in languages ]
    for name, lang in all_combinations:
        skin_basedir = utils.get_path_to_skin(name)
        options["skin"] = name
        options["language_code"] = lang
        options['loader'] = deepcopy(mother_of_all_loaders)
        options['loader'].searchpath = [ f'{skin_basedir}/jinja2' ] + options['loader'].searchpath
        env = SkinEnvironment(**options)
        env.globals.update(askbot_globals)
        env.set_language(lang)

    load_templatetags()

    # give Django what it asked for
    default_sibling = SkinEnvironment.build_sibling_key([
        askbot_settings.ASKBOT_DEFAULT_SKIN,
        get_language()
    ])

    return SkinEnvironment.siblings[default_sibling]
