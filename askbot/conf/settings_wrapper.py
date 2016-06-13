"""
Definition of a Singleton wrapper class for askbot.deps.livesettings
with interface similar to django.conf.settings
that is each setting has unique key and is accessible
via dotted lookup.

for example to lookup value of setting BLAH you would do

from askbot.conf import settings as askbot_settings

askbot_settings.BLAH

NOTE that at the moment there is distinction between settings
(django settings) and askbot_settings (forum.deps.livesettings)

the value will be taken from askbot.deps.livesettings database or cache
note that during compilation phase database is not accessible
for the most part, so actual values are reliably available only
at run time

askbot.deps.livesettings is a module developed for satchmo project
"""
import askbot
import logging
from django.conf import settings as django_settings
from django.core.cache import cache
from django.contrib.sites.models import Site
from django.utils.encoding import force_unicode
from django.utils.functional import lazy
from django.utils.translation import get_language
from django.utils.translation import string_concat
from django.utils.translation import ugettext_lazy as _
from askbot.deps.livesettings import SortedDotDict, config_register
from askbot.deps.livesettings.functions import config_get
from askbot.deps.livesettings import signals
from askbot.utils.functions import format_setting_name

def assert_setting_info_correct(info):
    assert isinstance(info, tuple), u'must be tuple, %s found' % unicode(info)
    assert len(info) in (3, 4), 'setting tuple must have three or four elements'
    assert isinstance(info[0], str)
    assert isinstance(info[1], str)
    assert isinstance(info[2], bool)


class ConfigSettings(object):
    """A very simple Singleton wrapper for settings
    a limitation is that all settings names using this class
    must be distinct, even though they might belong
    to different settings groups
    """
    __instance = None
    __group_map = {}

    def __init__(self):
        """assigns SortedDotDict to self.__instance if not set"""
        if ConfigSettings.__instance == None:
            ConfigSettings.__instance = SortedDotDict()
        self.__dict__['_ConfigSettings__instance'] = ConfigSettings.__instance
        self.__ordering_index = {}

    def __getattr__(self, key):
        """value lookup returns the actual value of setting
        not the object - this way only very minimal modifications
        will be required in code to convert an app
        depending on django.conf.settings to askbot.deps.livesettings
        """
        hardcoded_setting = getattr(django_settings, 'ASKBOT_' + key, None)
        if hardcoded_setting is None:
            return getattr(self.__instance, key).value
        else:
            return hardcoded_setting

    def get_default(self, key):
        """return the defalut value for the setting"""
        return getattr(self.__instance, key).default

    def get_description(self, key):
        """returns descriptive title of the setting"""
        return unicode(getattr(self.__instance, key).description)

    def reset(self, key):
        """returns setting to the default value"""
        self.update(key, self.get_default(key))

    def update(self, key, value, language_code=None):
        try:
            setting = config_get(self.__group_map[key], key)
            if setting.localized:
                lang = language_code or get_language()
            else:
                lang = None
            setting.update(value, lang)

        except:
            from askbot.deps.livesettings.models import Setting
            lang_postfix = '_' + get_language().upper()
            #first try localized setting
            try:
                setting = Setting.objects.get(key=key + lang_postfix)
            except Setting.DoesNotExist:
                setting = Setting.objects.get(key=key)

            setting.value = value
            setting.save()
        #self.prime_cache()

    def register(self, value):
        """registers the setting
        value must be a subclass of askbot.deps.livesettings.Value
        """
        key = value.key
        group_key = value.group.key

        ordering = self.__ordering_index.get(group_key, None)
        if ordering:
            ordering += 1
            value.ordering = ordering
        else:
            ordering = 1
            value.ordering = ordering
        self.__ordering_index[group_key] = ordering

        if key not in self.__instance:
            self.__instance[key] = config_register(value)
            self.__group_map[key] = group_key

    def get_setting_url(self, data):
        from askbot.utils.html import internal_link #not site_link
        group_name = data[0]
        setting_name = data[1]

        link = internal_link(
            'group_settings',
            setting_name, #todo: better use description
            kwargs={'group': group_name},
            anchor='id_%s__%s__%s' % (group_name, setting_name, get_language())
        )
        if len(data) == 4:
            return force_unicode(string_concat(link, ' (', data[3], ')'))
        return link


    def get_related_settings_info(self, *requirements):
        """returns a translated string explaining which
        settings are required,
        the parameters are tuples of triples:
            (<group name>, <setting name>, <required or noot boolean>)
        """
        def _func():
            #error checking
            map(assert_setting_info_correct, requirements)
            required = list()
            optional = list()
            for req in requirements:
                if req[2] == True:
                    required.append(req)
                else:
                    optional.append(req)

            required_links = map(lambda v: self.get_setting_url(v), required)
            optional_links = map(lambda v: self.get_setting_url(v), optional)
                
            if required_links and optional_links:
                return _(
                    'There are required related settings: '
                    '%(required)s and some optional: '
                    '%(optional)s.'
                ) % {
                    'required': ', '.join(required_links),
                    'optional': ', '.join(optional_links)
                }
            elif required_links:
                return _(
                    'There are required related settings: %(required)s.'
                ) % {
                    'required': ', '.join(required_links)
                }
            elif optional_links:
                return _(
                    'There are optional related settings: %(optional)s.'
                ) % {
                    'optional': ', '.join(optional_links)
                }
            else:
                return ''
        return lazy(_func, unicode)()

    def as_dict(self):
        cache_key = get_bulk_cache_key()
        return cache.get(cache_key) or self.prime_cache(cache_key)

    @classmethod
    def precache_all_values(cls):
        from askbot.deps.livesettings.models import Setting, LongSetting
        from django.contrib.sites.models import Site
        settings = Setting.objects.filter(site=Site.objects.get_current())
        settings = settings.select_related('site')
        keys = set()
        for setting in settings:
            setting.cache_set()
            keys.add(setting.key)

        settings = LongSetting.objects.filter(site=Site.objects.get_current())
        settings = settings.select_related('site')
        for setting in settings:
            setting.cache_set()
            keys.add(setting.key)

        return keys

    @classmethod
    def prime_cache(cls, cache_key, **kwargs):
        """reload all settings into cache as dictionary
        """
        db_keys = cls.precache_all_values()

        out = dict()
        for key in cls.__instance.keys():
            hardcoded_setting = getattr(django_settings, 'ASKBOT_' + key, None)
            if hardcoded_setting is not None:
                value = hardcoded_setting
            else:
                setting_value = cls.__instance[key]
                if setting_value.localized:
                    db_key = '{}_{}'.format(key, format_setting_name(get_language()))
                else:   
                    db_key = key

                if db_key in db_keys:
                    value = setting_value.value
                else:
                    if hasattr(setting_value, 'default'):
                        value = setting_value.default
                    else:
                        logging.critical('setting %s lacks default value', key)
                        value = setting_value.value
                    db_setting = setting_value.make_setting_with_value(value)
                    db_setting.site = Site.objects.get_current()
                    db_setting.cache_set()

            out[key] = value
        cache.set(cache_key, out)

        return out


def get_bulk_cache_key(lang=None):
    from askbot.utils.translation import get_language
    return 'askbot-settings-' + (lang or get_language())


def update_cached_value(key, value, language_code=None):
    cache_key = get_bulk_cache_key(language_code or get_language())
    settings_dict = cache.get(cache_key)
    if settings_dict:
        settings_dict[key] = value
        cache.set(cache_key, settings_dict)

def cached_value_update_handler(setting=None, new_value=None, language_code=None, *args, **kwargs):
    key=setting.key
    if setting.localized == False and askbot.is_multilingual():
        languages = dict(django_settings.LANGUAGES).keys()
        for lang in languages:
            update_cached_value(key, new_value, lang)
    else:
        update_cached_value(key, new_value, language_code)

signals.configuration_value_changed.connect(
    cached_value_update_handler,
    dispatch_uid='update_cached_value_upon_config_change'
)
#settings instance to be used elsewhere in the project
settings = ConfigSettings()
