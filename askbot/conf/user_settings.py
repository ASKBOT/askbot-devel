"""
User policy settings
"""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import LOGIN_USERS_COMMUNICATION
from askbot.deps import livesettings
from django.utils.translation import ugettext as _
from askbot import const

USER_SETTINGS = livesettings.ConfigurationGroup(
                    'USER_SETTINGS',
                    _('User settings'),
                    super_group = LOGIN_USERS_COMMUNICATION
                )

settings.register(
    livesettings.BooleanValue(
        USER_SETTINGS,
        'EDITABLE_SCREEN_NAME',
        default = True,
        description = _('Allow editing user screen name')
    )
)

settings.register(
    livesettings.BooleanValue(
        USER_SETTINGS,
        'ALLOW_ACCOUNT_RECOVERY_BY_EMAIL',
        default = True,
        description = _('Allow account recovery by email')
    )
)

settings.register(
    livesettings.BooleanValue(
        USER_SETTINGS,
        'ALLOW_ADD_REMOVE_LOGIN_METHODS',
        default = True,
        description = _('Allow adding and removing login methods')
    )
)

settings.register(
    livesettings.IntegerValue(
        USER_SETTINGS,
        'MIN_USERNAME_LENGTH',
        hidden=True,
        default=1,
        description=_('Minimum allowed length for screen name')
    )
)

settings.register(
    livesettings.StringValue(
        USER_SETTINGS,
        'GRAVATAR_TYPE',
        default='identicon',
        choices=const.GRAVATAR_TYPE_CHOICES,
        description=_('Default Gravatar icon type'),
        help_text=_(
                    'This option allows you to set the default avatar type for email addresses without associated gravatar images.  For more information, please visit <a href="http://en.gravatar.com/site/implement/images/">this page</a>.'
                    ) 
    )
)

settings.register(
    livesettings.StringValue(
        USER_SETTINGS,
        'NAME_OF_ANONYMOUS_USER',
        default = '',
        description = _('Name for the Anonymous user')
    )
)
