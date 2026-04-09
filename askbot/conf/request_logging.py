"""Request logging livesettings configuration."""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import EXTERNAL_SERVICES
from livesettings import values as livesettings
from django.utils.translation import gettext_lazy as _

REQUEST_LOGGING = livesettings.ConfigurationGroup(
    'REQUEST_LOGGING',
    _('Request logging'),
    super_group=EXTERNAL_SERVICES
)

settings.register(
    livesettings.BooleanValue(
        REQUEST_LOGGING,
        'REQUEST_LOG_ENABLED',
        description=_('Enable request logging'),
        default=True,
        help_text=_('Log every request with IP, method, path, status, '
                    'response time, and user. Uses the askbot.request_log '
                    'Python logger.')
    )
)

settings.register(
    livesettings.BooleanValue(
        REQUEST_LOGGING,
        'REQUEST_LOG_IGNORE_STATIC',
        description=_('Ignore static file requests'),
        default=True,
        help_text=_('Skip logging requests for /m/ and /upfiles/ paths.')
    )
)
