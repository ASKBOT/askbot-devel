"""Per-IP request rate limiting middleware.

Thin shell over ``askbot.utils.ratelimit.check_askbot_ratelimit``:
the helper handles the enabled-flag short-circuit, allowlist
bypass, per-subnet bucketing, content-negotiated 429 response,
and the structured WARNING line emitted to the
``askbot.utils.ratelimit`` logger on every rate-limit hit
(consumed by log-tailer integrations).

The middleware adds one thing on top: a one-shot worker-boot
WARNING when ``CACHES['default']`` is a per-process backend
(``LocMemCache`` / ``DummyCache``), so a deploy that never wired
up a shared cache cannot silently make rate-limit state
per-worker.
"""
import logging

from django.conf import settings

from askbot.conf import settings as askbot_settings
from askbot.utils.ratelimit import (
    PER_PROCESS_CACHE_BACKENDS,
    check_askbot_ratelimit,
)


logger = logging.getLogger(__name__)

MISCONFIG_CHECK_DONE = False


def maybe_warn_misconfig():
    global MISCONFIG_CHECK_DONE
    if MISCONFIG_CHECK_DONE:
        return
    MISCONFIG_CHECK_DONE = True

    # Check 1: master kill switch contradicts admin toggles.
    # Falsy match (not `is False`) so RATELIMIT_ENABLE=0 / '' / None
    # — all of which django-ratelimit treats as disabled at
    # core.py:166 — also fire the warning.
    if not getattr(settings, 'RATELIMIT_ENABLE', True):
        try:
            contradicts = any([
                askbot_settings.REQUEST_RATE_LIMIT_ENABLED,
                askbot_settings.REGISTRATION_RATE_LIMIT_ENABLED,
                askbot_settings.WATCHED_USER_POST_RATE_LIMIT_ENABLED,
            ])
        except Exception:
            # Mirrors checks.py: livesettings DB may be transiently
            # unreachable at worker boot. Suppress and continue to
            # Check 2 — DO NOT crash the worker on a startup hiccup.
            # Wording mirrors askbot.I001 so an operator reading either
            # surface sees the same "couldn't verify" framing.
            logger.info(
                'RATELIMIT_ENABLE is falsy but askbot livesettings '
                'could not be read; consistency with admin toggles '
                'could not be verified.'
            )
            contradicts = False
        if contradicts:
            logger.warning(
                'RATELIMIT_ENABLE is falsy; this overrides every '
                'askbot rate-limit livesetting and admin toggles '
                'will have no effect.'
            )

    # Check 2: actually-used cache, not just `default`.
    # Emission order: W001 → W002/W004. W004 takes the W002 slot when
    # the cache entry is missing or non-dict (the two are mutually
    # exclusive — a missing/non-dict entry can't be a dict-shaped
    # per-process backend).
    cache_name = getattr(settings, 'RATELIMIT_USE_CACHE', 'default')
    caches = getattr(settings, 'CACHES', None) or {}
    cache_entry = caches.get(cache_name)
    if cache_entry is None:
        logger.warning(
            'RATELIMIT_USE_CACHE resolves to %r, but CACHES has no '
            'entry %r. django-ratelimit will raise '
            'InvalidCacheBackendError at the first rate-limited '
            'request.',
            cache_name, cache_name,
        )
        return
    if not isinstance(cache_entry, dict):
        logger.warning(
            'RATELIMIT_USE_CACHE resolves to %r, but the matching '
            'CACHES entry is not a dict; django-ratelimit expects a '
            'cache configuration dict.',
            cache_name,
        )
        return
    backend = cache_entry.get('BACKEND', '')
    # endswith() intentionally false-negatives on custom subclasses
    # (e.g. a user-written `MyLocMemCache`); we warn on the documented
    # Django backend names only.
    if backend.endswith(PER_PROCESS_CACHE_BACKENDS):
        logger.warning(
            'RATELIMIT_USE_CACHE=%r points at %r; rate limiting '
            'state is per-process and limits will be ineffective '
            'under multiple workers.',
            cache_name, backend,
        )


class RateLimitMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response
        maybe_warn_misconfig()

    def __call__(self, request):
        return self.get_response(request)

    # Per-request limiter must run after URL resolution so views can
    # opt out via the askbot_ratelimit_exempt attribute. Do not move
    # this check back into __call__ — the resolved view callable is
    # not available there.
    def process_view(self, request, view_func, view_args, view_kwargs):
        if getattr(view_func, 'askbot_ratelimit_exempt', False) is True:
            return None
        return check_askbot_ratelimit(request, policy='request')
