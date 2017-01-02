"""
User policy settings
"""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import LOGIN_USERS_COMMUNICATION
from askbot.deps import livesettings
from django.conf import settings as django_settings
from askbot.skins import utils as skin_utils
from django.utils.translation import ugettext_lazy as _
from askbot import const
import re

USER_SETTINGS = livesettings.ConfigurationGroup(
                    'USER_SETTINGS',
                    _('User settings'),
                    super_group = LOGIN_USERS_COMMUNICATION
                )

settings.register(
    livesettings.LongStringValue(
        USER_SETTINGS,
        'NEW_USER_GREETING',
        default=_('Welcome to our community!'),
        description=_('On-screen greeting shown to the new users')
    )
)

settings.register(
    livesettings.BooleanValue(
        USER_SETTINGS,
        'EDITABLE_SCREEN_NAME',
        default=True,
        description=_('Allow editing user screen name')
    )
)

settings.register(
    livesettings.BooleanValue(
        USER_SETTINGS,
        'SHOW_ADMINS_PRIVATE_USER_DATA',
        default=False,
        description=_('Show email addresses to moderators')
    )
)

settings.register(
    livesettings.BooleanValue(
        USER_SETTINGS,
        'AUTOFILL_USER_DATA',
        default = True,
        description = _('Auto-fill user name, email, etc on registration'),
        help_text = _('Implemented only for LDAP logins at this point')
    )
)

settings.register(
    livesettings.BooleanValue(
        USER_SETTINGS,
        'EDITABLE_EMAIL',
        default = True,
        description = _('Allow users change own email addresses')
    )
)

settings.register(
    livesettings.BooleanValue(
        USER_SETTINGS,
        'ALLOW_EMAIL_ADDRESS_IN_USERNAME',
        default=True,
        description=_('Allow email address in user name')
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

def avatar_type_callback(old, new):
    """strips trailing slash"""
    if settings.ENABLE_GRAVATAR:
        return new
    elif new == 'g':
        #can't use gravatar because it is disabled
        return 'n'
    return new

settings.register(
    livesettings.StringValue(
        USER_SETTINGS,
        'AVATAR_TYPE_FOR_NEW_USERS',
        description=_('Avatar type for new users'),
        default='g',
        choices=const.AVATAR_TYPE_CHOICES_FOR_NEW_USERS,
        update_callback=avatar_type_callback
    )
)

settings.register(
    livesettings.ImageValue(
        USER_SETTINGS,
        'DEFAULT_AVATAR_URL',
        description = _('Default avatar for users'),
        help_text = _(
                        'To change the avatar image, select new file, '
                        'then submit this whole form.'
                    ),
        default = '/images/nophoto.png',
        url_resolver = skin_utils.get_media_url
    )
)

def gravatar_url_callback(old, new):
    """strips trailing slash"""
    url_re = re.compile(r'([^/]*)/+$')
    return url_re.sub(r'\1', new)

settings.register(
    livesettings.StringValue(
        USER_SETTINGS,
        'GRAVATAR_BASE_URL',
        description=_(
                'Base URL for the gravatar service'
            ),
        default='//www.gravatar.com/avatar',
        update_callback=gravatar_url_callback
    )
)

settings.register(
    livesettings.BooleanValue(
        USER_SETTINGS,
        'ENABLE_GRAVATAR',
        default = True,
        description = _('Use automatic avatars from gravatar service'),
        help_text=_(
            'Check this option if you want to allow the use of '
            'gravatar.com for avatars. Please, note that this feature '
            'might take about 10 minutes to become fully effective. '
            'You will have to enable uploaded avatars as well. '
            'For more information, please visit '
            '<a href="http://askbot.org/doc/optional-modules.html#uploaded-avatars">this page</a>.'
        )
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
                    'This option allows you to set the default '
                    'avatar type for email addresses without associated '
                    'gravatar images.  For more information, please visit '
                    '<a href="http://en.gravatar.com/site/implement/images/">this page</a>.'
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
