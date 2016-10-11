from django.core.management.base import BaseCommand, CommandError
from django.contrib.sites.models import Site

from query.models import Authentication

class Command(BaseCommand):
	help = 'Sets the authentication key and secret necessary in order to make requests'

	def handle(self, *args, **options):
		site = Site.objects.get_current()
		if hasattr(site, 'auth'):
			auth = site.auth
		else:
			auth = Authentication(site=site)
		auth.key = input('Consumer key: ')
		auth.secret = input('Consumer secret: ')
		auth.save()
		print('Authentication details succesfully saved')