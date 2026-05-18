"""Livesettings-aware rate-limit helpers built on top of django-ratelimit.

Bridges django-ratelimit (which wants a static rate string at decoration
time) with Askbot's livesettings (which must be readable and mutable at
request time). Exposes a decorator variant (``askbot_ratelimit``) for
view-level use, a non-decorator variant (``check_askbot_ratelimit``)
for middleware-style call sites that have no view function, a
bool-check primitive (``is_askbot_ratelimited``) for call sites that
need to render their own UX (e.g. a session message + form re-render)
instead of returning the helper's content-negotiated 429 response, and
a view-level opt-out (``ratelimit_exempt``) for UI-bookkeeping
endpoints that must not be subject to the per-request middleware
policy.

Callers pick a policy by name (``policy='request'``, etc.); the policy
table maps each name to its enabled-flag livesetting, max-count
livesetting, and fixed window (from ``askbot.const``). Adding a new
limited surface = adding one entry to ``_POLICIES`` + a matching pair
of settings.
"""
import functools
import ipaddress
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils.cache import patch_vary_headers
from django.utils.module_loading import import_string
from django.utils.translation import ngettext
from django_ratelimit import ALL as _ALL_METHODS
from django_ratelimit.core import is_ratelimited

from askbot import const
from askbot.conf import settings as askbot_settings


logger = logging.getLogger(__name__)

_RATELIMITED_RESPONSE_BODY = 'Rate limit exceeded. Please slow down.'


# Per-process Django cache backends — incompatible with multi-worker
# rate limiting. Both the middleware-init WARNING and the
# `manage.py check` `askbot.W002` system check read this tuple, so a
# future addition (e.g. a third per-process backend) updates both
# surfaces in one place.
PER_PROCESS_CACHE_BACKENDS = ('LocMemCache', 'DummyCache')


# Subnet granularity dispatch table. The dropdown livesetting
# RATE_LIMIT_SUBNET_GRANULARITY pairs IPv4 and IPv6 prefix widths so
# admins cannot mismatch them. The map is module-private (single
# consumer: _current_prefixes) and intentionally skips a per-row
# constant for each pair — the names already live in
# RATE_LIMIT_SUBNET_GRANULARITY_CHOICES on conf/rate_limiting.py.
_GRANULARITY_TO_PREFIXES = {
    'host':   (32, 128),
    'subnet': (24, 64),
    'region': (16, 48),
}


def _current_prefixes():
    """Resolve the active (ipv4_prefix, ipv6_prefix) pair.

    Reads ``RATE_LIMIT_SUBNET_GRANULARITY`` per-call so admin toggles
    apply on the next request. An unknown value (e.g. a rolled-back
    migration that left a stale string in DB) falls back to the
    'subnet' default rather than crashing — `livesettings.StringValue`
    enforces `choices` only at the admin-form layer, so the DB layer
    can hold arbitrary strings.
    """
    granularity = askbot_settings.RATE_LIMIT_SUBNET_GRANULARITY
    return _GRANULARITY_TO_PREFIXES.get(granularity, (24, 64))


def resolve_request_ip(request):
    """Return the client IP string for ``request``.

    Mirrors ``django_ratelimit.core._get_ip``'s lookup precedence so
    ``subnet_ip_key`` and ``is_allowlisted`` agree with the rest of
    django-ratelimit on what "the client IP" means under reverse-proxy
    setups. Four deliberate divergences:

    1. **No mask.** ``_get_ip`` always applies an IPv4/IPv6 mask before
       returning a network address. We return the raw IP and let the
       caller (``subnet_ip_key`` / ``is_allowlisted``) apply its own
       prefix from the granularity livesetting.
    2. **Multi-hop XFF splitting.** ``_get_ip`` reads
       ``request.META[ip_meta]`` raw — it does not split a
       comma-separated ``HTTP_X_FORWARDED_FOR``. We split and take
       the first entry, preserving PR 959's middleware behavior.
    3. **Graceful fallback on a missing META key.** ``_get_ip`` raises
       ``ImproperlyConfigured`` when the configured key is absent. We
       return ``''`` instead, so ``subnet_ip_key``'s sentinel branch
       keeps the request flowing when an admin misconfigures one
       proxy hop.
    4. **Defensive ``getattr``.** ``RATELIMIT_IP_META_KEY`` is read via
       ``getattr(settings, 'RATELIMIT_IP_META_KEY', None)`` so this
       helper runs cleanly before the project-level setting is wired
       in (helper-level tests / staged rollout).
    """
    ip_meta = getattr(settings, 'RATELIMIT_IP_META_KEY', None)

    if not ip_meta:
        raw = request.META.get('REMOTE_ADDR', '')
    elif callable(ip_meta):
        raw = ip_meta(request)
    elif isinstance(ip_meta, str) and '.' in ip_meta:
        # Dotted-path string → import and call. The `'.' in ip_meta`
        # check is the discriminator that separates a dotted import
        # path (e.g. 'myproj.utils.get_ip') from a META-key string
        # (e.g. 'HTTP_X_FORWARDED_FOR'). Matches _get_ip exactly.
        raw = import_string(ip_meta)(request)
    else:
        # Plain META key. .get(..., '') over bracket access so a
        # misconfigured proxy header degrades to fallback rather
        # than raising.
        raw = request.META.get(ip_meta, '')

    if not raw:
        return ''

    # Multi-hop XFF: take the first entry, stripped.
    return raw.split(',', 1)[0].strip()


def subnet_ip_key(group, request):
    """``key=`` callable: bucket a request by subnet network.

    Wired into every row of ``_POLICIES`` as the policy's ``'key'``;
    no longer imported by production call sites — kept public for the
    ``SubnetIpKeyTests``, ``AllowlistTests``, and
    ``SubnetGranularityTests`` unit-level coverage.

    Resolves the client IP via ``resolve_request_ip`` (so it honors
    ``RATELIMIT_IP_META_KEY``), normalizes IPv4-mapped IPv6 addresses
    to plain IPv4 (so ``::ffff:1.2.3.4`` from a dual-stack server
    buckets at IPv4 width), and returns the network string at the
    currently-configured granularity. On unparseable input, returns
    a per-request unique sentinel — never ``None``, never the raw
    value, never a shared empty-string bucket.

    **Sentinel rationale.** ``django-ratelimit`` does not have a
    None-as-skip convention for key callables: ``_get_window`` calls
    ``value.encode('utf-8')`` on the result, so ``None`` would crash
    the request. Falling back to the raw IP would collapse every
    parse-failure (anonymized headers, misconfigured proxies) into one
    shared bucket, silently imposing a global rate limit. The
    per-request ``f'invalid:{id(request)}'`` sentinel degrades to
    "unbucketed" — each unparseable request gets its own slot.

    **id(request) lifetime caveat.** ``id()`` is unique only for the
    lifetime of the live object. Within a single request flow the
    request object stays alive while ``subnet_ip_key`` runs and any
    cache writes settle, so the key is stable for that request.
    Across requests an id may be reused after GC, but the cache
    window plus the rarity of unparseable IPs makes any collision
    benign.
    """
    raw = resolve_request_ip(request)
    if not raw:
        return f'invalid:{id(request)}'

    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return f'invalid:{id(request)}'

    # Dual-stack server: ::ffff:1.2.3.4 buckets at IPv4 width.
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped

    ipv4_prefix, ipv6_prefix = _current_prefixes()
    prefix = ipv4_prefix if isinstance(addr, ipaddress.IPv4Address) else ipv6_prefix
    # strict=False masks host bits so the IP buckets to its containing
    # network (1.2.3.4/24 -> 1.2.3.0/24) instead of raising.
    return str(ipaddress.ip_network(f'{addr}/{prefix}', strict=False))


def _get_allowlist_networks():
    """Return the union of parsed allowlist networks.

    Sources: the ``ASKBOT_INTERNAL_IPS`` django setting (deploy-time)
    and the ``RATE_LIMIT_IP_ALLOWLIST`` livesetting (runtime). Plain
    IPs are auto-promoted to /32 or /128 by ``ip_network`` natively,
    so existing ``ASKBOT_INTERNAL_IPS=['10.0.0.1']`` deployments
    continue to work. Invalid entries log at WARNING and are skipped
    — a typo in admin config never raises.

    No ``request`` parameter and no per-request cache: parsing two
    short lists per request is cheaper than the bookkeeping a cache
    would require.
    """
    networks = []
    raw_entries = []

    internal_ips = getattr(settings, 'ASKBOT_INTERNAL_IPS', None) or []
    raw_entries.extend(internal_ips)

    livesetting_entries = getattr(
        askbot_settings, 'RATE_LIMIT_IP_ALLOWLIST', None
    ) or []
    raw_entries.extend(livesetting_entries)

    for entry in raw_entries:
        if not isinstance(entry, str):
            logger.warning(
                'Invalid rate-limit allowlist entry %r (not a string), skipping.',
                entry,
            )
            continue
        cleaned = entry.strip()
        if not cleaned:
            continue
        try:
            networks.append(ipaddress.ip_network(cleaned, strict=False))
        except ValueError:
            logger.warning(
                'Invalid rate-limit allowlist entry %r, skipping.',
                cleaned,
            )
    return networks


def is_allowlisted(request):
    """True iff the request's client IP matches any allowlist entry.

    Public name (no leading underscore) because this helper is
    imported across module boundaries — ``askbot/views/writers.py``
    calls it directly to short-circuit the watched-user-post limiter.

    Honors ``RATELIMIT_IP_META_KEY`` (via ``resolve_request_ip``) and
    applies the same IPv4-mapped IPv6 normalization as
    ``subnet_ip_key`` so an admin who allowlists ``1.2.3.4``
    correctly bypasses dual-stack ``::ffff:1.2.3.4`` traffic.
    """
    raw = resolve_request_ip(request)
    if not raw:
        return False

    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return False

    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped

    for network in _get_allowlist_networks():
        if addr in network:
            return True
    return False


def get_internal_ip_networks():
    """Parsed networks from the ASKBOT_INTERNAL_IPS django setting only.

    Mirrors _get_allowlist_networks's parsing (plain IPs auto-promoted
    to /32 or /128, invalid entries logged at WARNING and skipped) but
    excludes the RATE_LIMIT_IP_ALLOWLIST livesetting — closed-forum-mode
    bypass is a deploy-time-only concern. The setting may be a list or
    tuple of strings (intranet-setup.rst documents it as a tuple);
    iteration handles both.
    """
    networks = []
    internal_ips = getattr(settings, 'ASKBOT_INTERNAL_IPS', None) or []
    for entry in internal_ips:
        if not isinstance(entry, str):
            logger.warning(
                'Invalid ASKBOT_INTERNAL_IPS entry %r (not a string), skipping.',
                entry,
            )
            continue
        cleaned = entry.strip()
        if not cleaned:
            continue
        try:
            # strict=False masks host bits so the IP buckets to its containing
            # network (1.2.3.4/24 -> 1.2.3.0/24) instead of raising.
            networks.append(ipaddress.ip_network(cleaned, strict=False))
        except ValueError:
            logger.warning(
                'Invalid ASKBOT_INTERNAL_IPS entry %r, skipping.',
                cleaned,
            )
    return networks


def is_internal_ip(raw_ip):
    """True iff raw_ip matches an entry in ASKBOT_INTERNAL_IPS.

    Accepts plain IPv4/IPv6 and CIDR entries in the setting. IPv4-mapped
    IPv6 addresses (``::ffff:1.2.3.4``) are normalized to plain IPv4 so
    a deploy that lists ``1.2.3.4`` matches dual-stack traffic. Returns
    False on empty / unparseable input.

    Caller passes a clean IP (typically ``request.META['REMOTE_ADDR']``,
    set by Django from the socket and free of whitespace). This helper
    does NOT strip ``raw_ip`` — unlike ``is_allowlisted``, which goes
    through ``resolve_request_ip`` for XFF-aware splitting and
    stripping. If you ever wire this into a code path that reads
    user-controlled headers, pre-strip at the call site.
    """
    if not raw_ip:
        return False
    try:
        addr = ipaddress.ip_address(raw_ip)
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    for network in get_internal_ip_networks():
        if addr in network:
            return True
    return False


# Policy table: policy name -> (enabled_setting, rate_setting, window_seconds).
# Each row bundles the three values that always travel together for one
# rate-limited surface, so call sites pass a single `policy=` kwarg
# instead of re-listing them (and risking a mismatched pairing).
#
# `window_seconds` is a fixed module constant (not a livesetting) per
# askbot-master-ct9. `rate_setting` holds the name of the livesetting
# whose integer value is the max count for the window.
_POLICIES = {
    'request': {
        'enabled_setting': 'REQUEST_RATE_LIMIT_ENABLED',
        'rate_setting': 'REQUEST_RATE_LIMIT_MAX_REQUESTS',
        'window_seconds': const.REQUEST_RATE_LIMIT_WINDOW_SECONDS,
        'group': 'askbot.ratelimit.request',
        'key': subnet_ip_key,
        'methods': _ALL_METHODS,
    },
    'registration': {
        'enabled_setting': 'REGISTRATION_RATE_LIMIT_ENABLED',
        'rate_setting': 'REGISTRATION_RATE_LIMIT_MAX_REGISTRATIONS',
        'window_seconds': const.REGISTRATION_RATE_LIMIT_WINDOW_SECONDS,
        'group': 'askbot.ratelimit.registration',
        'key': subnet_ip_key,
        'methods': ['POST'],
    },
    'watched_user_post': {
        'enabled_setting': 'WATCHED_USER_POST_RATE_LIMIT_ENABLED',
        'rate_setting': 'WATCHED_USER_POST_RATE_LIMIT_MAX_POSTS',
        'window_seconds':
            const.WATCHED_USER_POST_RATE_LIMIT_WINDOW_SECONDS,
        'group': 'askbot.ratelimit.watched_user_post',
        'key': subnet_ip_key,
        'methods': _ALL_METHODS,
    },
}


def _resolve_policy(policy):
    try:
        return _POLICIES[policy]
    except KeyError:
        valid = ', '.join(sorted(_POLICIES))
        raise ValueError(
            f'Unknown rate-limit policy {policy!r}. Valid: {valid}.'
        )


def _is_over_limit(request, *, policy, policy_spec):
    """Core evaluation shared by decorator + check variant.

    Returns True iff enabled and over limit. Emits a structured
    WARNING on the ``askbot.utils.ratelimit`` logger per rate-limit
    hit (the stable ``askbot.ratelimit hit `` prefix is what
    log-tailer integrations match against).
    """
    # INVARIANT: the enabled-flag check MUST run before is_ratelimited().
    # Short-circuiting here guarantees that flipping the livesetting off
    # never leaves stale bucket state visible — when disabled we never
    # consult the cache, so a previously-exhausted bucket cannot cause
    # a false positive after admin flips enabled=False.
    if not getattr(askbot_settings, policy_spec['enabled_setting']):
        return False

    # Allowlist short-circuit: trusted IPs never touch the cache. Same
    # invariant style as the enabled-flag check above. The watched-
    # user-post limiter (DB-backed, lives in writers.py) applies the
    # same is_allowlisted check at its own call site.
    if is_allowlisted(request):
        return False

    max_count = getattr(askbot_settings, policy_spec['rate_setting'])
    rate = f"{max_count}/{policy_spec['window_seconds']}s"

    limited = is_ratelimited(
        request,
        group=policy_spec['group'],
        key=policy_spec['key'],
        rate=rate,
        method=policy_spec['methods'],
        increment=True,
    )
    if limited:
        logger.warning(
            'askbot.ratelimit hit policy=%s ip=%s group=%s',
            policy, resolve_request_ip(request) or '-',
            policy_spec['group'],
        )
    return limited


def _humanize_seconds(seconds):
    """Render a duration in seconds as a translated human string.

    Picks the largest unit that fits cleanly (hour / minute / second).
    For mixed values like 90 seconds, rounds down to the larger unit
    ("1 minute") — Retry-After is already a worst-case overestimate
    so a coarse hint is fine.
    """
    if seconds >= 3600:
        hours = seconds // 3600
        return ngettext('%(count)d hour', '%(count)d hours', hours) % {
            'count': hours,
        }
    if seconds >= 60:
        minutes = seconds // 60
        return ngettext(
            '%(count)d minute', '%(count)d minutes', minutes,
        ) % {'count': minutes}
    return ngettext(
        '%(count)d second', '%(count)d seconds', seconds,
    ) % {'count': seconds}


def _wants_json(request):
    """Heuristic for machine callers.

    Priority order:
    1. Explicit ``X-Requested-With: XMLHttpRequest`` header (jQuery
       idiom used throughout Askbot's frontend). This header wins
       even if ``Accept: text/html`` is also set — jQuery callers
       routinely send both and expect JSON back.
    2. ``Accept`` header prefers JSON AND does not accept HTML.

    Why ``accepts_json AND NOT accepts_html``: ``request.accepts()``
    in Django 4.x returns True for ``*/*`` — the curl/old-client
    default — and also for a missing ``Accept`` header (Django treats
    that as ``*/*``). A naive ``accepts_json`` check would regress
    browsers whose Accept list contains ``*/*`` somewhere into JSON
    rendering. Requiring JSON to be preferred *over* HTML is the
    conservative default that keeps browsers on the HTML path.

    Edge case (mixed q-values): an Accept header like
    ``application/json;q=0.9,text/html;q=0.5`` semantically prefers
    JSON, but ``request.accepts()`` does not surface q-values — both
    return True, so this helper picks HTML. Acceptable trade-off:
    such clients are rare, and they always have the
    ``X-Requested-With`` escape hatch.

    Note: ``HttpRequest.accepts()`` was added in Django 4.1. The
    floor bump in pyproject.toml (>=4.2) makes this safe.
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    accepts_json = request.accepts('application/json')
    accepts_html = request.accepts('text/html')
    return accepts_json and not accepts_html


def _build_429(request, *, retry_after):
    """Build a content-negotiated 429 response.

    JSON for AJAX/API callers (``X-Requested-With: XMLHttpRequest`` or
    Accept prefers JSON over HTML), HTML for everyone else. Both
    variants carry a ``Retry-After`` header (seconds) and a
    ``Vary: Accept, X-Requested-With`` so caches that key 429s key
    them on the negotiating headers.
    """
    if _wants_json(request):
        response = JsonResponse(
            {
                'error': 'rate_limited',
                'message': _RATELIMITED_RESPONSE_BODY,
                'retry_after': retry_after,
            },
            status=429,
        )
    else:
        # Template name is '429.html', NOT 'askbot/429.html' — matches
        # the idiom used for '404.html' (see askbot/views/meta.py).
        html = render_to_string(
            '429.html',
            {
                'retry_after': retry_after,
                'retry_after_human': _humanize_seconds(retry_after),
            },
            request=request,
        )
        response = HttpResponse(html, status=429)
    # Conservative overestimate: window_seconds is the worst case.
    # django-ratelimit does not expose precise seconds-until-reset.
    response['Retry-After'] = str(retry_after)
    # Use patch_vary_headers (additive) instead of `response['Vary']
    # = ...` (overwriting). Django may set other Vary entries
    # internally on JsonResponse/HttpResponse, and raw assignment
    # would silently drop them.
    patch_vary_headers(response, ['Accept', 'X-Requested-With'])
    return response


def askbot_ratelimit(*, policy):
    """Decorator variant. Wraps a Django view.

    ``policy`` is a key into ``_POLICIES`` that selects the
    enabled-flag livesetting, max-count livesetting, fixed window,
    bucket group string, key callable, and HTTP-method filter for the
    limited surface. Livesettings are read per-request, so admin
    toggles apply live. The policy IS the bucket discriminator: two
    decorators with the same ``policy=`` share a bucket without
    further configuration. To restrict bucket counting to a different
    set of HTTP methods, add a new ``_POLICIES`` row.
    """
    policy_spec = _resolve_policy(policy)
    window = policy_spec['window_seconds']

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if _is_over_limit(
                request,
                policy=policy,
                policy_spec=policy_spec,
            ):
                return _build_429(request, retry_after=window)
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def ratelimit_exempt(view_func):
    """Mark a view as exempt from the per-request rate-limit middleware.

    Mirrors the ``csrf_exempt`` idiom: stamps an attribute on the view
    function and returns it unchanged — no inner wrapper, no
    ``functools.wraps``. This keeps the function identity intact
    (``ratelimit_exempt(view) is view``) and lets ``__name__`` and
    ``__doc__`` carry over trivially.

    Contract:

    * Sets ``view_func.askbot_ratelimit_exempt = True`` (the literal
      ``True`` sentinel, not just any truthy value). ``RateLimitMiddleware``
      reads the attribute with ``is True`` — strict identity — so a
      future drift to ``= 1`` / ``= 'yes'`` fails closed.

    * Exempts only the per-request middleware policy. The
      ``registration`` policy is opt-in at the view layer via
      ``@askbot_ratelimit(policy='registration')`` and
      ``watched_user_post`` is enforced by a separate DB-count helper —
      neither is affected by this decorator. A view may still carry
      ``@askbot_ratelimit(policy='registration')`` alongside
      ``@ratelimit_exempt``; the two are orthogonal.

    * Apply as the OUTERMOST decorator on the view (listed first /
      topmost in source order). Many Django decorators use
      ``functools.wraps``, which updates the wrapper's ``__dict__``
      from the wrapped function and therefore carries this attribute
      up — so in practice the attribute often survives common inner
      wrappers (``csrf_protect``, ``csrf_exempt``, ``login_required``,
      etc.). But a wrapper that does NOT use ``@wraps`` (or excludes
      ``__dict__`` from ``WRAPPER_UPDATES``) will shadow it. Applying
      this decorator outermost makes the attribute land directly on
      the callable returned by URL resolution and is robust to any
      inner wrapper.
    """
    view_func.askbot_ratelimit_exempt = True
    return view_func


def check_askbot_ratelimit(request, *, policy):
    """Non-decorator variant for middleware.

    Returns an ``HttpResponse`` (429) if the request is over the limit,
    or ``None`` otherwise. The bucket discriminator and the HTTP-method
    filter are the per-policy ``'group'`` and ``'methods'`` rows baked
    into ``_POLICIES``.
    """
    policy_spec = _resolve_policy(policy)
    if _is_over_limit(
        request,
        policy=policy,
        policy_spec=policy_spec,
    ):
        return _build_429(
            request, retry_after=policy_spec['window_seconds']
        )
    return None


def is_askbot_ratelimited(request, *, policy):
    """Public bool-check primitive.

    Returns True iff the request is over limit for the given policy
    AND the policy's enabled-flag livesetting is True. When the
    enabled flag is False, returns False without consulting the
    bucket — same short-circuit semantics as the decorator and
    check variant (see ``_is_over_limit``).

    Bucket-increment semantics: every call where the enabled flag is
    True increments the bucket exactly once
    (``django_ratelimit.is_ratelimited(..., increment=True)``). This
    is true regardless of whether the call returns True or False —
    so calling this helper N times under MAX uses N slots. When the
    enabled flag is False, the bucket is NEVER consulted.

    Use this when the call site needs to render its own UX (e.g.
    add a session message and re-render a form) instead of returning
    the helper's content-negotiated 429 response. Use the decorator
    or check variant when the 429 response IS the right UX.
    """
    policy_spec = _resolve_policy(policy)
    return _is_over_limit(
        request,
        policy=policy,
        policy_spec=policy_spec,
    )
