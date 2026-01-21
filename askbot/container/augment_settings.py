# This requires the following environment variables to be set:
# * DATABASE_URL
# * SECRET_KEY
# * CACHE_NODES (,-separated list)
# The following environment variables are optional:
# * CACHE_DB (defaults to 1)
# * CACHE_PASSWORD (defaults to none)

MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'upfiles')
TIME_ZONE = 'Europe/Berlin'

import dj_database_url

db_url = os.environ.get('DATABASE_URL')

if db_url is not None and len(db_url.strip()) > 0:
  DATABASES['default'] = dj_database_url.parse(db_url)
  DATABASES['default'].update({ 'TEST': {
    'CHARSET': 'utf8',  # Setting the character set and collation to utf-8
  }})

SECRET_KEY = os.environ['SECRET_KEY']

CACHES['locmem'] = CACHES['default']
CACHES['redis'] = {
    'BACKEND': 'redis_cache.RedisCache',
    'LOCATION': os.environ['CACHE_NODES'].split(','),
    'OPTIONS': {
        'DB': os.environ.get('CACHE_DB', 1),
        'CONNECTION_POOL_CLASS': 'redis.BlockingConnectionPool',
        'CONNECTION_POOL_CLASS_KWARGS': {
            'max_connections': 50,
            'timeout': 20,
        },
        'MAX_CONNECTIONS': 1000,
        'PICKLE_VERSION': -1,
    },
}

cache_select = os.environ.get('ASKBOT_CACHE', 'locmem')
CACHES['default'] = CACHES[cache_select]

if 'CACHE_PASSWORD' in os.environ and 'OPTIONS' in CACHES['default']:
    CACHES['default']['OPTIONS']['PASSWORD'] = os.environ['CACHE_PASSWORD']
