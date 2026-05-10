"""Django system checks for askbot rate-limit configuration.

Registered in ``AskbotConfig.ready()``. Surface misconfigurations in
``manage.py check`` output so deploy pipelines fail before traffic
hits the live container — complements the runtime WARNING emitted in
``askbot.middleware.ratelimit.maybe_warn_misconfig``.
"""
import logging

from django.conf import settings
from django.core.checks import Info, Warning, register

from askbot.utils.ratelimit import PER_PROCESS_CACHE_BACKENDS


@register()
def check_ratelimit_enable_consistency(app_configs, **kwargs):
    """W001: RATELIMIT_ENABLE falsy with any askbot policy enabled."""
    # if django-ratelimit is enabled - then any askbot rate limit settins
    # are acceptable - return no errors
    if getattr(settings, 'RATELIMIT_ENABLE', True):
        return []

    # rate-limit is disabled - therefore all askbot rate limits
    # must be disabled as well
    try:
        # handle the case when livesettings are not available
        from askbot.conf import settings as askbot_settings
        contradicts = any([
            askbot_settings.REQUEST_RATE_LIMIT_ENABLED,
            askbot_settings.REGISTRATION_RATE_LIMIT_ENABLED,
            askbot_settings.WATCHED_USER_POST_RATE_LIMIT_ENABLED,
        ])
    except Exception:
        return [Info(
            'RATELIMIT_ENABLE is falsy but askbot livesettings could '
            'not be read; consistency with admin toggles could not be '
            'verified.',
            hint='This is expected during collectstatic / migrate / '
                 'fresh bootstrap. If it persists during normal worker '
                 'operation, investigate the livesettings DB '
                 'connection.',
            id='askbot.I001',
        )]
    if not contradicts:
        return []
    # warn if any askbot rate limits is enabled when the ratelimit app is disabled
    return [Warning(
        'RATELIMIT_ENABLE is falsy; this disables every askbot '
        'rate-limit livesetting and admin toggles have no effect.',
        hint='Either remove the falsy RATELIMIT_ENABLE from your '
             'django settings, or disable the askbot rate-limit '
             'livesettings in the admin UI to make the configuration '
             'consistent.',
        id='askbot.W001',
    )]


@register()
def check_ratelimit_cache_backend(app_configs, **kwargs):
    """W002/W004: RATELIMIT_USE_CACHE cache-entry shape and backend."""
    cache_name = getattr(settings, 'RATELIMIT_USE_CACHE', 'default')
    caches = getattr(settings, 'CACHES', None) or {}
    cache_entry = caches.get(cache_name)
    shared_w004_hint = (
        f'Either add a CACHES[{cache_name!r}] entry pointing at Redis '
        f'or Memcached, or remove RATELIMIT_USE_CACHE so the limiter '
        f"falls back to CACHES['default']."
    )
    if cache_entry is None:
        return [Warning(
            f'RATELIMIT_USE_CACHE resolves to {cache_name!r}, but '
            f'CACHES has no entry {cache_name!r}. django-ratelimit '
            f'will raise InvalidCacheBackendError at the first '
            f'rate-limited request.',
            hint=shared_w004_hint,
            id='askbot.W004',
        )]
    if not isinstance(cache_entry, dict):
        return [Warning(
            f'RATELIMIT_USE_CACHE resolves to {cache_name!r}, but the '
            f'matching CACHES entry is not a dict; django-ratelimit '
            f'expects a cache configuration dict.',
            hint=shared_w004_hint,
            id='askbot.W004',
        )]
    backend = cache_entry.get('BACKEND', '')
    if not backend.endswith(PER_PROCESS_CACHE_BACKENDS):
        return []
    return [Warning(
        f'RATELIMIT_USE_CACHE={cache_name!r} points at {backend!r}; '
        f'rate-limit counters will be per-process and ineffective '
        f'under multiple workers.',
        hint=(f'Configure CACHES[{cache_name!r}] to use Redis or '
              f'Memcached, or point RATELIMIT_USE_CACHE at a shared '
              f'cache entry.'),
        id='askbot.W002',
    )]


@register()
def check_ratelimit_logger_level(app_configs, **kwargs):
    """W003: askbot.utils.ratelimit logger muted above WARNING.
    Gated on rate limiting being actually enabled — a muted logger has
    no operational impact when no rate-limit hit events are produced,
    so the warning would be pure noise for deployments that leave rate
    limiting off.
    """
    # `RATELIMIT_ENABLE` short-circuit mirrors W001's first guard
    # above; a falsy value bypasses django-ratelimit entirely, so the
    # logger level no longer matters.
    if not getattr(settings, 'RATELIMIT_ENABLE', True):
        return []
    try:
        # Deferred import + broad except mirror W001 — see
        # check_ratelimit_enable_consistency for the rationale on why
        # the except cannot be narrowed. Returning [] silently on read
        # failure is INTENTIONAL: unlike W001 there is no
        # user-supplied signal worth surfacing as Info from logger
        # configuration alone.
        from askbot.conf import settings as askbot_settings
        any_enabled = any([
            askbot_settings.REQUEST_RATE_LIMIT_ENABLED,
            askbot_settings.REGISTRATION_RATE_LIMIT_ENABLED,
            askbot_settings.WATCHED_USER_POST_RATE_LIMIT_ENABLED,
        ])
    except Exception:
        return []
    if not any_enabled:
        return []
    level = logging.getLogger('askbot.utils.ratelimit').getEffectiveLevel()
    if level <= logging.WARNING:
        return []
    return [Warning(
        'Rate-limit logger is muted above WARNING.',
        hint='Set askbot.utils.ratelimit logger to WARNING or lower '
             'in LOGGING; otherwise rate-limit hit events will be '
             'dropped silently and log-tailer integrations '
             '(fail2ban / CrowdSec / Wazuh / Filebeat) will fail.',
        id='askbot.W003',
    )]
