"""Management command to reset the summarized flag on all items.
And delete all the event summaries.
"""
import sys
from django.db import models
from django.core.management.base import BaseCommand
from askbot.utils.console import get_yes_or_no
from askbot.models.analytics import (
    Event, DailyGroupSummary, HourlyGroupSummary,
    DailyUserSummary, HourlyUserSummary, Session
)

RESET_CONFIRMATION_MESSAGE = """Are you you want to reset all analytics data?
This will mark all events and sessions as unsummarized
and delete all the hourly and daily event summaries.
"""

class Command(BaseCommand): # pylint: disable=missing-class-docstring, too-few-public-methods

    def add_arguments(self, parser): # pylint: disable=missing-function-docstring
        parser.add_argument('--silent', action='store_true', help='Print progress on the console')

    def handle(self, *args, **options): # pylint: disable=missing-function-docstring
        """
        Filters unsummarized analytics events.
        Iterates over the events, and calculates per user summaries
        per date.

        THen iterates over the per-user summaries and combines them
        into the per-group summaries.
        """
        self.reset_analytics(options)

    def reset_analytics(self, options):
        """Resets the summarized flag on all items and recompile from scratch"""
        if not options['silent']:
            answer = get_yes_or_no(RESET_CONFIRMATION_MESSAGE, default='no')
            if answer != 'yes':
                print('Aborting')
                sys.exit(1)

        Session.objects.update(last_summarized_at=models.F('created_at'))
        Event.objects.filter(summarized=True).update(summarized=False) # pylint: disable=no-member
        HourlyUserSummary.objects.all().delete()
        HourlyGroupSummary.objects.all().delete()
        DailyUserSummary.objects.all().delete()
        DailyGroupSummary.objects.all().delete()