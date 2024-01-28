from django.conf import settings
from django.apps import apps

from haystack import indexes

from .utils import get_base_index

ENABLE_HAYSTACK_SEARCH = getattr(settings, 'ENABLE_HAYSTACK_SEARCH', False)


class ThreadIndex(get_base_index()):
    haystack_use_for_indexing = ENABLE_HAYSTACK_SEARCH

    title = indexes.CharField()
    tags = indexes.MultiValueField()

    def get_language(self, obj):
        return obj.language_code

    def get_model(self):
        return apps.get_model('askbot', 'Thread')

    def get_index_kwargs(self, language):
        kwargs = {'deleted': False}

        if self.i18n_enabled:
            kwargs['language_code__startswith'] = language
        return kwargs

    def prepare_tags(self, obj):
        return [tag.name for tag in obj.tags.all()]

    def should_update(self, instance, **kwargs):
        # Update only if thread is not deleted
        return not instance.deleted


class UserIndex(get_base_index()):

    haystack_use_for_indexing = ENABLE_HAYSTACK_SEARCH

    def get_model(self):
        return apps.get_model('auth', 'User')
