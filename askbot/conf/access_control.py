from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import LOGIN_USERS_COMMUNICATION
from askbot.deps import livesettings
from django.utils.translation import ugettext as _

ACCESS_CONTROL = livesettings.ConfigurationGroup(
                    'ACCESS_CONTROL',
                    _('Access control settings'),
                    super_group = LOGIN_USERS_COMMUNICATION
                )

settings.register(
    livesettings.BooleanValue(
        ACCESS_CONTROL,
        'ASKBOT_CLOSED_FORUM_MODE',
        default = False,
        description=_('Support mode where only registered users can access the forum'),
        help_text=_('to activate this permanently use ASKBOT_CLOSED_FORUM_MODE '
            'in your settings.py')
    )
)


