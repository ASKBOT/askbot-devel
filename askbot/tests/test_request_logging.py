"""Tests for request logging middleware."""
from unittest.mock import patch

from django.test import TestCase, RequestFactory

from askbot.tests.utils import with_settings
from askbot.middleware.request_log import RequestLogMiddleware


class RequestLogMiddlewareTests(TestCase):
    """Tests for the request logging middleware."""

    def setUp(self):
        self.factory = RequestFactory()

    def _make_middleware(self, status_code=200):
        response = type('Response', (), {'status_code': status_code})()
        return RequestLogMiddleware(lambda request: response)

    @with_settings(REQUEST_LOG_ENABLED=True, REQUEST_LOG_IGNORE_STATIC=True)
    def test_logs_request(self):
        middleware = self._make_middleware()
        request = self.factory.get('/questions/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        request.user = type('User', (), {
            'is_authenticated': False,
            'username': 'anonymous'
        })()

        with patch('askbot.middleware.request_log.logger') as mock_logger:
            middleware(request)
            mock_logger.info.assert_called_once()
            log_msg = mock_logger.info.call_args[0][0]
            self.assertIn('ip=1.2.3.4', log_msg)
            self.assertIn('method=GET', log_msg)
            self.assertIn('path=/questions/', log_msg)
            self.assertIn('status=200', log_msg)
            self.assertIn('user=anonymous', log_msg)
            self.assertNotIn('ratelimited', log_msg)

    @with_settings(REQUEST_LOG_ENABLED=True, REQUEST_LOG_IGNORE_STATIC=True)
    def test_logs_ratelimited_flag(self):
        middleware = self._make_middleware(status_code=429)
        request = self.factory.get('/questions/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        request._ratelimited = True
        request.user = type('User', (), {
            'is_authenticated': False,
            'username': 'anonymous'
        })()

        with patch('askbot.middleware.request_log.logger') as mock_logger:
            middleware(request)
            log_msg = mock_logger.info.call_args[0][0]
            self.assertIn('ratelimited=true', log_msg)

    @with_settings(REQUEST_LOG_ENABLED=True, REQUEST_LOG_IGNORE_STATIC=True)
    def test_skips_static_paths(self):
        middleware = self._make_middleware()
        request = self.factory.get('/m/default/media/js/utils.js')
        request.META['REMOTE_ADDR'] = '1.2.3.4'

        with patch('askbot.middleware.request_log.logger') as mock_logger:
            middleware(request)
            mock_logger.info.assert_not_called()

    @with_settings(REQUEST_LOG_ENABLED=True, REQUEST_LOG_IGNORE_STATIC=False)
    def test_logs_static_when_not_ignored(self):
        middleware = self._make_middleware()
        request = self.factory.get('/m/default/media/js/utils.js')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        request.user = type('User', (), {
            'is_authenticated': False,
            'username': 'anonymous'
        })()

        with patch('askbot.middleware.request_log.logger') as mock_logger:
            middleware(request)
            mock_logger.info.assert_called_once()

    @with_settings(REQUEST_LOG_ENABLED=True, REQUEST_LOG_IGNORE_STATIC=True)
    def test_x_forwarded_for_logged(self):
        """Request log should use X-Forwarded-For IP when present."""
        middleware = self._make_middleware()
        request = self.factory.get('/questions/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.50'
        request.user = type('User', (), {
            'is_authenticated': False,
            'username': 'anonymous'
        })()

        with patch('askbot.middleware.request_log.logger') as mock_logger:
            middleware(request)
            log_msg = mock_logger.info.call_args[0][0]
            self.assertIn('ip=203.0.113.50', log_msg)
            self.assertNotIn('ip=127.0.0.1', log_msg)

    @with_settings(REQUEST_LOG_ENABLED=False)
    def test_disabled_skips_logging(self):
        middleware = self._make_middleware()
        request = self.factory.get('/questions/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'

        with patch('askbot.middleware.request_log.logger') as mock_logger:
            middleware(request)
            mock_logger.info.assert_not_called()
