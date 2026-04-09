"""Request logging middleware for DDoS monitoring and analysis."""
import logging
import time

from askbot.conf import settings as askbot_settings


logger = logging.getLogger('askbot.request_log')

STATIC_PREFIXES = ('/m/', '/upfiles/')


class RequestLogMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not askbot_settings.REQUEST_LOG_ENABLED:
            return self.get_response(request)

        path = request.path

        # Optionally skip static file paths
        if askbot_settings.REQUEST_LOG_IGNORE_STATIC:
            if any(path.startswith(p) for p in STATIC_PREFIXES):
                return self.get_response(request)

        start = time.monotonic()
        response = self.get_response(request)
        duration = time.monotonic() - start

        # Use X-Forwarded-For when behind a reverse proxy (e.g., nginx)
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ip = forwarded_for.split(',')[0].strip() if forwarded_for else request.META.get('REMOTE_ADDR', '')
        method = request.method
        status = response.status_code
        user = request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous'
        ratelimited = getattr(request, '_ratelimited', False)

        parts = [
            'ip=%s' % ip,
            'method=%s' % method,
            'path=%s' % path,
            'status=%s' % status,
            'time=%.3fs' % duration,
            'user=%s' % user,
        ]
        if ratelimited:
            parts.append('ratelimited=true')

        logger.info(' '.join(parts))

        return response
