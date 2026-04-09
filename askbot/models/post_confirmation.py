"""Model for first-post email confirmation.

When a watched user makes their first post, we save the post as unapproved
and send a confirmation email. The user must click the link and confirm
to publish the post and get promoted to approved status.

Unconfirmed posts are deleted after expiry (3 days) along with the user
if they have no other posts.
"""
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

LOG = logging.getLogger(__name__)


def _make_key():
    return uuid.uuid4().hex


class PostConfirmation(models.Model):
    """Tracks pending first-post confirmations."""
    key = models.CharField(max_length=64, primary_key=True, default=_make_key)
    post = models.ForeignKey(
        'askbot.Post',
        on_delete=models.CASCADE,
        related_name='confirmations'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='post_confirmations'
    )
    created_at = models.DateTimeField(default=timezone.now)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    expires_on = models.DateTimeField(blank=True)

    class Meta:
        app_label = 'askbot'

    def save(self, *args, **kwargs):
        if not self.expires_on:
            self.expires_on = (self.created_at or timezone.now()) + timedelta(days=3)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_on

    @property
    def is_confirmed(self):
        return self.confirmed_at is not None

    def confirm(self):
        """Handle email confirmation of a first post."""
        if self.is_confirmed:
            return

        self.confirmed_at = timezone.now()
        self.save(update_fields=['confirmed_at'])

        from askbot.conf import settings as askbot_settings
        if askbot_settings.FIRST_POST_MODERATE_AFTER_CONFIRMATION:
            return

        self._approve_post()

    def _approve_post(self):
        """Approve the post and promote the user to approved status."""
        post = self.post
        post.approved = True
        post.save(update_fields=['approved'])

        revision = post.get_latest_revision()
        if revision and not revision.approved:
            revision.approved = True
            revision.approved_by = self.user
            revision.approved_at = self.confirmed_at
            revision.save(update_fields=['approved', 'approved_by', 'approved_at'])

        if post.post_type == 'question':
            post.thread.approved = True
            post.thread.save(update_fields=['approved'])

        post.thread.reset_cached_data()

        profile = self.user.askbot_profile
        if profile.status == 'w':
            profile.status = 'a'
            profile.save(update_fields=['status'])

    @classmethod
    def delete_expired_unconfirmed(cls):
        """Delete expired unconfirmed posts and their users."""
        from askbot.models.post import Post
        expired = cls.objects.filter(
            confirmed_at__isnull=True,
            expires_on__lt=timezone.now()
        ).select_related('post', 'user')

        count = 0
        for confirmation in expired:
            user = confirmation.user
            post = confirmation.post
            try:
                post.delete()
                has_other_posts = Post.objects.filter(
                    author=user
                ).exists()
                if not has_other_posts:
                    user.delete()
                    LOG.info('Deleted unconfirmed user %s (no posts)', user.id)
                confirmation.delete()
                count += 1
            except Exception:
                LOG.exception(
                    'Error cleaning up expired confirmation %s',
                    confirmation.key[:8]
                )
        return count

    def __str__(self):
        return f'PostConfirmation(key={self.key[:8]}..., user={self.user_id})'
