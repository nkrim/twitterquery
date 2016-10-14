from django.core.management.base import BaseCommand, CommandError

from datetime import datetime, timedelta
from pytz import utc
from sys import stderr

from query.models import *

class Command(BaseCommand):
	help = 'Deletes all search entries up until a specified date, and then uncoditionally cleans all status and user objects that have no current reference to a search entry'

	def add_arguments(self, parser):
		parser.add_argument('date', 
							nargs='?',
							default='',
							help='The date up to which search entries will be deleted (leave empty to only clean redundant status and user objects)')
		parser.add_argument('-f', '--format',
							default='%x',
							help='The format string for parsing the `date` argument, defaults to `%x` (more info go to "https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior")')
		parser.add_argument('-t', '--timestamp',
							action='store_true',
							help='If present, the `date` argument will be interpreted as a UTC timestamp representing seconds since Unix epoch (if this flag is present, any format options are ignored)')
		parser.add_argument('-a', '--all',
							action='store_true',
							help='If present, all search entries are deleted, regardless of the `date` argument, the only thing that will be left in the database is the authentication settings')

	def handle(self, *args, **options):
		if options['all']:
			print('Deleting all search entries')
			count, deleted = Search.objects.all().delete()
			print('Search cleaning completed\n\t'+str(count)+' searches deleted')
		else:
			datestring = options['date']
			dateformat = options['format']
			usetimestamp = options['timestamp']
			if datestring != '':
				date = None
				if usetimestamp:
					try:
						timestamp = float(datestring)
						date = datetime.fromtimestamp(timestamp, utc)
					except ValueError:
						printerr('Error: Could not convert string to float: '+datestring)
					except TypeError:
						printerr('Error: Could not get timestamp from float: '+timestamp)
				else:
					try:
						date = datetime.strptime(datestring, dateformat)
					except ValueError:
						printerr('Error: Could not parse `date` argument "'+datestring+'" with format string "'+dateformat+'"')
				if date:
					print('Finding all out-dated search entries')
					count, deleted = Search.objects.filter(time_of__lt=date).delete()
					print('Search cleaning completed\n\t'+str(count)+' searches deleted')
		print('Finding all statuses with no related searches')
		count, deleted = Status.objects.filter(search__isnull=True).delete()
		print('Status cleaning completed\n\t'+str(deleted.get('query.Status',0))+' statuses deleted\n\t'+str(deleted.get('query.Photo',0))+' photos deleted')
		print('Finding all twitter users with no related statuses')
		count, deleted = TwitterUser.objects.filter(status__isnull=True).delete()
		print('Twitter User cleaning completed\n\t'+str(count)+' users deleted')

def printerr(*args, **kwargs):
	print(*args, file=stderr, **kwargs)