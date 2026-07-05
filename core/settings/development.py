from .base import *

DEBUG = True

# CORS — allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Dev throttle rates — essentially unlimited so local dev & tests aren't rate-limited.
# Mirror the keys in base.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'auth': '999999/minute',
    'user_write': '999999/minute',
    'anon_read': '999999/minute',
    'sustained': '999999/hour',
}

# Console logging for development
LOGGING['root']['level'] = 'DEBUG'
LOGGING['loggers']['django']['level'] = 'INFO'
LOGGING['loggers']['smart_billiard']['level'] = 'DEBUG'
