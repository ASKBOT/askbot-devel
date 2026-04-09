"""Tests for per-IP rate limiting middleware, registration rate limiting,
and content velocity limiting."""
import time
from unittest.mock import patch

from django.test import TestCase, RequestFactory

from askbot.tests.utils import AskbotTestCase, with_settings
from askbot.middleware.ratelimit import (
    RateLimitMiddleware, _request_log, _registration_log, _lock
)


def _clear_rate_limit_state():
    """Clear the module-level rate limit tracking dicts."""
    with _lock:
        _request_log.clear()
        _registration_log.clear()


class RateLimitMiddlewareTests(TestCase):
    """Tests for the per-IP rate limiting middleware."""

    def setUp(self):
        _clear_rate_limit_state()
        self.factory = RequestFactory()
        self.get_response = lambda request: type(
            'Response', (), {'status_code': 200}
        )()
        self.middleware = RateLimitMiddleware(self.get_response)

    def tearDown(self):
        _clear_rate_limit_state()

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=5,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
    )
    def test_allows_requests_under_limit(self):
        for i in range(5):
            request = self.factory.get('/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200,
                             'Request %d should be allowed' % (i + 1))

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=5,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
    )
    def test_blocks_requests_over_limit(self):
        for i in range(5):
            request = self.factory.get('/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            self.middleware(request)

        # 6th request should be rate limited
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        response = self.middleware(request)
        self.assertEqual(response.status_code, 429)

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=2,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
    )
    def test_x_forwarded_for_used(self):
        """Rate limiter should use X-Forwarded-For header when present."""
        for i in range(2):
            request = self.factory.get('/')
            request.META['REMOTE_ADDR'] = '127.0.0.1'
            request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1'
            self.middleware(request)

        # 3rd request from same forwarded IP should be blocked
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1'
        response = self.middleware(request)
        self.assertEqual(response.status_code, 429)

        # But a request from 127.0.0.1 without forwarded header should pass
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=2,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
    )
    def test_x_forwarded_for_multiple_uses_first(self):
        """When X-Forwarded-For has multiple IPs, use the first one."""
        for i in range(2):
            request = self.factory.get('/')
            request.META['REMOTE_ADDR'] = '127.0.0.1'
            request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1, 10.0.0.2, 10.0.0.3'
            self.middleware(request)

        # 3rd request from same first forwarded IP should be blocked
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1, 10.0.0.2'
        response = self.middleware(request)
        self.assertEqual(response.status_code, 429)

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=2,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
    )
    def test_empty_x_forwarded_for_fallback(self):
        """Empty X-Forwarded-For should fall back to REMOTE_ADDR."""
        for i in range(2):
            request = self.factory.get('/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            request.META['HTTP_X_FORWARDED_FOR'] = ''
            self.middleware(request)

        # Should be blocked by REMOTE_ADDR
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        request.META['HTTP_X_FORWARDED_FOR'] = ''
        response = self.middleware(request)
        self.assertEqual(response.status_code, 429)

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=5,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
    )
    def test_different_ips_tracked_separately(self):
        for i in range(5):
            request = self.factory.get('/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            self.middleware(request)

        # Different IP should still be allowed
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '5.6.7.8'
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=5,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
    )
    def test_sets_ratelimited_attribute(self):
        for i in range(5):
            request = self.factory.get('/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            self.middleware(request)

        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        self.middleware(request)
        self.assertTrue(getattr(request, '_ratelimited', False))

    @with_settings(RATE_LIMIT_ENABLED=False)
    def test_disabled_allows_all(self):
        for i in range(200):
            request = self.factory.get('/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=2,
        RATE_LIMIT_WINDOW_SECONDS=1,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
    )
    def test_window_expiry_resets_count(self):
        for i in range(2):
            request = self.factory.get('/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            self.middleware(request)

        # Should be blocked now
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        response = self.middleware(request)
        self.assertEqual(response.status_code, 429)

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)


class RateLimitWhitelistTests(TestCase):
    """Tests for ASKBOT_INTERNAL_IPS whitelist bypass."""

    def setUp(self):
        _clear_rate_limit_state()
        self.factory = RequestFactory()
        self.get_response = lambda request: type(
            'Response', (), {'status_code': 200}
        )()
        self.middleware = RateLimitMiddleware(self.get_response)

    def tearDown(self):
        _clear_rate_limit_state()

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=2,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
    )
    def test_whitelisted_ip_bypasses_limit(self):
        with self.settings(ASKBOT_INTERNAL_IPS=['10.0.0.1']):
            for i in range(10):
                request = self.factory.get('/')
                request.META['REMOTE_ADDR'] = '10.0.0.1'
                response = self.middleware(request)
                self.assertEqual(response.status_code, 200)


class RegistrationRateLimitTests(TestCase):
    """Tests for per-IP registration rate limiting."""

    def setUp(self):
        _clear_rate_limit_state()
        self.factory = RequestFactory()
        self.get_response = lambda request: type(
            'Response', (), {'status_code': 200}
        )()
        self.middleware = RateLimitMiddleware(self.get_response)

    def tearDown(self):
        _clear_rate_limit_state()

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=100,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
        REGISTRATION_RATE_LIMIT_ENABLED=True,
        REGISTRATION_RATE_LIMIT_PER_IP=3,
        REGISTRATION_RATE_LIMIT_WINDOW_SECONDS=86400,
    )
    def test_allows_registrations_under_limit(self):
        for i in range(3):
            request = self.factory.post('/account/signup/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200,
                             'Registration %d should be allowed' % (i + 1))

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=100,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
        REGISTRATION_RATE_LIMIT_ENABLED=True,
        REGISTRATION_RATE_LIMIT_PER_IP=3,
        REGISTRATION_RATE_LIMIT_WINDOW_SECONDS=86400,
    )
    def test_blocks_registrations_over_limit(self):
        for i in range(3):
            request = self.factory.post('/account/signup/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            self.middleware(request)

        # 4th registration should be blocked
        request = self.factory.post('/account/signup/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        response = self.middleware(request)
        self.assertEqual(response.status_code, 429)

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=100,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
        REGISTRATION_RATE_LIMIT_ENABLED=True,
        REGISTRATION_RATE_LIMIT_PER_IP=3,
        REGISTRATION_RATE_LIMIT_WINDOW_SECONDS=86400,
    )
    def test_get_requests_not_counted(self):
        """GET requests to signup should not count toward registration limit."""
        for i in range(5):
            request = self.factory.get('/account/signup/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=100,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
        REGISTRATION_RATE_LIMIT_ENABLED=True,
        REGISTRATION_RATE_LIMIT_PER_IP=3,
        REGISTRATION_RATE_LIMIT_WINDOW_SECONDS=86400,
    )
    def test_different_ips_tracked_separately(self):
        for i in range(3):
            request = self.factory.post('/account/signup/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            self.middleware(request)

        # Different IP should still be allowed
        request = self.factory.post('/account/signup/')
        request.META['REMOTE_ADDR'] = '5.6.7.8'
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=100,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
        REGISTRATION_RATE_LIMIT_ENABLED=False,
        REGISTRATION_RATE_LIMIT_PER_IP=3,
        REGISTRATION_RATE_LIMIT_WINDOW_SECONDS=86400,
    )
    def test_disabled_allows_all(self):
        for i in range(10):
            request = self.factory.post('/account/signup/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)

    @with_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_WINDOW=100,
        RATE_LIMIT_WINDOW_SECONDS=60,
        RATE_LIMIT_CACHE_SIZE=1000,
        RATE_LIMIT_BAN_ENABLED=False,
        REGISTRATION_RATE_LIMIT_ENABLED=True,
        REGISTRATION_RATE_LIMIT_PER_IP=3,
        REGISTRATION_RATE_LIMIT_WINDOW_SECONDS=86400,
    )
    def test_register_path_also_matched(self):
        """The /account/register/ path should also be rate limited."""
        for i in range(3):
            request = self.factory.post('/account/register/')
            request.META['REMOTE_ADDR'] = '1.2.3.4'
            self.middleware(request)

        request = self.factory.post('/account/register/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        response = self.middleware(request)
        self.assertEqual(response.status_code, 429)


class ContentVelocityTests(AskbotTestCase):
    """Tests for content velocity limiting of watched users."""

    def setUp(self):
        self.watched_user = self.create_user('watched_user', status='w')
        self.approved_user = self.create_user('approved_user', status='a')

    @with_settings(
        CONTENT_VELOCITY_ENABLED=True,
        CONTENT_VELOCITY_MAX_POSTS=3,
        CONTENT_VELOCITY_WINDOW_MINUTES=60,
    )
    def test_watched_user_blocked_over_limit(self):
        from askbot.views.writers import _check_content_velocity
        from django.core import exceptions as django_exceptions

        # Create posts for the watched user
        for i in range(3):
            self.post_question(user=self.watched_user,
                               title='question %d' % i)

        with self.assertRaises(django_exceptions.PermissionDenied):
            _check_content_velocity(self.watched_user)

    @with_settings(
        CONTENT_VELOCITY_ENABLED=True,
        CONTENT_VELOCITY_MAX_POSTS=5,
        CONTENT_VELOCITY_WINDOW_MINUTES=60,
    )
    def test_watched_user_allowed_under_limit(self):
        from askbot.views.writers import _check_content_velocity

        # Create fewer posts than the limit
        for i in range(3):
            self.post_question(user=self.watched_user,
                               title='question %d' % i)

        # Should not raise
        _check_content_velocity(self.watched_user)

    @with_settings(
        CONTENT_VELOCITY_ENABLED=True,
        CONTENT_VELOCITY_MAX_POSTS=3,
        CONTENT_VELOCITY_WINDOW_MINUTES=60,
    )
    def test_approved_user_not_affected(self):
        from askbot.views.writers import _check_content_velocity

        # Create many posts for the approved user
        for i in range(5):
            self.post_question(user=self.approved_user,
                               title='question %d' % i)

        # Should not raise — approved users are not watched
        _check_content_velocity(self.approved_user)

    @with_settings(
        CONTENT_VELOCITY_ENABLED=False,
        CONTENT_VELOCITY_MAX_POSTS=3,
        CONTENT_VELOCITY_WINDOW_MINUTES=60,
    )
    def test_disabled_allows_all(self):
        from askbot.views.writers import _check_content_velocity

        for i in range(10):
            self.post_question(user=self.watched_user,
                               title='question %d' % i)

        # Should not raise when disabled
        _check_content_velocity(self.watched_user)
