import askbot
from django.conf import settings
from django.utils.translation import override

from haystack import indexes

from .utils import language_from_alias


class BaseIndex(indexes.SearchIndex):

    i18n_enabled = askbot.is_multilingual()

    text = indexes.CharField(document=True, use_template=True)

    def _get_backend(self, using):
        """
        We set the backend alias to be able to determine language in multilanguage setup.
        """
        self._backend_alias = using
        return super()._get_backend(using)

    def get_language(self, obj):
        return None

    def get_default_language(self, using):
        """
        When using multiple languages, this allows us to specify a fallback based on the
        backend being used.
        """
        return language_from_alias(using) or settings.LANGUAGE_CODE

    def get_current_language(self, using=None, obj=None):
        """
        Helper method bound to ALWAYS return a language.
        When obj is not None, this calls self.get_language to try and get a language from obj,
        this is useful when the object itself defines it's language in a "language" field.
        If no language was found or obj is None, then we call self.get_default_language to try and get a fallback language.
        """
        language = self.get_language(obj) if obj else None
        return language or self.get_default_language(using)

    def get_index_kwargs(self, language):
        """
        This is called to filter the indexed queryset.
        """
        return {}

    def index_queryset(self, using=None):
        self._get_backend(using)
        language = self.get_current_language(using)
        filter_kwargs = self.get_index_kwargs(language)
        return self.get_model().objects.filter(**filter_kwargs)

    def prepare(self, obj):
        current_language = self.get_current_language(using=self._backend_alias, obj=obj)

        with override(current_language):
            self.prepared_data = super().prepare(obj)
            self.prepared_data['text'] = ' '.join(self.prepared_data['text'].split())
            return self.prepared_data
