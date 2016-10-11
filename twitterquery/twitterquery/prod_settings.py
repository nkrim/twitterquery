"""
Django production settings for twitterquery project.
"""

from .shared_settings import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['*']

# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'query',
        'USER': 'query_db',
        'PASSWORD': '8359>>grieced',
        'HOST': 'localhost',
        'PORT': '',
    }
}