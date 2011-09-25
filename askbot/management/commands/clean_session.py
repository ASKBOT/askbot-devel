from django.core.management.base import NoArgsCommand
from django.contrib.sessions.models import Session
from django.db import transaction
from optparse import make_option
from askbot.utils.console import print_progress
from datetime import datetime

DELETE_LIMIT = 1000

class Command(NoArgsCommand):
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
        '''deletes old sessions'''
        quiet = options.get('quiet', False)
        expired_session_count  = Session.objects.filter(expire_date__lt=datetime.now()).count()
        expired_session_list= Session.objects.filter(expire_date__lt=datetime.now()).values_list('session_key', flat=True)
        transaction.commit()

        if not quiet:
            print "There are %d expired sessions" % expired_session_count

        range_limit = len(expired_session_list) - 1
        higher_limit = lower_limit = 0

        for i in range(DELETE_LIMIT, range_limit, DELETE_LIMIT):
            lower_limit = i
            higher_limit = lower_limit + DELETE_LIMIT
            sublist = expired_session_list[lower_limit:higher_limit]
            Session.objects.filter(session_key__in = sublist).delete()
            transaction.commit()
            if not quiet:
                print_progress(higher_limit-1, expired_session_count)

        if higher_limit < expired_session_list:
            sublist = expired_session_list[higher_limit:expired_session_count]
            Session.objects.filter(session_key__in = sublist).delete()
            print_progress(expired_session_count, expired_session_count)
            transaction.commit()

        if not quiet:
            print "sessions cleared"
