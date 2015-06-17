"""this management commands will fix corrupted posts
that do not have revisions by creating a fake initial revision
based on the content stored in the post itself
"""
from django.core.management.base import NoArgsCommand
from django.db.models import signals, Count
from askbot import models
from askbot import const

def fix_revisionless_posts(post_class):
        posts = post_class.objects.annotate(
                                        rev_count = Count('revisions')
                                    ).filter(rev_count = 0)
        print 'have %d corrupted posts' % len(posts)
        for post in posts:
            post.add_revision(
                        author=post.author,
                        text=post.text,
                        comment=unicode(const.POST_STATUS['default_version']),
                        revised_at = post.added_at
                    )
            post.last_edited_at = None
            post.last_edited_by = None
            post.save()

class Command(NoArgsCommand):
    """Command class for "fix_answer_counts"
    """

    def remove_save_signals(self):
        """removes signals on model pre-save and
        post-save, so that there are no side-effects
        besides actually updating the answer counts
        """
        signals.pre_save.receivers = []
        signals.post_save.receivers = []

    def handle(self, *arguments, **options):
        """function that handles the command job
        """
        self.remove_save_signals()
        fix_revisionless_posts(models.Post)
