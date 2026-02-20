DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'askbot',
        'USER': 'askbot',
        'PASSWORD': 'askbot',
        'HOST': 'postgres',
        'PORT': '5432',
        'TEST': {
            'CHARSET': 'utf8',
        }
    }
}
