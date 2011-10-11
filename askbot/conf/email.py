"""
Email related settings
"""
from askbot.conf.settings_wrapper import settings
from askbot.deps import livesettings
from askbot import const
from django.utils.translation import ugettext as _
from django.conf import settings as django_settings

EMAIL_SUBJECT_PREFIX = getattr(django_settings, 'EMAIL_SUBJECT_PREFIX', '')

EMAIL = livesettings.ConfigurationGroup(
            'EMAIL',
            _('Email and email alert settings'), 
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

settings.register(
    livesettings.IntegerValue(
        EMAIL,
        'MAX_ALERTS_PER_EMAIL',
        default=7,
        description=_('Maximum number of news entries in an email alert')
    )
)

#settings.register(
#    livesettings.StringValue(
#        EMAIL,
#        'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE',
#        default='w',
#        choices=const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES,
#        description=_('Default news notification frequency'),
#        help_text=_(
#                    'This option currently defines default frequency '
#                    'of emailed updates in the following five categories: '
#                    'questions asked by user, answered by user, individually '
#                    'selected, entire forum (per person tag filter applies) '
#                    'and posts mentioning the user and comment responses'
#                    )
#    )
#)


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
        default='w',
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
        default='w',
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
        default='w',
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
        default='w',
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
        description = _('Send periodic reminders about unanswered questions'),
        help_text = _(
            'NOTE: in order to use this feature, it is necessary to '
            'run the management command "send_unanswered_question_reminders" '
            '(for example, via a cron job - with an appropriate frequency) '
            'and an IMAP server with a dedicated inbox must be configured '
        )
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
        'EMAIL_VALIDATION',
        default=False,
        hidden=True,
        description=_('Require email verification before allowing to post'),
        help_text=_('Active email verification is done by sending a verification key in email')
    )
)

settings.register(
    livesettings.BooleanValue(
        EMAIL,
        'EMAIL_UNIQUE',
        default=True,
        description=_('Allow only one account per email address')
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
