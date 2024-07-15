"""Management commands for Askbot Analytics Events.
Compiles summaries of Askbot Analytics Events in the
per-user and per-group Summary tables.
"""
import datetime
from django.db import transaction
from django.core.management.base import BaseCommand
from askbot.utils.console import ProgressBar
from askbot.models.analytics import Event, GroupDailySummary, UserDailySummary

class Command(BaseCommand): # pylint: disable=missing-class-docstring, too-few-public-methods

    def add_arguments(self, parser): # pylint: disable=missing-function-docstring
        parser.add_argument('--silent', action='store_true', help='Print progress on the console')

    def handle(self, *args, **options): # pylint: disable=missing-function-docstring
        """
        Filters uncompiled analytics events.
        Iterates over the events, and calculates per user summaries
        per date.

        THen iterates over the per-user summaries and combines them
        into the per-group summaries.
        """
        events = Event.objects.filter(compiled=False).order_by('timestamp') # pylint: disable=no-member
        events_count = events.count()
        message = 'Compiling Events:'
        silent = options['silent']
        for event in ProgressBar(events.iterator(), events_count, message=message, silent=silent):
            self.compile_event(event)

        daily_summaries = UserDailySummary.objects.filter(compiled=False).order_by('date') # pylint: disable=no-member
        message = 'Compiling User Daily Summaries:'
        summaries_count = daily_summaries.count()
        iterator = daily_summaries.iterator()
        for daily_summary in ProgressBar(iterator, summaries_count, message=message, silent=silent):
            self.compile_user_daily_summary(daily_summary)

        # todo:
        # update the time on site (how?)
        # update the total number of users per group
        # maybe: record number of active users per group within period
        message = 'Count users per group:'
        group_daily_summaries = GroupDailySummary.objects.filter(compiled=False) # pylint: disable=no-member
        count = group_daily_summaries.count()
        iterator = group_daily_summaries.iterator() # pylint: disable=no-member
        for group_summary in ProgressBar(iterator, count, message=message, silent=silent):
            self.update_users_count_per_group(group_summary)


    @transaction.atomic
    def update_users_count_per_group(self, group_summary):
        """Counts the number of users in the group at the end of the day"""
        join_date_cutoff = group_summary.date + datetime.timedelta(days=1)
        users = group_summary.group.user_set.filter(date_joined__lte=join_date_cutoff) # pylint: disable=no-member
        group_summary.num_users = users.count()
        group_summary.compiled = True
        group_summary.save()


    @transaction.atomic
    def compile_event(self, event):
        """Adds up event stats into the user daily summary"""
        date = event.timestamp.date()
        user = event.session.user
        user_summary, _ = UserDailySummary.objects.get_or_create(date=date, # pylint: disable=no-member
                                                                 user=user)
        user_summary.add_event(event)
        user_summary.save()
        Event.objects.filter(id=event.id).update(compiled=True) # pylint: disable=no-member


    @transaction.atomic
    def compile_user_daily_summary(self, user_daily_summary):
        groups = user_daily_summary.user.get_groups(used_for_analytics=True)
        for group in groups:
            date = user_daily_summary.date
            group_summary, _ = GroupDailySummary.objects.get_or_create(date=date, # pylint: disable=no-member
                                                                       group=group)
            group_summary += user_daily_summary
            group_summary.save()

        UserDailySummary.objects.filter(id=user_daily_summary.id).update(compiled=True) # pylint: disable=no-member

