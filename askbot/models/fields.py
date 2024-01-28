from django.db import models
from django.conf import settings as django_settings

class LanguageCodeField(models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs['choices'] = django_settings.LANGUAGES
        kwargs['default'] = django_settings.LANGUAGE_CODE
        kwargs['max_length'] = 16
        super().__init__(*args, **kwargs)
