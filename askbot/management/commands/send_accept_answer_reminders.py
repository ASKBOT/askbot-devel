import datetime
from django.core.management.base import NoArgsCommand
from django.conf import settings as django_settings
from askbot import models
from askbot import const
from askbot.conf import settings as askbot_settings
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from askbot.utils import mail
from askbot.utils.classes import ReminderSchedule

DEBUG_THIS_COMMAND = False

class Command(NoArgsCommand):
    def handle_noargs(self, **options):
        if askbot_settings.ENABLE_ACCEPT_ANSWER_REMINDERS == False:
            return
        #get questions without answers, excluding closed and deleted
        #order it by descending added_at date

        schedule = ReminderSchedule(
            askbot_settings.DAYS_BEFORE_SENDING_ACCEPT_ANSWER_REMINDER,
            askbot_settings.ACCEPT_ANSWER_REMINDER_FREQUENCY,
            askbot_settings.MAX_ACCEPT_ANSWER_REMINDERS
        )

        questions = models.Question.objects.exclude(
                                        deleted = True
                                    ).added_between(
                                        start = schedule.start_cutoff_date,
                                        end = schedule.end_cutoff_date
                                    ).filter(
                                        answer_count__gt = 0
                                    ).filter(
                                        answer_accepted = False
                                    ).order_by('-added_at')
        #for all users, excluding blocked
        #for each user, select a tag filtered subset
        #format the email reminder and send it
        for user in models.User.objects.exclude(status = 'b'):
            user_questions = questions.filter(author = user)

            final_question_list = user_questions.get_questions_needing_reminder(
                activity_type = const.TYPE_ACTIVITY_ACCEPT_ANSWER_REMINDER_SENT,
                user = user,
                recurrence_delay = schedule.recurrence_delay
            )
            #todo: rewrite using query set filter
            #may be a lot more efficient

            question_count = len(final_question_list)
            if question_count == 0:
                continue

            #tag_summary = get_tag_summary_from_questions(final_question_list)
            subject_line = _(
                'Accept the best answer for %(question_count)d of your questions'
            ) % {'question_count': question_count}

            #todo - make a template for these
            if question_count == 1:
                reminder_phrase = _('Please accept the best answer for this question:')
            else:
                reminder_phrase = _('Please accept the best answer for these questions:')
            body_text = '<p>' + reminder_phrase + '</p>'
            body_text += '<ul>'
            for question in final_question_list:
                body_text += '<li><a href="%s%s?sort=latest">%s</a></li>' \
                            % (
                                askbot_settings.APP_URL,
                                question.get_absolute_url(),
                                question.title
                            )
            body_text += '</ul>'

            if DEBUG_THIS_COMMAND:
                print "User: %s<br>\nSubject:%s<br>\nText: %s<br>\n" % \
                    (user.email, subject_line, body_text)
            else:
                mail.send_mail(
                    subject_line = subject_line,
                    body_text = body_text,
                    recipient_list = (user.email,)
                )
