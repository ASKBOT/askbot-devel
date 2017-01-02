from django.utils.translation import ugettext_lazy as _
from django.utils.translation import string_concat

from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import LOGIN_USERS_COMMUNICATION
from askbot.deps import livesettings
from askbot.deps.livesettings import BooleanValue
from askbot.deps.livesettings import StringValue

ACCESS_CONTROL = livesettings.ConfigurationGroup(
                    'ACCESS_CONTROL',
                    _('Access control settings'),
                    super_group=LOGIN_USERS_COMMUNICATION
                )

settings.register(
    BooleanValue(
        ACCESS_CONTROL,
        'READ_ONLY_MODE_ENABLED',
        default=False,
        description=_('Make site read-only'),
    )
)

settings.register(
    StringValue(
        ACCESS_CONTROL,
        'READ_ONLY_MESSAGE',
        default=_(
            'The site is temporarily read-only. '
            'Only viewing of the content is possible at the moment.'
        )
    )
)

settings.register(
    livesettings.BooleanValue(
        ACCESS_CONTROL,
        'ASKBOT_CLOSED_FORUM_MODE',
        default=False,
        description=_('Allow only registered user to access the forum'),
    )
)

settings.register(
    livesettings.BooleanValue(
        ACCESS_CONTROL,
        'NEW_REGISTRATIONS_DISABLED',
        default=False,
        description=_('Disable registration of new users'),
    )
)

settings.register(
    livesettings.LongStringValue(
        ACCESS_CONTROL,
        'NEW_REGISTRATIONS_DISABLED_MESSAGE',
        default=_('<p>New users cannot be registered at this time. Please sign '
                  'in if you already have an account.</p>'),
        description=_('Message explaining that user registrations are disabled'),
        help_text=_('HTML is allowed')
    )
)

EMAIL_VALIDATION_CASE_CHOICES = (
    ('nothing', _('nothing - not required')),
    ('see-content', _('account registration')),
    # ('post-content', _('posting content')),
)

settings.register(
    livesettings.StringValue(
        ACCESS_CONTROL,
        'REQUIRE_VALID_EMAIL_FOR',
        default='nothing',
        choices=EMAIL_VALIDATION_CASE_CHOICES,
        description=_('Require valid email for')
    )
)

# TODO: move REQUIRE_VALID_EMAIL_FOR to boolean setting
# settings.register(
#     livesettings.BooleanValue(
#         ACCESS_CONTROL,
#         'EMAIL_VALIDATION_REQUIRED',
#         default=False,
#         description=_('Require valid email address to register')
#     )
# )


def update_email_callback(old, new):
    if new.strip():
        settings.update('BLACKLISTED_EMAIL_PATTERNS_MODE', 'disabled')
    return new

settings.register(
    livesettings.LongStringValue(
        ACCESS_CONTROL,
        'ALLOWED_EMAILS',
        default='',
        description=_('Allowed email addresses'),
        help_text=string_concat(
            _('Please use space to separate the entries'),
            '. ',
            _('Entry disables blacklisted email patterns')
        ),
        update_callback=update_email_callback
    )
)

settings.register(
    livesettings.LongStringValue(
        ACCESS_CONTROL,
        'ALLOWED_EMAIL_DOMAINS',
        default='',
        description=_('Allowed email domain names'),
        help_text=string_concat(
            _('Please use space to separate the entries, do not use the @ symbol!'),
            '. ',
            _('Entry disables blacklisted email patterns')
        ),
        update_callback=update_email_callback
    )
)

BLACKLISTED_EMAIL_PATTERNS_MODE_CHOICES = (
    ('disabled', _('disable')),
    ('medium', string_concat(_('block user registrations'),
                             ', ',
                             _('allow existing users to post'))),
    ('strict', _('block completely')),
)

settings.register(
    livesettings.StringValue(
        ACCESS_CONTROL,
        'BLACKLISTED_EMAIL_PATTERNS_MODE',
        default='strict',
        choices=BLACKLISTED_EMAIL_PATTERNS_MODE_CHOICES,
        description=_('Blacklisted email address patterns mode'),
    )
)

settings.register(
    livesettings.LongStringValue(
        ACCESS_CONTROL,
        'BLACKLISTED_EMAIL_PATTERNS',
        default='',
        description=_('Blacklisted email address patterns'),
        help_text=string_concat(
            _('Please use space to separate the entries'),
            ', ',
            _('regular expressions are allowed'),
            '.'
        )
    )
)

settings.register(
    livesettings.BooleanValue(
        ACCESS_CONTROL,
        'ADMIN_INBOX_ACCESS_ENABLED',
        default=False,
        description=_("Allow moderators to access other's messages"),
    )
)
