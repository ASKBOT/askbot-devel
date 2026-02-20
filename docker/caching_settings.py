CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'askbot',
        'KEY_PREFIX': 'askbot',
        'TIMEOUT': 6000,
    }
}
LIVESETTINGS_CACHE_TIMEOUT = CACHES['default']['TIMEOUT']
CACHE_MIDDLEWARE_ANONYMOUS_ONLY = True
CACHE_MIDDLEWARE_SECONDS = 600
