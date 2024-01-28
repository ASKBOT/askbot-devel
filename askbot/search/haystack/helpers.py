from haystack import connections
from haystack.exceptions import NotHandled
from haystack.query import SearchQuerySet

from ...models import Thread, User
from .utils import alias_from_language, get_language


def search(query, language=None):
    language = language or get_language()
    connection = alias_from_language(language)
    search_qs = SearchQuerySet(connection).filter(content=query)
    return search_qs


def search_model(query, model_class, language=None):
    language = language or get_language()
    connection = alias_from_language(language)
    index = get_index_from_model(model_class, language=language)
    search_qs = search(query, language=language).models(model_class)
    model_ids = (result.pk for result in search_qs)
    return index.index_queryset(using=connection).filter(pk__in=model_ids)


def get_index_from_model(model_class, language=None):
    language = language or get_language()
    alias = alias_from_language(language)
    unified_index = connections[alias].get_unified_index()

    try:
        model_index = unified_index.get_index(model_class)
    except NotHandled:
        model_index = None
    return model_index


def get_threads_from_query(query, language=None):
    return search_model(query, model_class=Thread, language=language)


def get_users_from_query(query, language=None):
    return search_model(query, model_class=User, language=language)
