from django.conf import settings as django_settings
from django.middleware.csrf import _sanitize_token
try:
    from django.middleware.csrf import _get_new_csrf_string
except ImportError:
    from django.middleware.csrf import _get_new_csrf_key as _get_new_csrf_string
