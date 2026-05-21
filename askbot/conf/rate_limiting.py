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
        'REQUEST_RATE_LIMIT_ENABLED',
        description=_('Enable rate limiting'),
        default=False,
        help_text=_('Master switch for per-IP request rate limiting.')
    )
)

# RATE_LIMIT_IP_ALLOWLIST and RATE_LIMIT_SUBNET_GRANULARITY are
# cross-policy: the allowlist applies to every limiter, the granularity
# applies to every IP-keyed limiter. They intentionally drop the
# per-scope prefix the other settings use.
settings.register(
    livesettings.StringArrayValue(
        RATE_LIMITING,
        'RATE_LIMIT_IP_ALLOWLIST',
        description=_('Rate-limit allowlist (IPs / CIDR ranges)'),
        default=[],
        help_text=_(
            'IP addresses and CIDR ranges that bypass every rate-limit '
            'policy (request, registration, watched-user-post). One '
            'entry per row. Plain IP (1.2.3.4, 2001:db8::1) or CIDR '
            '(1.2.3.0/24, 2001:db8::/32). IPv4 or IPv6. '
            'Combines with the deploy-time ASKBOT_INTERNAL_IPS django.'
            'Edits apply on the next request and do NOT '
            'invalidate any rate-limit buckets.'
        ),
    )
)

RATE_LIMIT_SUBNET_GRANULARITY_CHOICES = (
    ('host',   _('Individual IP (/32 IPv4, /128 IPv6) — strict')),
    ('subnet', _('Local subnet (/24 IPv4, /64 IPv6) — recommended')),
    ('region', _('Regional block (/16 IPv4, /48 IPv6) — aggressive')),
)
settings.register(
    livesettings.StringValue(
        RATE_LIMITING,
        'RATE_LIMIT_SUBNET_GRANULARITY',
        description=_('Subnet granularity for IP-keyed rate limits'),
        default='subnet',
        choices=RATE_LIMIT_SUBNET_GRANULARITY_CHOICES,
        help_text=_(
            'Controls how broadly IP-keyed rate limits group '
            'addresses. "host" buckets each IP separately (/32 IPv4, '
            '/128 IPv6) — strict. "subnet" buckets local-network '
            'neighbors together (/24 IPv4, /64 IPv6) — recommended '
            'default; "region" buckets entire regional blocks together '
            '(/16 IPv4, /48 IPv6) — aggressive. IPv4 and IPv6 widths '
            'always change together.'
        ),
    )
)

settings.register(
    livesettings.IntegerValue(
        RATE_LIMITING,
        'REQUEST_RATE_LIMIT_MAX_REQUESTS',
        description=_('Max requests per IP per window'),
        default=60,
        help_text=_('Number of requests allowed per IP within a 60-second window.')
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
        'REGISTRATION_RATE_LIMIT_MAX_REGISTRATIONS',
        description=_('Max registrations per IP per window'),
        default=3,
        help_text=_('Number of registrations allowed per IP within a 1-day window.')
    )
)

# --- Watched user post rate limiting ---

settings.register(
    livesettings.BooleanValue(
        RATE_LIMITING,
        'WATCHED_USER_POST_RATE_LIMIT_ENABLED',
        description=_('Enable post rate limiting for watched users'),
        default=False,
        help_text=_('Per-user post limit for watched users to slow '
                    'sophisticated spammers.')
    )
)

settings.register(
    livesettings.IntegerValue(
        RATE_LIMITING,
        'WATCHED_USER_POST_RATE_LIMIT_MAX_POSTS',
        description=_('Max posts per window (watched users)'),
        default=5,
        help_text=_('Maximum posts a watched user can make within a 1-hour window.')
    )
)

# Reputation-based bypass for the watched-user-post limit. Placed
# here (not in askbot/conf/minimum_reputation.py) so every knob that
# tunes rate-limit behavior lives in one admin form.
settings.register(
    livesettings.BooleanValue(
        RATE_LIMITING,
        'RATE_LIMIT_BYPASS_HIGH_REP_USERS',
        description=_('Bypass post rate limit for high-reputation users'),
        default=False,
        help_text=_(
            'Master switch. When on, users whose reputation meets the '
            'threshold below bypass the watched-user post rate limit. '
            'The per-IP request limit and the registration limit are not affected.'
            'Note: askbot also auto-approves watched users once their '
            'reputation crosses MIN_REP_TO_AUTOAPPROVE_USER — for this '
            'bypass to ever take effect, set the threshold below LOWER '
            'than MIN_REP_TO_AUTOAPPROVE_USER. See the deployment doc '
            "section 'rate-limit-high-rep-bypass' for the full "
            'rationale.'
        )
    )
)

settings.register(
    livesettings.IntegerValue(
        RATE_LIMITING,
        'MIN_REP_TO_BYPASS_RATE_LIMIT',
        description=_('Reputation threshold for rate-limit bypass'),
        default=200,
        help_text=_(
            "Only consulted when 'Bypass post rate limit for "
            "high-reputation users' is enabled. Applies ONLY to the "
            'watched-user post limit; the per-IP request limit and the '
            'registration limit are not affected. Set strictly LOWER '
            'than MIN_REP_TO_AUTOAPPROVE_USER — otherwise the bypass '
            'never fires, because askbot promotes reputable users out '
            'of the watched status before this threshold is reached.'
        )
    )
)
