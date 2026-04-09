"""Per-IP request rate limiting middleware using an in-memory sliding window."""
import collections
import threading
import time

from django.conf import settings as django_settings
from django.http import HttpResponse

from askbot.conf import settings as askbot_settings


# Module-level state: IP -> deque of timestamps
_request_log = {}
_registration_log = {}
_lock = threading.Lock()


def _cleanup_stale(now, window):
    """Remove IPs that haven't been seen within the window."""
    stale = [ip for ip, times in _request_log.items()
             if not times or (now - times[-1]) > window]
    for ip in stale:
        del _request_log[ip]


def _cleanup_stale_registrations(now, window):
    """Remove IPs that haven't registered within the window."""
    stale = [ip for ip, times in _registration_log.items()
             if not times or (now - times[-1]) > window]
    for ip in stale:
        del _registration_log[ip]


# Registration paths to match (suffix matching for i18n variants)
_REGISTRATION_SUFFIXES = ('/account/signup/', '/account/register/')


class RateLimitMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response
        self._cleanup_counter = 0

    def __call__(self, request):
        if not askbot_settings.RATE_LIMIT_ENABLED:
            return self.get_response(request)

        # Use X-Forwarded-For when behind a reverse proxy (e.g., nginx)
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ip = forwarded_for.split(',')[0].strip() if forwarded_for else request.META.get('REMOTE_ADDR', '')

        # Whitelisted IPs bypass rate limiting
        internal_ips = getattr(django_settings, 'ASKBOT_INTERNAL_IPS', None)
        if internal_ips and ip in internal_ips:
            return self.get_response(request)

        now = time.monotonic()
        window = askbot_settings.RATE_LIMIT_WINDOW_SECONDS
        max_requests = askbot_settings.RATE_LIMIT_REQUESTS_PER_WINDOW
        max_tracked = askbot_settings.RATE_LIMIT_CACHE_SIZE

        with _lock:
            # Periodic cleanup every 1000 requests
            self._cleanup_counter += 1
            if self._cleanup_counter >= 1000:
                self._cleanup_counter = 0
                _cleanup_stale(now, window)
                reg_window = askbot_settings.REGISTRATION_RATE_LIMIT_WINDOW_SECONDS
                _cleanup_stale_registrations(now, reg_window)
                # Evict oldest entries if over capacity
                while len(_request_log) > max_tracked:
                    oldest_ip = min(_request_log,
                                    key=lambda k: _request_log[k][-1]
                                    if _request_log[k] else 0)
                    del _request_log[oldest_ip]

            timestamps = _request_log.get(ip)
            if timestamps is None:
                timestamps = collections.deque()
                _request_log[ip] = timestamps

            # Trim timestamps outside the window
            cutoff = now - window
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            if len(timestamps) >= max_requests:
                # Mark on the request so logging middleware can see it
                request._ratelimited = True

                # Optional ban command
                if askbot_settings.RATE_LIMIT_BAN_ENABLED:
                    ban_cmd = askbot_settings.RATE_LIMIT_BAN_COMMAND
                    if ban_cmd and '{ip}' in ban_cmd:
                        import subprocess
                        try:
                            subprocess.Popen(
                                ban_cmd.format(ip=ip).split(),
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL
                            )
                        except OSError:
                            pass

                return HttpResponse(
                    'Rate limit exceeded. Please slow down.',
                    status=429,
                    content_type='text/plain'
                )

            timestamps.append(now)

            # Registration rate limiting (POST to signup/register paths)
            if (askbot_settings.REGISTRATION_RATE_LIMIT_ENABLED
                    and request.method == 'POST'
                    and any(request.path.endswith(s)
                            for s in _REGISTRATION_SUFFIXES)):
                reg_window = askbot_settings.REGISTRATION_RATE_LIMIT_WINDOW_SECONDS
                reg_max = askbot_settings.REGISTRATION_RATE_LIMIT_PER_IP
                reg_now = now

                reg_timestamps = _registration_log.get(ip)
                if reg_timestamps is None:
                    reg_timestamps = collections.deque()
                    _registration_log[ip] = reg_timestamps

                reg_cutoff = reg_now - reg_window
                while reg_timestamps and reg_timestamps[0] < reg_cutoff:
                    reg_timestamps.popleft()

                if len(reg_timestamps) >= reg_max:
                    return HttpResponse(
                        'Too many registrations. Please try again later.',
                        status=429,
                        content_type='text/plain'
                    )

                reg_timestamps.append(reg_now)

        return self.get_response(request)
