"""Delete expired unconfirmed first-post confirmations.

Removes the post and (if the user has no other posts) the user.
Intended to be run periodically via cron, e.g. daily.

Usage:
    python manage.py askbot_delete_expired_confirmations
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Delete expired unconfirmed first-post confirmations and their users'

    def handle(self, *args, **kwargs):
        from askbot.models.post_confirmation import PostConfirmation
        count = PostConfirmation.delete_expired_unconfirmed()
        self.stdout.write(f'Deleted {count} expired unconfirmed confirmation(s).')
