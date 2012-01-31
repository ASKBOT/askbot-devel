import datetime
from django.db import models
from askbot.models.base import AnonymousContent


class AnonymousAnswer(AnonymousContent):
    question = models.ForeignKey('Post', related_name='anonymous_answers')

    def publish(self, user):
        added_at = datetime.datetime.now()
        from askbot import models
        models.Post.objects.create_new_answer(
            thread=self.question.thread,
            author=user,
            added_at=added_at,
            wiki=self.wiki,
            text=self.text
        )
        self.delete()
