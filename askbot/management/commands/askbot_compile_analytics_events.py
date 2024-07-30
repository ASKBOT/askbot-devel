"""Management commands for Askbot Analytics Events.
Compiles summaries of Askbot Analytics Events in the
per-user and per-group Summary tables.
"""
import datetime
from django.db import models, transaction
from django.core.management.base import BaseCommand
from askbot.utils.console import ProgressBar
from askbot.models.analytics import (
    Event, DailyGroupSummary, HourlyGroupSummary,
    DailyUserSummary, HourlyUserSummary, Session
)

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
        now = datetime.datetime.now()
        self.summarize_events(options) # to hourly user summaries
        self.extract_time_on_site_from_sessions(options)
        self.compile_hourly_user_summaries(options, now) # to daily user and hourly group summaries
        self.compile_hourly_group_summaries(options, now)


    def summarize_events(self, options):
        """Compiles events into daily per-user summaries"""
        events = Event.objects.filter(summarized=False).order_by('timestamp') # pylint: disable=no-member
        events_count = events.count()
        message = 'Compiling Events:'
        silent = options['silent']
        # 1) Populate daily summaries per user
        for event in ProgressBar(events.iterator(), events_count, message=message, silent=silent):
            self.summarize_event(event)


    @transaction.atomic
    def summarize_event(self, event):
        """Adds up event stats into the user daily summary"""
        hour = event.timestamp.replace(minute=0, second=0, microsecond=0)
        user = event.session.user
        user_summary, _ = HourlyUserSummary.objects.get_or_create(hour=hour, # pylint: disable=no-member
                                                                 user=user)
        user_summary.add_event(event)
        user_summary.save()
        Event.objects.filter(id=event.id).update(summarized=True) # pylint: disable=no-member


    def extract_time_on_site_from_sessions(self, options):
        """Updates the time on site in the per-user daily summaries"""
        message = 'Updating the time on site:'
        sessions = Session.objects.filter(last_summarized_at__lt=models.F('updated_at')) # pylint: disable=no-member
        sessions = sessions.order_by('updated_at')
        for session in ProgressBar(sessions.iterator(), sessions.count(),
                                   message=message, silent=options['silent']):
            self.extract_time_on_site_from_session(session)


    @transaction.atomic
    def extract_time_on_site_from_session(self, session):
        """Calculates the time on site for the session"""
        if session.updated_at <= session.last_summarized_at:
            return

        sess_start = session.created_at
        sess_end = session.updated_at
        user_id = session.user_id
        hour = sess_start.replace(minute=0, second=0, microsecond=0)
        while hour <= sess_end:
            window_start = max(sess_start, hour)
            window_end = min(sess_end, hour + datetime.timedelta(hours=1))
            window_duration = window_end - window_start
            summary, _ = HourlyUserSummary.objects.get_or_create(hour=hour, user_id=user_id) # pylint: disable=no-member
            summary.time_on_site += window_duration
            summary.save()

            hour += datetime.timedelta(hours=1)

        session.last_summarized_at = sess_end
        session.save()


    def compile_hourly_user_summaries(self, options, cutoff_time):
        """Compiles hourly per-user summaries into daily per-user summaries"""
        hourly_summaries = HourlyUserSummary.objects.filter(summarized=False) # pylint: disable=no-member
        cutoff_hour = cutoff_time.replace(minute=0, second=0, microsecond=0)
        hourly_summaries = hourly_summaries.filter(hour__lt=cutoff_hour) # hour must be completed
        hourly_summaries = hourly_summaries.order_by('hour')
        count = hourly_summaries.count()
        message = 'Compiling User Hourly Summaries:'
        silent = options['silent']
        for hourly_summary in ProgressBar(hourly_summaries.iterator(), count,
                                          message=message, silent=silent):
            self.compile_hourly_user_summary(hourly_summary)


    @transaction.atomic
    def compile_hourly_user_summary(self, hourly_user_summary):
        """Adds up user hourly summaries into the user daily summaries
        and the group hourly summaries"""
        groups = hourly_user_summary.user.get_groups(used_for_analytics=True)
        hour = hourly_user_summary.hour
        for group in groups:
            group_summary, _ = HourlyGroupSummary.objects.get_or_create(hour=hour, # pylint: disable=no-member
                                                                        group=group)
            group_summary += hourly_user_summary
            group_summary.save()

        daily_user_summary, _ = DailyUserSummary.objects.get_or_create( # pylint: disable=no-member
                                                date=hourly_user_summary.hour.date(),
                                                user=hourly_user_summary.user)
        daily_user_summary += hourly_user_summary
        daily_user_summary.save()

        HourlyUserSummary.objects.filter(id=hourly_user_summary.id).update(summarized=True) # pylint: disable=no-member


    def compile_hourly_group_summaries(self, options, cutoff_time):
        """
        1. Compiles hourly per-group summaries into daily per-group summaries
        2. Updates the total number of users in the group that joined before the end of the hour
        """
        message = 'Compile hourly group summaries: '
        hourly_group_summaries = HourlyGroupSummary.objects.filter(summarized=False) # pylint: disable=no-member
        cutoff_hour = cutoff_time.replace(minute=0, second=0, microsecond=0)
        # hour must be completed
        hourly_group_summaries = hourly_group_summaries.filter(hour__lt=cutoff_hour)
        count = hourly_group_summaries.count()
        iterator = hourly_group_summaries.iterator() # pylint: disable=no-member
        for group_summary in ProgressBar(iterator, count, message=message,
                                         silent=options['silent']):
            self.compile_hourly_group_summary(group_summary)


    @transaction.atomic
    def compile_hourly_group_summary(self, hourly_group_summary):
        """
        1. Adds hourly per-group summary into daily per-group summary
        2. Updates the total number of users in the group that joined before the end of the hour
        """
        join_date_cutoff = hourly_group_summary.hour + datetime.timedelta(hours=1)
        users = hourly_group_summary.group.user_set.filter(date_joined__lt=join_date_cutoff) # pylint: disable=no-member
        hourly_group_summary.num_users = users.count()

        daily_group_summary, _ = DailyGroupSummary.objects.get_or_create( # pylint: disable=no-member
                                                date=hourly_group_summary.hour.date(),
                                                group=hourly_group_summary.group)
        daily_group_summary += hourly_group_summary
        daily_group_summary.save()

        hourly_group_summary.summarized = True
        hourly_group_summary.save()
