from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import LOGIN_USERS_COMMUNICATION
from askbot.deps import livesettings
from askbot.deps.livesettings import BooleanValue
from askbot.deps.livesettings import StringValue
from django.utils.translation import ugettext_lazy as _

ACCESS_CONTROL = livesettings.ConfigurationGroup(
                    'ACCESS_CONTROL',
                    _('Access control settings'),
                    super_group = LOGIN_USERS_COMMUNICATION
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
        default=True,
        description=_('Allow only registered user to access the forum'),
    )
)

EMAIL_VALIDATION_CASE_CHOICES = (
    ('nothing', _('nothing - not required')),
    ('see-content', _('access to content')),
    #'post-content', _('posting content'),
)

settings.register(
    livesettings.StringValue(
        ACCESS_CONTROL,
        'REQUIRE_VALID_EMAIL_FOR',
        default='see-content',
        choices=EMAIL_VALIDATION_CASE_CHOICES,
        description=_(
            'Require valid email for'
        )
    )
)

settings.register(
    livesettings.LongStringValue(
        ACCESS_CONTROL,
        'ALLOWED_EMAILS',
        default='',
        description=_('Allowed email addresses'),
        help_text=_('Please use space to separate the entries')
    )
)

settings.register(
    livesettings.LongStringValue(
        ACCESS_CONTROL,
        'ALLOWED_EMAIL_DOMAINS',
        default='appfolio.com rentlinx.com mycase.com',
        description=_('Allowed email domain names'),
        help_text=_('Please use space to separate the entries, do not use the @ symbol!')
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
