"""Utility classes"""
import datetime
from django.utils import timezone
from django.conf import settings as django_settings

class ReminderSchedule: #pylint: disable=too-few-public-methods
    """class that given the three settings:
    * days to wait before sending the reminders
    * frequency of reminders
    * maximum number of reminders
    return dates when to start sending the reminders,
    when to stop, and give friendly names to other
    variables

    These objects can be reused to all methods that
    intend to remind of certain events periodically
    """

    def __init__(self, days_before_starting=None, frequency_days=None,
                 max_reminders=None):
        """function that calculates values
        and assigns them to user-friendly variable names
        * ``days_before_starting`` - days to wait before sending any reminders
        * ``frequency_days`` - days to wait between sending reminders
        * ``max_reminders`` - maximum number of reminders to send
        """
        # allows to start informing of unanswered questions
        # posted only after a specific date
        reset_cutoff = django_settings.ASKBOT_DELAYED_EMAIL_ALERTS_CUTOFF_TIMESTAMP

        self.wait_period = datetime.timedelta(days_before_starting)
        self.end_cutoff_date = max(timezone.now() - self.wait_period, reset_cutoff)

        self.recurrence_delay = datetime.timedelta(frequency_days)
        self.max_reminders = max_reminders

        norm_cutoff = self.end_cutoff_date \
                      - (self.max_reminders - 1)*self.recurrence_delay

        # allows to start informing of unanswered questions
        # posted only after a specific date
        reset_cutoff = django_settings.ASKBOT_DELAYED_EMAIL_ALERTS_CUTOFF_TIMESTAMP
        self.start_cutoff_date = max(norm_cutoff, reset_cutoff)
