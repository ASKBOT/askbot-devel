
import datetime
from django.core.management import BaseCommand
from django.conf import settings as django_settings
from django.template.loader import get_template
from askbot import models
from askbot import const
from askbot.conf import settings as askbot_settings
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.utils import translation
from askbot.mail.messages import AcceptAnswersReminder
from askbot.utils.classes import ReminderSchedule
from askbot.utils.html import site_url
from django.template import Context

DEBUG_THIS_COMMAND = False

class Command(BaseCommand):
    def handle(self, **options):
        translation.activate(django_settings.LANGUAGE_CODE)
        if askbot_settings.ENABLE_EMAIL_ALERTS == False:
            return
        if askbot_settings.ENABLE_ACCEPT_ANSWER_REMINDERS == False:
            return
        #get questions without answers, excluding closed and deleted
        #order it by descending added_at date

        schedule = ReminderSchedule(
            askbot_settings.DAYS_BEFORE_SENDING_ACCEPT_ANSWER_REMINDER,
            askbot_settings.ACCEPT_ANSWER_REMINDER_FREQUENCY,
            askbot_settings.MAX_ACCEPT_ANSWER_REMINDERS
        )

        questions = models.Post.objects.get_questions().exclude(
                                        deleted = True
                                    ).added_between(
                                        start = schedule.start_cutoff_date,
                                        end = schedule.end_cutoff_date
                                    ).filter(
                                        thread__answer_count__gt = 0
                                    ).filter(
                                        thread__accepted_answer__isnull=True #answer_accepted = False
                                    ).order_by('-added_at')
        #for all users, excluding blocked
        #for each user, select a tag filtered subset
        #format the email reminder and send it
        for user in models.User.objects.exclude(askbot_profile__status__in = ('t', 'c')):
            user_questions = questions.filter(author=user)

            final_question_list = user_questions.get_questions_needing_reminder(
                activity_type=const.TYPE_ACTIVITY_ACCEPT_ANSWER_REMINDER_SENT,
                user=user,
                recurrence_delay=schedule.recurrence_delay
            )
            #todo: rewrite using query set filter
            #may be a lot more efficient

            question_count = len(final_question_list)
            if question_count == 0:
                continue

            email = AcceptAnswersReminder({
                        'questions': final_question_list,
                        'recipient_user': user
                    })

            if DEBUG_THIS_COMMAND:
                print(f"User: {user.email}<br>\nSubject:{email.render_subject()}<br>\nText: {email.render_body()}<br>\n")
            else:
                email.send([user.email],)
