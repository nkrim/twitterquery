"""
Django aws settings for twitterquery project.
"""

from .shared_settings import *

import os

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

if 'RDS_HOSTNAME' in os.environ:
	DATABASES = {
	    'default': {
	        'ENGINE': 'django.db.backends.postgresql_psycopg2',
	        'NAME': os.environ['RDS_DB_NAME'],
	        'USER': os.environ['RDS_USERNAME'],
	        'PASSWORD': os.environ['RDS_PASSWORD'],
	        'HOST': os.environ['RDS_HOSTNAME'],
	        'PORT': os.environ['RDS_PORT'],
	    }
	}