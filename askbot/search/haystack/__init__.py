from django.conf import settings
from django.utils.translation import get_language

from haystack import indexes

try:
    from searchquery import AskbotSearchQuerySet
except:
    pass

class ThreadIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField()
    tags = indexes.MultiValueField()

    def get_model(self):
        from askbot.models import Thread
        return Thread

    def index_queryset(self, using=None):
        if getattr(settings, 'ASKBOT_MULTILINGUAL', True):
            lang_code = get_language()[:2]
            return self.get_model().objects.filter(language_code__startswith=lang_code,
                                                   deleted=False)
        else:
            return self.get_model().objects.filter(deleted=False)

    def prepare_tags(self, obj):
        return [tag.name for tag in obj.tags.all()]

class PostIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    post_text = indexes.CharField(model_attr='text')
    author = indexes.CharField()
    thread_id = indexes.IntegerField(model_attr='thread__pk', null=True)


    def get_model(self):
        from askbot.models import Post
        return Post

    def index_queryset(self, using=None):
        ALLOWED_TYPES = ('question', 'answer', 'comment')
        model_cls = self.get_model()
        if getattr(settings, 'ASKBOT_MULTILINGUAL', True):
            lang_code = get_language()[:2]
            return model_cls.objects.filter(
                                    language_code__startswith=lang_code,
                                    deleted=False,
                                    post_type__in=ALLOWED_TYPES
                                )
        else:
            return model_cls.objects.filter(
                                    deleted=False,
                                    post_type__in=ALLOWED_TYPES
                                )

class UserIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)

    def get_model(self):
        from askbot.models import User
        return User

    def index_queryset(self, using=None):
        return self.get_model().objects.all()
