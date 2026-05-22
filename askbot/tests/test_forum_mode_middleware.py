"""Integration tests for ForumModeMiddleware's internal-IP bypass.

Coverage focuses on the new CIDR / IPv6 / design-invariant behavior of
the ``ASKBOT_INTERNAL_IPS`` bypass branch in
``askbot.middleware.forum_mode``. Uses the django ``Client`` end-to-end
pattern (matches ``ClosedForumTests`` in
``askbot/tests/test_permission_assertions.py``) so the full middleware
stack — including ``resolve()`` — runs.
"""
from django.conf import settings
from django.test.client import Client
from django.urls import reverse

from askbot.tests.utils import (
    AskbotTestCase,
    skipIf,
    with_settings,
)
from askbot.utils import url_utils
from django.test import override_settings


_SKIP_REASON = 'no ForumModeMiddleware set'
_MIDDLEWARE_KEY = 'askbot.middleware.forum_mode.ForumModeMiddleware'


class ForumModeInternalIpBypassTests(AskbotTestCase):
    """End-to-end coverage of the ``ASKBOT_INTERNAL_IPS`` bypass branch.

    Pinned URL: ``reverse('questions')`` always resolves to an askbot
    view, so the ``is_askbot_view`` short-circuit at the top of
    ``process_request`` does not preempt the IP-bypass branch under
    test.
    """

    def setUp(self):
        self.target_url = reverse('questions')
        self.login_url = url_utils.get_login_url()

    def _client(self, ip):
        return Client(REMOTE_ADDR=ip)

    def _assert_bypass(self, response):
        # Bypass: middleware returns None and the view runs. The
        # questions view returns 200 for anonymous traffic.
        self.assertEqual(response.status_code, 200)

    def _assert_redirected(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response['Location'])

    @skipIf(_MIDDLEWARE_KEY not in settings.MIDDLEWARE, _SKIP_REASON)
    @with_settings(ASKBOT_CLOSED_FORUM_MODE=True)
    @override_settings(ASKBOT_INTERNAL_IPS=['10.0.0.0/8'])
    def test_cidr_match_bypasses_redirect(self):
        response = self._client('10.0.0.5').get(self.target_url)
        self._assert_bypass(response)

    @skipIf(_MIDDLEWARE_KEY not in settings.MIDDLEWARE, _SKIP_REASON)
    @with_settings(ASKBOT_CLOSED_FORUM_MODE=True)
    @override_settings(ASKBOT_INTERNAL_IPS=['10.0.0.0/8'])
    def test_outside_cidr_redirects(self):
        response = self._client('11.0.0.5').get(self.target_url)
        self._assert_redirected(response)

    @skipIf(_MIDDLEWARE_KEY not in settings.MIDDLEWARE, _SKIP_REASON)
    @with_settings(ASKBOT_CLOSED_FORUM_MODE=True)
    @override_settings(ASKBOT_INTERNAL_IPS=['2001:db8::/32'])
    def test_ipv6_match_bypasses_redirect(self):
        response = self._client('2001:db8::1').get(self.target_url)
        self._assert_bypass(response)

    @skipIf(_MIDDLEWARE_KEY not in settings.MIDDLEWARE, _SKIP_REASON)
    @with_settings(ASKBOT_CLOSED_FORUM_MODE=True)
    @override_settings(ASKBOT_INTERNAL_IPS=['2001:db8::/32'])
    def test_outside_ipv6_cidr_redirects(self):
        response = self._client('2001:db9::1').get(self.target_url)
        self._assert_redirected(response)

    @skipIf(_MIDDLEWARE_KEY not in settings.MIDDLEWARE, _SKIP_REASON)
    @with_settings(ASKBOT_CLOSED_FORUM_MODE=True)
    @override_settings(ASKBOT_INTERNAL_IPS=['10.0.0.1'])
    def test_plain_ip_backwards_compatible(self):
        # Pre-fix deploys listing plain IPs continue to bypass.
        response = self._client('10.0.0.1').get(self.target_url)
        self._assert_bypass(response)

    @skipIf(_MIDDLEWARE_KEY not in settings.MIDDLEWARE, _SKIP_REASON)
    @with_settings(ASKBOT_CLOSED_FORUM_MODE=True)
    @override_settings(
        ASKBOT_INTERNAL_IPS=['10.0.0.1'],
        RATELIMIT_IP_META_KEY='HTTP_X_FORWARDED_FOR',
    )
    def test_xff_header_does_not_drive_bypass(self):
        # Design invariant: even with RATELIMIT_IP_META_KEY set to
        # X-Forwarded-For (so the rate limiter consults XFF),
        # closed-forum-mode bypass MUST keep using REMOTE_ADDR.
        client = self._client('10.0.0.1')
        response = client.get(
            self.target_url,
            HTTP_X_FORWARDED_FOR='8.8.8.8',
        )
        self._assert_bypass(response)

    @skipIf(_MIDDLEWARE_KEY not in settings.MIDDLEWARE, _SKIP_REASON)
    @with_settings(
        ASKBOT_CLOSED_FORUM_MODE=True,
        RATE_LIMIT_IP_ALLOWLIST=['5.5.5.5'],
    )
    @override_settings(ASKBOT_INTERNAL_IPS=[])
    def test_livesetting_allowlist_does_not_broaden_bypass(self):
        # Design invariant: RATE_LIMIT_IP_ALLOWLIST is rate-limiter-only.
        # An IP in the livesetting allowlist but NOT in
        # ASKBOT_INTERNAL_IPS must still be redirected.
        response = self._client('5.5.5.5').get(self.target_url)
        self._assert_redirected(response)
