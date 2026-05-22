==========================================================
Setting up Askbot for use on the closed network (Intranet)
==========================================================

When using Askbot on the Intranet (for example - within your 
Company network), it will be useful to disable references to
all external resources - such as custom fonts, gravatars.

Please change the following settings in your ``settings.py`` file::

    ASKBOT_USE_LOCAL_FONTS=True

In addition, in the "live settings":
* disable gravatar in "settings->User settings"

If you would like to password/protect your site
(achievable via "access control settings" -> "allow only registered users..."),
and at the same time be able to have some dedicated service
to read your site without authentication, add
IPs or CIDR ranges of that service to a tuple ``ASKBOT_INTERNAL_IPS``
in your ``settings.py`` file (see :ref:`rate-limit-allowlist` for
the full value semantics).

.. _rate-limit-allowlist:

Internal IP allowlist
---------------------

``ASKBOT_INTERNAL_IPS`` has a second role: it is the deploy-time
half of the unified rate-limit allowlist. IPs and CIDR ranges listed
here bypass every rate-limit policy (the request, registration, and
watched-user-post limiters). The runtime half of the allowlist is
the ``RATE_LIMIT_IP_ALLOWLIST`` livesetting, editable from the admin
UI under "Rate limiting"; the two sources combine by union (an IP
bypasses if matched by either). Plain IPs are auto-promoted to ``/32``
or ``/128``; CIDR notation is supported on both tiers. The
rate-limiter resolves the client IP through ``RATELIMIT_IP_META_KEY``
(typically ``HTTP_X_FORWARDED_FOR`` behind a reverse proxy), so
allowlist matches respect proxy headers.
