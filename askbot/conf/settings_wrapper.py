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
from django.core.cache import cache
from askbot.deps.livesettings import SortedDotDict, config_register
from askbot.deps.livesettings.functions import config_get
from askbot.deps.livesettings import signals

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
        return getattr(self.__instance, key).value

    def get_default(self, key):
        """return the defalut value for the setting"""
        return getattr(self.__instance, key).default

    def reset(self, key):
        """returns setting to the default value"""
        self.update(key, self.get_default(key))

    def update(self, key, value):
        setting = config_get(self.__group_map[key], key) 
        setting.update(value)

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

        if key in self.__instance:
            raise Exception('setting %s is already registered' % key)
        else:
            self.__instance[key] = config_register(value)
            self.__group_map[key] = group_key

    def as_dict(self):
        settings = cache.get('askbot-livesettings')
        if settings:
            return settings
        else:
            self.prime_cache()
            return cache.get('askbot-livesettings')

    @classmethod
    def prime_cache(cls, **kwargs):
        """reload all settings into cache as dictionary
        """
        out = dict()
        for key in cls.__instance.keys():
            #todo: this is odd that I could not use self.__instance.items() mapping here
            out[key] = cls.__instance[key].value
        cache.set('askbot-livesettings', out)


signals.configuration_value_changed.connect(ConfigSettings.prime_cache)
#settings instance to be used elsewhere in the project
settings = ConfigSettings()
