"""
Email related settings
"""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import LOGIN_USERS_COMMUNICATION
from askbot.deps import livesettings
from askbot import const
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import string_concat
from django.conf import settings as django_settings

EMAIL_SUBJECT_PREFIX = getattr(django_settings, 'EMAIL_SUBJECT_PREFIX', '')

EMAIL = livesettings.ConfigurationGroup(
            'EMAIL',
            _('Email and email alert settings'),
            super_group = LOGIN_USERS_COMMUNICATION
        )

settings.register(
    livesettings.StringValue(
        EMAIL,
        'EMAIL_SUBJECT_PREFIX',
        default = EMAIL_SUBJECT_PREFIX,
        description = _('Prefix for the email subject line'),
        help_text = _(
                'This setting takes default from the django setting'
                'EMAIL_SUBJECT_PREFIX. A value entered here will override'
                'the default.'
            )
    )
)

def get_default_admin_email():
    try:
        return django_settings.ADMINS[0][1]
    except:
        return ''

settings.register(
    livesettings.StringValue(
        EMAIL,
        'ADMIN_EMAIL',
        default=get_default_admin_email(),
        description=_('Site administrator email address')
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'ENABLE_EMAIL_ALERTS',
        default=True,
        description=_('Enable email alerts'),
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'INSTANT_EMAIL_ALERT_ENABLED',
        description=_('Enable instant email alerts'),
        default=True
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'WELCOME_EMAIL_ENABLED',
        description=_('Enable welcome email'),
        default=True
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'REJECTED_POST_EMAIL_ENABLED',
        description=_('Enable rejected post alert'),
        help_text=_('Also, premoderation mode must be enabled'),
        default=True
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'APPROVED_POST_NOTIFICATION_ENABLED',
        description=_('Enable approved post alert'),
        help_text=_('Also, premoderation mode must be enabled'),
        default=True
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'BATCH_EMAIL_ALERT_ENABLED',
        description=_('Enable batch email alert'),
        default=True
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'GROUP_MESSAGING_EMAIL_ALERT_ENABLED',
        description=_('Enable private messaging alerts'),
        default=True
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'MODERATION_QUEUE_NOTIFICATION_ENABLED',
        description=_('Enable moderation queue alerts'),
        default=True
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'HTML_EMAIL_ENABLED',
        default=True,
        description=_('Enable HTML-formatted email'),
        help_text=_('May not be supported by some email clients')
    )
)

settings.register(
    livesettings.IntegerValue(
        EMAIL,
        'MAX_ALERTS_PER_EMAIL',
        default=7,
        description=_('Maximum number of news entries in an email alert')
    )
)

settings.register(
    livesettings.StringValue(
        EMAIL,
        'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_Q_ALL',
        default='w',
        choices=const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES,
        description=_('Default notification frequency all questions'),
        help_text=_(
                    'Option to define frequency of emailed updates for: '
                    'all questions.'
                    )
    )
)

settings.register(
    livesettings.StringValue(
        EMAIL,
        'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_Q_ASK',
        default='i',
        choices=const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES,
        description=_('Default notification frequency questions asked by the user'),
        help_text=_(
                    'Option to define frequency of emailed updates for: '
                    'Question asked by the user.'
                    )
    )
)

settings.register(
    livesettings.StringValue(
        EMAIL,
        'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_Q_ANS',
        default='d',
        choices=const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES,
        description=_('Default notification frequency questions answered by the user'),
        help_text=_(
                    'Option to define frequency of emailed updates for: '
                    'Question answered by the user.'
                    )
    )
)

settings.register(
    livesettings.StringValue(
        EMAIL,
        'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_Q_SEL',
        default='i',
        choices=const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES,
        description=_('Default notification frequency questions individually \
                       selected by the user'),
        help_text=_(
                    'Option to define frequency of emailed updates for: '
                    'Question individually selected by the user.'
                    )
    )
)

settings.register(
    livesettings.StringValue(
        EMAIL,
        'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_M_AND_C',
        default='i',
        choices=const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES,
        description=_('Default notification frequency for mentions \
                       and comments'),
        help_text=_(
                    'Option to define frequency of emailed updates for: '
                    'Mentions and comments.'
                    )
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'ENABLE_UNANSWERED_REMINDERS',
        default = False,
        description = _('Enable reminders about unanswered questions'),
        help_text = _(
            'NOTE: in order to use this feature, it is necessary to '
            'run the management command "send_unanswered_question_reminders" '
            '(for example, via a cron job - with an appropriate frequency) '
        )
    )
)

UNANSWERED_REMINDER_RECIPIENTS_CHOICES = (
    ('everyone', _('everyone')),
    ('admins', _('moderators & administrators'))
)

settings.register(
    livesettings.StringValue(
        EMAIL,
        'UNANSWERED_REMINDER_RECIPIENTS',
        default='everyone',
        choices=UNANSWERED_REMINDER_RECIPIENTS_CHOICES,
        description=_('Whom to remind about unanswered questions')
    )
)

settings.register(
    livesettings.IntegerValue(
        EMAIL,
        'DAYS_BEFORE_SENDING_UNANSWERED_REMINDER',
        default = 1,
        description = _(
            'Days before starting to send reminders about unanswered questions'
        ),
    )
)

settings.register(
    livesettings.IntegerValue(
        EMAIL,
        'UNANSWERED_REMINDER_FREQUENCY',
        default = 1,
        description = _(
            'How often to send unanswered question reminders '
            '(in days between the reminders sent).'
        )
    )
)

settings.register(
    livesettings.IntegerValue(
        EMAIL,
        'MAX_UNANSWERED_REMINDERS',
        default = 5,
        description = _(
            'Max. number of reminders to send '
            'about unanswered questions'
        )
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'ENABLE_ACCEPT_ANSWER_REMINDERS',
        default = False,
        description = _('Enable accept the best answer reminders'),
        help_text = _(
            'NOTE: in order to use this feature, it is necessary to '
            'run the management command "send_accept_answer_reminders" '
            '(for example, via a cron job - with an appropriate frequency) '
        )
    )
)

settings.register(
    livesettings.IntegerValue(
        EMAIL,
        'DAYS_BEFORE_SENDING_ACCEPT_ANSWER_REMINDER',
        default = 3,
        description = _(
            'Days before starting to send reminders to accept an answer'
        ),
    )
)

settings.register(
    livesettings.IntegerValue(
        EMAIL,
        'ACCEPT_ANSWER_REMINDER_FREQUENCY',
        default = 3,
        description = _(
            'How often to send accept answer reminders '
            '(in days between the reminders sent).'
        )
    )
)

settings.register(
    livesettings.IntegerValue(
        EMAIL,
        'MAX_ACCEPT_ANSWER_REMINDERS',
        default = 5,
        description = _(
            'Max. number of reminders to send '
            'to accept the best answer'
        )
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'BLANK_EMAIL_ALLOWED',
        default=False,
        description=_('Allow blank email'),
        help_text=string_concat(
            _('DANGER: makes impossible account recovery by email.'),
            ' ',
            settings.get_related_settings_info(
                ('ACCESS_CONTROL', 'REQUIRE_VALID_EMAIL_FOR', True, _('Must be not be required')),
            )
        )
    )
)

settings.register(
    livesettings.StringValue(
        EMAIL,
        'ANONYMOUS_USER_EMAIL',
        default='anonymous@askbot.org',
        description=_('Fake email for anonymous user'),
        help_text=_('Use this setting to control gravatar for email-less user')
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'ALLOW_ASKING_BY_EMAIL',
        default = False,
        description=_('Allow posting questions by email'),
        help_text=_(
            'Before enabling this setting - please fill out IMAP settings '
            'in the settings.py file'
        )
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'REPLACE_SPACE_WITH_DASH_IN_EMAILED_TAGS',
        default = True,
        description = _('Replace space in emailed tags with dash'),
        help_text = _(
            'This setting applies to tags written in the subject line '
            'of questions asked by email'
        )
    )
)

settings.register(
     livesettings.BooleanValue(
         EMAIL,
        'REPLY_BY_EMAIL',
        default = False,
        description=_('Enable posting answers and comments by email'),
        #TODO give a better explanation depending on lamson startup procedure
        help_text=_(
            'To enable this feature make sure lamson is running'

        )
    )
)

settings.register(
    livesettings.StringValue(
        EMAIL,
        'SELF_NOTIFY_EMAILED_POST_AUTHOR_WHEN',
        description=_(
            'Emailed post: when to notify author about publishing'
        ),
        choices=const.SELF_NOTIFY_EMAILED_POST_AUTHOR_WHEN_CHOICES,
        default=const.NEVER
    )
)

#not implemented at this point
#settings.register(
#    livesettings.IntegerValue(
#        EMAIL,
#        'SELF_NOTIFY_WEB_POST_AUTHOR_WHEN',
#        description = _(
#            'Web post: when to notify author about publishing'
#        ),
#        choices = const.SELF_NOTIFY_WEB_POST_AUTHOR_WHEN_CHOICES,
#        default =  const.NEVER
#    )
#)

settings.register(
     livesettings.StringValue(
         EMAIL,
        'REPLY_BY_EMAIL_HOSTNAME',
        default = "",
        description=_('Reply by email hostname'),
        #TODO give a better explanation depending on lamson startup procedure

    )
)

settings.register(
    livesettings.IntegerValue(
        EMAIL,
        'MIN_WORDS_FOR_ANSWER_BY_EMAIL',
        default=14,
        description=_('Email replies having fewer words than this number will be posted as comments instead of answers')
    )
)
