import os

# --- Overrides from environment variables ---
SECRET_KEY = os.environ.get('SECRET_KEY', SECRET_KEY)
DEBUG = os.environ.get('DEBUG', 'false').lower() in ('1', 'true', 'yes')
_hosts = os.environ.get('ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = [h.strip() for h in _hosts.split(',')]

# --- Email (defaults to console backend — prints to docker logs) ---
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '25'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'false').lower() in ('1', 'true', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@askbot.local')

# --- Whitenoise for static files (no nginx needed) ---
MIDDLEWARE = ('whitenoise.middleware.WhiteNoiseMiddleware',) + tuple(MIDDLEWARE)
# Let WhiteNoise serve django-compressor's runtime-generated CACHE files:
# USE_FINDERS enables CompressorFinder; AUTOREFRESH re-checks the filesystem
# per request so files created after startup are found. Fine for hobby traffic.
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
# Remove old-style setting that conflicts with STORAGES (Django 4.2+)
del DEFAULT_FILE_STORAGE
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

# --- Redis/Valkey cache (overrides locmem default when CACHE_URL is set) ---
_cache_url = os.environ.get('CACHE_URL')
if _cache_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _cache_url,
            'KEY_PREFIX': 'askbot',
            'TIMEOUT': 6000,
        }
    }
    LIVESETTINGS_CACHE_TIMEOUT = CACHES['default']['TIMEOUT']

# --- Django compressor: runtime compression (compress on first request, then cached) ---
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = False

# --- Celery ---
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://valkey:6379/1')
