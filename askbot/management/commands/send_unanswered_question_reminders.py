"""Command that sends reminders about unanswered questions"""

from django.db.models import Q
from django.conf import settings as django_settings
from django.core.management import BaseCommand
from django.utils import translation
from askbot import models
from askbot import const
from askbot.conf import settings as askbot_settings
from askbot.mail.messages import UnansweredQuestionsReminder
from askbot.utils.classes import ReminderSchedule

DEBUG_THIS_COMMAND = False

class Command(BaseCommand):
    """management command that sends reminders
    about unanswered questions to all users
    """
    def handle(self, **options):
        """The function running the command."""
        translation.activate(django_settings.LANGUAGE_CODE)
        if askbot_settings.ENABLE_EMAIL_ALERTS is False:
            return
        if askbot_settings.ENABLE_UNANSWERED_REMINDERS is False:
            return

        #select questions within the range of the reminder schedule
        schedule = ReminderSchedule(
            askbot_settings.DAYS_BEFORE_SENDING_UNANSWERED_REMINDER,
            askbot_settings.UNANSWERED_REMINDER_FREQUENCY,
            max_reminders=askbot_settings.MAX_UNANSWERED_REMINDERS
        )
        if schedule.start_cutoff_date == schedule.end_cutoff_date:
            return

        questions = self.get_questions(schedule)
        if questions.count() == 0:
            return

        # for each eligible user send a somewhat personalized email if
        # they agreed to receiving those emails
        for user in self.get_users():
            user.add_missing_askbot_subscriptions()
            email_setting = user.notification_subscriptions.filter(feed_type='q_noans')[0]
            if not email_setting.should_send_now():
                continue
            filtered_questions = self.get_filtered_question_list(questions, user, schedule)
            if not filtered_questions:
                continue

            self.send_email(user, filtered_questions)
            email_setting.mark_reported_now()


    @staticmethod
    def send_email(user, questions):
        """Sends the formatted email"""
        email = UnansweredQuestionsReminder({'recipient_user': user,
                                             'questions': questions})
        if DEBUG_THIS_COMMAND:
            print(f"User: {user.email}<br>\nSubject:{email.render_subject()}<br>\nText: {email.render_body()}<br>\n")
        else:
            email.send([user.email,])


    @staticmethod
    def get_filtered_question_list(questions, user, schedule):
        """Returns a list of questions tag filtered for the user
        that fall within acceptable reminder time window."""
        user_questions = questions.exclude(author=user)
        user_questions = user.get_tag_filtered_questions(user_questions)

        if askbot_settings.GROUPS_ENABLED:
            user_groups = user.get_groups()
            user_questions = user_questions.filter(groups__in=user_groups)

        return user_questions.get_questions_needing_reminder(
            user=user,
            activity_type=const.TYPE_ACTIVITY_UNANSWERED_REMINDER_SENT,
            recurrence_delay=schedule.recurrence_delay
        )


    @staticmethod
    def get_questions(schedule):
        """Returns query set of questions that have no answers
        that are not in moderation and were added within a scheduled
        interval.
        Questions are sorted as oldest first"""
        #get questions without answers, excluding closed and deleted
        #order it by descending added_at date
        questions = models.Post.objects.get_questions()

        #we don't report closed, deleted or moderation queue questions
        exclude_filter = Q(thread__closed=True) | Q(deleted=True)
        if askbot_settings.CONTENT_MODERATION_MODE == 'premoderation':
            exclude_filter |= Q(approved=False)
        questions = questions.exclude(exclude_filter)
        questions = questions.added_between(start=schedule.start_cutoff_date,
                                            end=schedule.end_cutoff_date)

        #take only questions with zero answers
        questions = questions.filter(thread__answer_count=0)
        return questions.order_by('added_at')


    @staticmethod
    def get_users():
        """Returns query set of users that are eligible to receive
        the notification"""
        if askbot_settings.UNANSWERED_REMINDER_RECIPIENTS == 'admins':
            # admins and moderators
            recipient_statuses = ('d', 'm')
        else:
            # accepted users (regular users), watched users, admins and moderators
            recipient_statuses = ('a', 'w', 'd', 'm')
        return models.User.objects.filter(askbot_profile__status__in=recipient_statuses)
