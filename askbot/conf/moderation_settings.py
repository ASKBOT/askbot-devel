"""Moderation-related livesettings."""
from django.utils.translation import gettext_lazy as _
from livesettings import values as livesettings
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import DATA_AND_FORMATTING

MODERATION_SETTINGS = livesettings.ConfigurationGroup(
    'MODERATION_SETTINGS',
    _('Moderation settings'),
    super_group=DATA_AND_FORMATTING
)

settings.register(
    livesettings.BooleanValue(
        MODERATION_SETTINGS,
        'DELETE_BLOCKED_USERS',
        description=_('Delete blocked spammer accounts entirely'),
        help_text=_(
            'When enabled, blocking a spammer deletes the user account '
            'along with all their content, preventing accumulation of '
            'dead accounts. When disabled, the account is kept with '
            'blocked status (original behavior).'
        ),
        default=True
    )
)
