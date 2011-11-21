"""various utility classes"""
import datetime

class ReminderSchedule(object):
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

    def __init__(self, 
        days_before_starting = None,
        frequency_days = None, 
        max_reminders = None):
        """function that calculates values
        and assigns them to user-friendly variable names

        * ``days_before_starting`` - days to wait before sending any reminders
        * ``frequency_days`` - days to wait between sending reminders
        * ``max_reminders`` - maximum number of reminders to send
        """
        self.wait_period = datetime.timedelta(days_before_starting)
        self.end_cutoff_date = datetime.datetime.now() - self.wait_period

        self.recurrence_delay = datetime.timedelta(frequency_days)
        self.max_reminders = max_reminders
        self.start_cutoff_date = self.end_cutoff_date - \
            (self.max_reminders - 1)*self.recurrence_delay
