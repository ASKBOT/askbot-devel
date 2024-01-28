from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
try:
    from importlib import import_module
except ImportError:
    from django.utils.importlib import import_module
from django.utils.translation import get_language as _get_language

from haystack.constants import DEFAULT_ALIAS


DEFAULT_BASE_INDEX = 'askbot.search.haystack.base.BaseIndex'


def get_base_index():
    index_string = getattr(settings, 'ASKBOT_HAYSTACK_INDEX_BASE_CLASS', DEFAULT_BASE_INDEX)

    try:
        BaseClass = get_callable(index_string)
    except (AttributeError, ImportError) as error:
        raise ImproperlyConfigured('ASKBOT_HAYSTACK_INDEX_BASE_CLASS: %s' % (str(error)))

    required_fields = ['text']

    if not all(field in BaseClass.fields for field in required_fields):
        raise ImproperlyConfigured(f'ASKBOT_HAYSTACK_INDEX_BASE_CLASS: {index_string} must contain at least these fields: {required_fields}')
    return BaseClass


def get_callable(string_or_callable):
    """
    If given a callable then it returns it, otherwise it resolves the path
    and returns an object.
    """
    if callable(string_or_callable):
        return string_or_callable
    else:
        module_name, object_name = string_or_callable.rsplit('.', 1)
        module = import_module(module_name)
        return getattr(module, object_name)


def get_language():
    return _get_language()[:2]


def get_connection_prefix():
    return getattr(settings, 'ASKBOT_HAYSTACK_CONNECTION_PREFIX', 'default')


def alias_from_language(language):
    if language == settings.LANGUAGE_CODE:
        # if it's the default language, then we assume we're dealing with "default" connection.
        return DEFAULT_ALIAS

    connection_prefix = get_connection_prefix()

    if connection_prefix:
        connection = f'{connection_prefix}_{language}'
    else:
        connection = language
    return connection


def language_from_alias(alias):
    if alias == DEFAULT_ALIAS:
        language = settings.LANGUAGE_CODE
    else:
        language = alias.split('_')[-1]
    return language
