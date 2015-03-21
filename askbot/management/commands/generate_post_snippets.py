from django.core.management.base import NoArgsCommand
from django.db import transaction
from askbot.models import Post
from askbot.utils.console import ProgressBar

class Command(NoArgsCommand):
    help = 'Generates snippets for all posts'
    @transaction.commit_manually
    def handle_noargs(self, *args, **kwargs):
        posts = Post.objects.all()
        count = posts.count()
        message = 'Building post snippets'
        for post in ProgressBar(posts.iterator(), count, message):
            if hasattr(post, 'summary'):
                post.summary = post.get_snippet()
                post.html = post.parse_post_text()['html']
                post.save()
                transaction.commit()
                if post.thread:
                    post.thread.clear_cached_data()
        transaction.commit()
