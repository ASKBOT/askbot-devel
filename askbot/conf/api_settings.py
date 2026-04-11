"""API access control livesettings configuration."""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import EXTERNAL_SERVICES
from livesettings import values as livesettings
from django.utils.translation import gettext_lazy as _

API_SETTINGS = livesettings.ConfigurationGroup(
    'API_SETTINGS',
    _('Askbot API settings'),
    super_group=EXTERNAL_SERVICES
)

settings.register(
    livesettings.StringValue(
        API_SETTINGS,
        'API_V1_ACCESS_MODE',
        description=_('API v1 access mode'),
        default='public',
        choices=(
            ('public', _('Public (anyone can access)')),
            ('authenticated', _('Authenticated (login required)')),
            ('disabled', _('Disabled (moderator item lookups only)')),
        ),
        help_text=_(
            'NOTE: v1 API is read-only and this setting controls '
            'who can access the its endpoints. '
            '"Authenticated" requires login for all API access. '
            '"Disabled" blocks list endpoints entirely and allows '
            'only individual item lookups for moderators/admins '
            '(preserves merge dialog functionality).'
        )
    )
)
