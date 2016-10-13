from django.core.management.base import BaseCommand, CommandError

from datetime import datetime, timedelta

from query.models import *

class Command(BaseCommand):
	help = 'Cleans all objects that have no current reference to a search'

	def handle(self, *args, **options):
		print('Finding all out-dated search objects')
		count, deleted = Search.objects.filter(time_of__lt=datetime.today()-timedelta(days=7)).delete()
		print('Search cleaning completed\n\t'+str(count)+' searches deleted')
		print('Finding all statuses with no related searches')
		count, deleted = Status.objects.filter(search__isnull=True).delete()
		print('Status cleaning completed\n\t'+str(deleted.get('query.Status',0))+' statuses deleted\n\t'+str(deleted.get('query.Photo',0))+' photos deleted')
		print('Finding all twitter users with no related statuses')
		count, deleted = TwitterUser.objects.filter(status__isnull=True).delete()
		print('Twitter User cleaning completed\n\t'+str(count)+' users deleted')
