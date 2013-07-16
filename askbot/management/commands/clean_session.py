"""deletes expired sessions from the session database table
works only when sessions are stored in the database
"""
from django.core.management.base import NoArgsCommand
from django.contrib.sessions.models import Session
from django.db import transaction
from optparse import make_option
from askbot.utils.console import ProgressBar
from datetime import datetime
from django.utils import timezone

ITEMS_PER_TRANSACTION = 1000

class Command(NoArgsCommand):
    """Django management command class"""

    option_list = NoArgsCommand.option_list + (
            make_option('--quiet',
                action='store_true',
                dest='quiet',
                default=False,
                help="Do not print anything when called."
                ),
            )

    @transaction.commit_manually
    def handle_noargs(self, **options):
        """deletes old sessions"""
        quiet = options.get('quiet', False)

        expired_sessions = Session.objects.filter(
                                expire_date__lt=timezone.now()
                            )
        count = expired_sessions.count()
        expired_sessions = expired_sessions.iterator()
        if quiet is False:
            message = 'There are %d expired sessions' % count
            expired_sessions = ProgressBar(expired_sessions, count, message)

        deleted_count = 0
        for session in expired_sessions:
            session.delete()
            deleted_count += 1
            if deleted_count % ITEMS_PER_TRANSACTION == 0:
                transaction.commit()

        transaction.commit()
