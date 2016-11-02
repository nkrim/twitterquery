"""
WSGI config for twitterquery project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.9/howto/deployment/wsgi/
"""

import os
import sys

from django.core.wsgi import get_wsgi_application

sys.path.insert(0, '/opt/python/current/app/twitterquery')
#os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twitterquery.aws_settings")

application = get_wsgi_application()
