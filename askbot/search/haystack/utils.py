# -*- coding: utf-8 -*-
from lxml.etree import ParserError
from lxml.html.clean import Cleaner as LxmlCleaner

from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.utils import six
from django.utils.importlib import import_module
from django.utils.html import strip_tags as _strip_tags
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
        raise ImproperlyConfigured('ASKBOT_HAYSTACK_INDEX_BASE_CLASS: %s must contain at least these fields: %s' % (index_string, required_fields))
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
        connection = '{0}_{1}'.format(connection_prefix, language)
    else:
        connection = language
    return connection


def language_from_alias(alias):
    if alias == DEFAULT_ALIAS:
        language = settings.LANGUAGE_CODE
    else:
        language = alias.split('_')[-1]
    return language


def strip_tags(value):
    """
    Returns the given HTML with all tags stripped.
    We use lxml to strip all js tags and then hand the result to django's
    strip tags. If value isn't valid, just return value since there is
    no tags to strip.
    """
    # borrowed from aldryn-search

    if isinstance(value, six.string_types):
        value = value.strip()

        if not value:
            return

        try:
            partial_strip = LxmlCleaner().clean_html(value)
        except ParserError:
            # error could occur because of empty comment
            partial_strip = value
        value = _strip_tags(partial_strip)
        return value.strip()  # clean cases we have <div>\n\n</div>
    return value
