.. _deployment:

================
Deploying Askbot
================

Deploying askbot (assuming that it is already installed) entails:

* collecting static media files
* setting correct file access permissions
* configuring the webserver to work with your application

This document currently explains the configuration under Apache and mod_wsgi_.

Collecting static media files
-----------------------------
Static media must be collected into a single location with a command::

    python manage.py collectstatic

There are several options on where to put the static files - the simplest is 
a local directory, but it is also possible to use a dedicated static files
storage or a CDN, for more information see django documentation about
serving static files.

Cache backend for rate limiting
-------------------------------
Askbot's rate limiting stores counters in Django's cache framework (via
``django-ratelimit``). In production you **must** use a shared cache
backend such as Redis or Memcached — in-process or no-op cache backends
are unsafe:

* ``LocMemCache`` (Django's default when ``CACHES`` is not configured) is
  per-worker, so counters are not shared across gunicorn workers and
  clients can exceed the configured limit by a factor of the worker count.
* ``DummyCache`` never stores anything at all, which silently disables
  rate limiting entirely.

Recommended backends (choose one that matches your installed Django
version):

* Django 4.0+: ``django.core.cache.backends.redis.RedisCache``
* Django 3.2+: ``django.core.cache.backends.memcached.PyMemcacheCache``
* Django 3.2+ via third-party packages:
  ``django_redis.cache.RedisCache`` (from ``django-redis``) or
  ``django.core.cache.backends.memcached.PyLibMCCache``.

Avoid the legacy ``django.core.cache.backends.memcached.MemcachedCache``
backend: it was deprecated in Django 3.2 and removed in Django 4.1.

``LocMemCache`` is acceptable only for single-process development servers.

Askbot's ``askbot/setup_templates/settings.py.jinja2`` sets
``CACHES['default']['KEY_PREFIX'] = 'askbot'`` when ``askbot-setup``
generates your ``settings.py``, so a Redis or Memcached cluster may
safely be shared with other applications without key collisions. Note:
the worked ``CACHES`` examples in that template currently reference
older backends and will be refreshed in a follow-up; configure your own
``CACHES`` dict using one of the recommended backends above.

.. _rate-limit-reverse-proxies:

Rate limiting under reverse proxies and multi-worker deployments
----------------------------------------------------------------
Askbot's rate limiting is controlled by two layers stacked together:
the ``django-ratelimit`` library (configured in ``settings.py``) and
Askbot's livesettings (configured in the admin UI). When the two
disagree the disagreement is silent — the admin UI keeps showing rate
limiting as enabled while the library no-ops every request. The three
django-side knobs below are the ones operators must get right;
``manage.py check`` emits stable warning codes (``askbot.W001``,
``askbot.W002``, ``askbot.W003``, ``askbot.W004``, ``askbot.W005``) so
deploy pipelines can fail before traffic hits production **when
``manage.py check`` is invoked with** ``--fail-level=WARNING --deploy``. Without those flags,
Django's default fail-level is ``ERROR`` and these Warning-level checks
are informational. ``askbot.W003`` polices the rate-limit log channel
and is documented in :ref:`rate-limit-log-monitoring`.

**Multiple workers — pick a shared cache.** ``RATELIMIT_USE_CACHE``
(default ``'default'``) names the ``CACHES`` entry used for rate-limit
counters. Under multi-worker deployments this MUST point at a shared
cache (Redis or Memcached); a per-process backend such as
``LocMemCache`` or ``DummyCache`` makes the configured limit
``N × workers`` instead of ``N``. See *Cache backend for rate limiting*
above for backend recommendations. ``manage.py check`` emits
``askbot.W002`` when ``RATELIMIT_USE_CACHE`` resolves to a per-process
backend. ``askbot.W004`` fires when ``RATELIMIT_USE_CACHE`` resolves
to a ``CACHES`` key that is missing or not a dict — django-ratelimit
will raise ``InvalidCacheBackendError`` at the first rate-limited
request.

**Reverse proxy — set RATELIMIT_IP_META_KEY.** Without it,
``django-ratelimit`` reads ``REMOTE_ADDR``, which is the proxy's IP
under nginx / haproxy / ELB. Every visitor then appears to come from
the proxy, so the per-IP request bucket and the registration bucket
degrade to a single global counter, and ``RATE_LIMIT_IP_ALLOWLIST``
matching the proxy IP whitelists the entire internet. For single-hop
nginx::

    RATELIMIT_IP_META_KEY = 'HTTP_X_FORWARDED_FOR'

For multi-hop proxy chains that need to skip trusted intermediaries,
``RATELIMIT_IP_META_KEY`` accepts a callable returning the client IP.

**Master kill switch — RATELIMIT_ENABLE.** Defaults to ``True``. ANY
falsy value (``False``, ``0``, ``''``, ``None``) disables every askbot
rate-limit policy regardless of admin UI state. ``manage.py check``
emits ``askbot.W001`` when a falsy ``RATELIMIT_ENABLE`` contradicts an
enabled livesetting. ``askbot.I001`` (informational) is emitted when
the livesettings DB cannot be reached during the consistency check;
this is expected during fresh bootstrap and does not fail deploy
gates.

**Middleware presence — install RateLimitMiddleware.** ``manage.py
check`` emits ``askbot.W005`` when ``REQUEST_RATE_LIMIT_ENABLED`` is
on in the admin UI but
``askbot.middleware.ratelimit.RateLimitMiddleware`` is missing from
Django's ``MIDDLEWARE`` setting — the admin toggle then has no effect
because no middleware consumes it. Add the middleware ahead of
``askbot.middleware.view_log.ViewLogMiddleware`` so rate-limited
requests are not logged as ordinary traffic, or disable the
livesetting. W005 short-circuits when ``RATELIMIT_ENABLE`` is falsy
so it does not duplicate ``askbot.W001`` for the same underlying
disable.

.. _rate-limit-subnet-keying:

Subnet keying for IP-based rate limits
--------------------------------------
The ``RATE_LIMIT_SUBNET_GRANULARITY`` livesetting (admin UI → "Rate
limiting") controls how broadly IP-keyed limiters group neighbouring
addresses. Three options:

* ``host`` — bucket each IP separately (/32 IPv4, /128 IPv6). Strict.
* ``subnet`` — bucket local-network neighbours together
  (/24 IPv4, /64 IPv6). Recommended default; defends against per-IP
  rotation within one subnet.
* ``region`` — bucket entire regional blocks together
  (/16 IPv4, /48 IPv6). Aggressive.

IPv4 and IPv6 widths always change together — a single setting drives
both families. The cache key for each bucket includes the prefix, so
changing the granularity starts fresh buckets for every client. This
is intentional and is distinct from edits to the IP allowlist (see
:ref:`rate-limit-allowlist`), which short-circuit before the bucket
key is computed and therefore do not invalidate any cached counters.

.. _rate-limit-log-monitoring:

Log monitoring and the log-tailer recipe
----------------------------------------
Each rate-limit hit emits a structured WARNING line on the
``askbot.utils.ratelimit`` logger, anchored on the literal string
``askbot.ratelimit hit `` (trailing space). The emit site is
``askbot/utils/ratelimit.py`` (single emission point inside
``_is_over_limit``). Two rendered examples:

.. code-block:: text

   askbot.ratelimit hit policy=request ip=1.2.3.4 group=askbot.ratelimit.request
   askbot.ratelimit hit policy=request ip=- group=askbot.ratelimit.request

The ``group=`` field is per policy: ``askbot.ratelimit.request``,
``askbot.ratelimit.registration``, and
``askbot.ratelimit.watched_user_post``. Log-tailers anchored on the
older ``askbot.middleware.ratelimit`` / ``askbot.registration``
literals must update to the new strings; recipes anchored on
``policy=`` (including the bundled fail2ban filter below) are
unaffected.

When the limiter cannot resolve a client IP (proxy misconfigured, the
header was anonymized) the IP field renders as ``ip=-``. Log-tailer
recipes must either skip those rows or anchor on a bannable policy so
the actioner is never fed the ``-`` placeholder.

**Exempted endpoints emit nothing.** Views decorated with
``askbot.utils.ratelimit.ratelimit_exempt`` short-circuit the
per-request middleware before any bucket lookup, so they neither
consume a slot nor emit a ``askbot.ratelimit hit`` line. Askbot ships
this mark on the two UI-bookkeeping endpoints whose 429s would break
the user session: ``POST /messages/markread/`` (dismissing the
rate-limit banner) and ``GET /jsi18n/`` (the JavaScript-i18n
catalog). Custom views that should bypass the per-request bucket can
apply the same decorator; only the per-request policy honours it —
the registration policy fires from its own view-level decorator and
is unaffected.

**Bannable-policy choice.** The middleware emits ``policy=request``,
the registration decorator emits ``policy=registration``, and the
watched-user-post check declares ``policy=watched_user_post`` (in
``_POLICIES`` inside ``askbot/utils/ratelimit.py``). Operators who
also want to ban registration spam can broaden their regex to
``policy=(request|registration)``. The ``watched_user_post`` policy
is currently dormant — enforcement lives in
``askbot.views.writers.check_watched_user_post_rate_limit`` and
raises ``PermissionDenied`` rather than emitting an
``askbot.ratelimit hit policy=watched_user_post`` line, so do not
expect that policy in fail2ban regex matches today. The
watched-user-post limiter is content-based and would not be a typical
fail2ban target even once it does emit.

**Two distinct askbot rate-limit loggers.** They are sibling modules,
NOT parent/child. Configure both:

* ``askbot.utils.ratelimit`` — per-hit
  ``askbot.ratelimit hit …`` WARNINGs from ``_is_over_limit`` (the
  log-tailer integration target). ``askbot.W003`` polices this
  logger's effective level.
* ``askbot.middleware.ratelimit`` — one-shot worker-boot WARNINGs
  from ``maybe_warn_misconfig`` (RATELIMIT_ENABLE-vs-livesetting
  contradiction; missing or non-dict ``CACHES`` entry; per-process
  ``RATELIMIT_USE_CACHE``). NOT covered by ``askbot.W003``. These are
  the runtime twin of the W001/W002/W004 system checks; the
  deterministic emission ordering at boot is ``W001 → W002/W004``
  (W002 and W004 are mutually exclusive — see
  ``askbot/middleware/ratelimit.py``).

**Recommended LOGGING.** Askbot ships no default ``LOGGING`` block —
operators add it to their own ``settings.py``. Configure the parent
``askbot`` logger at ``WARNING`` and let Django's default
``propagate=True`` chain catch both children in one entry. Do NOT set
``propagate=False`` on the parent or on either child, or the
parent-only setup silently breaks::

    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'ratelimit_file': {
                'class': 'logging.FileHandler',
                'filename': '/var/log/askbot/ratelimit.log',
            },
        },
        'loggers': {
            'askbot': {
                'handlers': ['ratelimit_file'],
                'level': 'WARNING',
                # propagate defaults to True; do NOT set it to False
                # here or on the askbot.utils.ratelimit /
                # askbot.middleware.ratelimit children.
            },
        },
    }

Pin the level to ``'WARNING'`` — setting it below produces noise, and
setting it above trips ``askbot.W003`` for the
``askbot.utils.ratelimit`` child. Operators who prefer per-module
control can configure ``askbot.utils.ratelimit`` and
``askbot.middleware.ratelimit`` as two separate ``loggers`` entries
instead of configuring the parent.

**Two operator volume knobs:**

1. ``REQUEST_RATE_LIMIT_ENABLED`` livesetting (admin UI) — disables
   the limiter entirely; no events to log.
2. ``LOGGING`` level on the askbot rate-limit loggers — silences
   emission while keeping the limiter active. ``manage.py check``
   raises ``askbot.W003`` if the ``askbot.utils.ratelimit`` logger is
   set above ``WARNING``, so operators do not accidentally mute their
   own attack record. Note that W003 does NOT cover
   ``askbot.middleware.ratelimit`` — muting the misconfig logger is
   silently destructive.

**W003 fail-level.** Like W001/W002/W004/W005, ``askbot.W003`` is a
Warning-level system check. It does NOT fail ``manage.py check``
unless invoked as ``manage.py check --fail-level=WARNING --deploy``
(Django's default ``--fail-level`` is ``ERROR``). The same caveat is
documented for W001/W002/W004/W005 in
:ref:`rate-limit-reverse-proxies`.

**Headline fail2ban recipe.** Drop a ``jail.d`` snippet matching the
anchor and capturing the ``ip=`` field. Two regex variants — pick the
one matching your threat model:

.. code-block:: ini

   # /etc/fail2ban/filter.d/askbot-ratelimit.conf
   [Definition]
   # Request-only ban (recommended starting point).
   failregex = askbot\.ratelimit hit policy=request ip=(?P<host>\S+?)\s
   # Or, to also ban registration spam, replace the line above with:
   # failregex = askbot\.ratelimit hit policy=(request|registration) ip=(?P<host>\S+?)\s

.. code-block:: ini

   # /etc/fail2ban/jail.d/askbot.conf
   [askbot-ratelimit]
   enabled  = true
   filter   = askbot-ratelimit
   logpath  = /var/log/askbot/ratelimit.log
   # findtime / bantime / maxretry are starting points — tune for
   # your threat model.
   findtime = 600
   bantime  = 3600
   maxretry = 5
   action   = iptables-multiport[name=askbot, port="http,https"]

The ``\S+?`` capture handles both IPv4 and IPv6 addresses; a
``[\d.]+`` capture would silently drop every IPv6 hit. Anchoring on
``policy=request`` keeps allowlisted passes (which never emit) and
``ip=-`` placeholder rows out of the actioner's input.

**Other consumers.** Any regex log-tailer works the same way —
CrowdSec, Wazuh, Filebeat → SIEM. There is no askbot-specific
plumbing required beyond the regex anchor above.

**Removal of the bundled ban command.** Earlier branches shipped
``RATE_LIMIT_BAN_ENABLED`` and ``RATE_LIMIT_BAN_COMMAND`` livesettings
that fanned out to a configurable shell command per ban event. Both
are removed; this log-tailer recipe is the supported integration
path.

.. _rate-limit-high-rep-bypass:

High-reputation bypass for the watched-user post limit
------------------------------------------------------

Two livesettings let trusted contributors bypass the watched-user
post rate limit while still being treated as watched for every
other moderation purpose:

* ``RATE_LIMIT_BYPASS_HIGH_REP_USERS`` — master switch. Off by
  default. When on, users at or above the reputation threshold
  below skip the watched-user post limit.
* ``MIN_REP_TO_BYPASS_RATE_LIMIT`` — integer reputation threshold,
  default 200. Only consulted when the master switch is on.

**Scope.** The bypass applies ONLY to the watched-user post limit.
The per-IP ``request`` policy and the ``registration`` policy
remain uniform for everyone — admins, moderators, high-reputation
users, and anonymous traffic are all subject to the same caps.

**Interaction with auto-approval.** Askbot promotes a watched user
out of the watched status when their reputation crosses
``MIN_REP_TO_AUTOAPPROVE_USER``. Once approved, the watched-user
limit no longer applies to them and this bypass is never consulted.
For the bypass to ever take effect, set ``MIN_REP_TO_BYPASS_RATE_LIMIT``
strictly LOWER than ``MIN_REP_TO_AUTOAPPROVE_USER``. The bypass is
useful when auto-approval is set very high (or effectively disabled),
or when an admin has manually re-watched a high-reputation user.

Setting up file access permissions
----------------------------------

Webserver process must be able to write to the following locations within your project::

    log/
    askbot/upfiles

If you know user name or the group name under which the webserver runs,
you can make those directories writable by setting the permissons
accordingly:

For example, if you are using Linux installation of apache webserver running under
group name 'apache' you could do the following::

    cd /path/to/django-project
    cd .. #go one level up
    chown -R yourlogin:apache django-project 
    chmod -R g+w django-project/askbot/upfiles
    chmod -R g+w django-project/log

If your account somehow limits you from running such commands - please consult your
system administrator.

Installation under Apache/mod\_wsgi
------------------------------------

Apache/mod\_wsgi combination is the only type of deployment described in this
document at the moment. mod_wsgi_ is currently the most resource efficient
apache handler for the Python web applications.

The main wsgi script is in the file django.wsgi_
it does not need to be modified

Configure webserver
~~~~~~~~~~~~~~~~~~~~

Settings below are not perfect but may be a good starting point::

    #NOTE: the directory paths used here may be adjusted

    #the following two directories must be both readable and writable by apache
    WSGISocketPrefix /path/to/socket/sock
    WSGIPythonEggs /var/python/eggs

    #the following directory must be readable by apache
    WSGIPythonHome /usr/local

    #NOTE: all urs below will need to be adjusted if
    #settings.FORUM_SCRIPT_ALIAS is anything other than empty string (e.g. = 'forum/')
    #this allows "rooting" forum at http://example.com/forum, if you like

    #replace with 127.0.0.1 with real IP address
    <VirtualHost 127.0.0.1:80>
         ServerAdmin you@example.com
         DocumentRoot /path/to/django-project
         ServerName example.come

         #aliases to serve static media directly
         #will probably need adjustment
         Alias /m/ /path/to/django-project/static/
         Alias /upfiles/ /path/to/django-project/askbot/upfiles/
         <DirectoryMatch "/path/to/django-project/askbot/skins/([^/]+)/media">
            Order deny,allow
            Allow from all
         </DirectoryMatch>
         <Directory "/path/to/django-project/askbot/upfiles">
            Order deny,allow
            Allow from all
         </Directory>
         #must be a distinct name within your apache configuration
         WSGIDaemonProcess askbot2
         WSGIProcessGroup askbot2
         WSGIScriptAlias / /path/to/django-project/django.wsgi
         #make all admin stuff except media go through secure connection
         <LocationMatch "/admin(?!/media)">
         RewriteEngine on
             RewriteRule /admin(.*)$ https://example.com/admin$1 [L,R=301]
             </LocationMatch>
         CustomLog /var/log/httpd/askbot/access_log common
         ErrorLog /var/log/httpd/askbot/error_log
         LogLevel debug
    </VirtualHost>
    #again, replace the IP address
    <VirtualHost 127.0.0.1:443>
         ServerAdmin you@example.com
         DocumentRoot /path/to/django-project
         ServerName example.com
         <LocationMatch "^(?!/admin)">
             RewriteEngine on
             RewriteRule django.wsgi(.*)$ http://example.com$1 [L,R=301]
         </LocationMatch>
         SSLEngine on
         #your SSL keys
         SSLCertificateFile /etc/httpd/ssl.crt/server.crt
         SSLCertificateKeyFile /etc/httpd/ssl.key/server.key
         Alias /admin/media/ /usr/lib/python3.6/site-packages/django/contrib/admin/media/
         WSGIScriptAlias / /path/to/django-project/django.wsgi
         CustomLog /var/log/httpd/askbot/access_log common
         ErrorLog /var/log/httpd/askbot/error_log
    </VirtualHost>

.. _mod_wsgi: http://code.google.com/p/modwsgi/
.. _django.wsgi: http://github.com/ASKBOT/askbot-devel/blob/master/askbot/setup_templates/django.wsgi
