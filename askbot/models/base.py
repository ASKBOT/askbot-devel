from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from askbot.conf import settings as askbot_settings

class BaseQuerySetManager(models.Manager):
    """Base class for chainable custom filters on the query sets.

    pattern from http://djangosnippets.org/snippets/562/

    Usage (the most basic example, all imports explicit for clarity):

    >>>import django.db.models.QuerySet
    >>>import django.db.models.Model
    >>>import askbot.models.base.BaseQuerySetManager
    >>>
    >>>class SomeQuerySet(django.db.models.QuerySet):
    >>>    def some_custom_filter(self, *args, **kwargs):
    >>>        return self #or any custom code
    >>>    #add more custom filters here
    >>>
    >>>class SomeManager(askbot.models.base.BaseQuerySetManager)
    >>>    def get_queryset(self):
    >>>        return SomeQuerySet(self.model)
    >>>
    >>>class SomeModel(django.db.models.Model)
    >>>    #add fields here
    >>>    objects = SomeManager()
    """
    def __getattr__(self, attr, *args):
        ## The following two lines fix the problem from this ticket:
        ## https://code.djangoproject.com/ticket/15062#comment:6
        ## https://code.djangoproject.com/changeset/15220
        ## Queryset.only() seems to suffer from that on some occasions
        if attr.startswith('_'):
            raise AttributeError
        ##
        try:
            return getattr(self.__class__, attr, *args)
        except AttributeError:
            return getattr(self.get_queryset(), attr, *args)


class AnonymousContent(models.Model):
    """Base class for AnonymousQuestion and AnonymousAnswer"""
    session_key = models.CharField(max_length=40)  #session id for anonymous questions
    wiki = models.BooleanField(default=False)
    added_at = models.DateTimeField(default=timezone.now)
    ip_addr = models.GenericIPAddressField(max_length=45) #allow high port numbers
    author = models.ForeignKey(User,null=True)
    text = models.TextField()

    class Meta:
        abstract = True
        app_label = 'askbot'

class DraftContent(models.Model):
    """Base for autosaved DraftQuestion and DraftAnswer"""
    text = models.TextField(null=True)

    class Meta:
        abstract = True
        app_label = 'askbot'

    def get_text(self):
        if self.text.strip() == '<br data-mce-bogus="1">':
            return ''
        return self.text
