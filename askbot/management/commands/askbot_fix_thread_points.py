from django.core.management import BaseCommand
from django.db.models import F
from django.utils.translation import override

from askbot.models import Post


class Command(BaseCommand):
    """
    Fix incorrectly denormalized thread points by copying the value from
    its question.
    """
    def handle(self, *args, **kwargs):
        questions = (Post.objects
                     .filter(post_type='question')
                     .exclude(points=F('thread__points'))
                     .select_related('thread'))

        self.stdout.write(f'Fixing {questions.count()} threads...')

        for post in questions:
            with override(post.thread.language_code):
                post.thread.points = post.points
                post.thread.save()
                post.thread.clear_cached_data()
