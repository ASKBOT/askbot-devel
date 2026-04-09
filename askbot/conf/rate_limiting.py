"""Rate limiting livesettings configuration."""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import EXTERNAL_SERVICES
from livesettings import values as livesettings
from django.utils.translation import gettext_lazy as _

RATE_LIMITING = livesettings.ConfigurationGroup(
    'RATE_LIMITING',
    _('Rate limiting'),
    super_group=EXTERNAL_SERVICES
)

settings.register(
    livesettings.BooleanValue(
        RATE_LIMITING,
        'RATE_LIMIT_ENABLED',
        description=_('Enable rate limiting'),
        default=True,
        help_text=_('Master switch for per-IP request rate limiting.')
    )
)

settings.register(
    livesettings.IntegerValue(
        RATE_LIMITING,
        'RATE_LIMIT_REQUESTS_PER_WINDOW',
        description=_('Max requests per IP per window'),
        default=60,
        help_text=_('Number of requests allowed per IP within the sliding window.')
    )
)

settings.register(
    livesettings.IntegerValue(
        RATE_LIMITING,
        'RATE_LIMIT_WINDOW_SECONDS',
        description=_('Rate limit window (seconds)'),
        default=60,
        help_text=_('Duration of the sliding window in seconds.')
    )
)

settings.register(
    livesettings.IntegerValue(
        RATE_LIMITING,
        'RATE_LIMIT_CACHE_SIZE',
        description=_('Max tracked IPs'),
        default=200000,
        help_text=_('Maximum number of IPs to track in memory. '
                    'Each tracked IP uses approximately 3KB of memory '
                    '(50,000 IPs ≈ 150MB, 200,000 ≈ 600MB). '
                    'Set based on available server RAM. IPs exceeding this '
                    'limit evict the oldest entries, so use the ban command '
                    'for persistent blocking.')
    )
)

settings.register(
    livesettings.BooleanValue(
        RATE_LIMITING,
        'RATE_LIMIT_BAN_ENABLED',
        description=_('Enable ban command on rate limit'),
        default=False,
        help_text=_('When enabled, executes the ban command below '
                    'when an IP exceeds the rate limit. Note: the web '
                    'process typically lacks permissions to run '
                    'fail2ban-client directly. The recommended approach '
                    'for fail2ban is to enable request logging instead '
                    'and configure fail2ban to watch the log file for '
                    '"ratelimited=true" entries. Use this setting only '
                    'for commands the web process can run (e.g. writing '
                    'to a file or calling a local API).')
    )
)

settings.register(
    livesettings.StringValue(
        RATE_LIMITING,
        'RATE_LIMIT_BAN_COMMAND',
        description=_('Ban command template'),
        default='',
        help_text=_('Command to execute when banning an IP. '
                    'Use {ip} as placeholder. Must be runnable by the '
                    'web process user without elevated privileges.')
    )
)

# --- Registration rate limiting ---

settings.register(
    livesettings.BooleanValue(
        RATE_LIMITING,
        'REGISTRATION_RATE_LIMIT_ENABLED',
        description=_('Enable registration rate limiting'),
        default=True,
        help_text=_('Per-IP throttle on signup endpoints to slow '
                    'automated account creation.')
    )
)

settings.register(
    livesettings.IntegerValue(
        RATE_LIMITING,
        'REGISTRATION_RATE_LIMIT_PER_IP',
        description=_('Max registrations per IP per window'),
        default=3,
        help_text=_('Number of registrations allowed per IP within '
                    'the sliding window.')
    )
)

settings.register(
    livesettings.IntegerValue(
        RATE_LIMITING,
        'REGISTRATION_RATE_LIMIT_WINDOW_SECONDS',
        description=_('Registration rate limit window (seconds)'),
        default=86400,
        help_text=_('Duration of the sliding window in seconds. '
                    'Default: 86400 (1 day).')
    )
)

# --- Content velocity limiting ---

settings.register(
    livesettings.BooleanValue(
        RATE_LIMITING,
        'CONTENT_VELOCITY_ENABLED',
        description=_('Enable content velocity limiting'),
        default=False,
        help_text=_('Per-user post limit for watched users to slow '
                    'sophisticated spammers.')
    )
)

settings.register(
    livesettings.IntegerValue(
        RATE_LIMITING,
        'CONTENT_VELOCITY_MAX_POSTS',
        description=_('Max posts per window (watched users)'),
        default=5,
        help_text=_('Maximum posts a watched user can make within '
                    'the velocity window.')
    )
)

settings.register(
    livesettings.IntegerValue(
        RATE_LIMITING,
        'CONTENT_VELOCITY_WINDOW_MINUTES',
        description=_('Content velocity window (minutes)'),
        default=60,
        help_text=_('Duration of the content velocity window in minutes.')
    )
)
