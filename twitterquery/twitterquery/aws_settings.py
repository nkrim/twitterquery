"""
Django aws settings for twitterquery project.
"""

from .shared_settings import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'query',
        'USER': 'twitterquery_db',
        'PASSWORD': '2299>>snared',
        'HOST': 'twitterquery.cpchpntjumj7.us-west.rds.amazonaws.com',
        'PORT': '5432',
    }
}