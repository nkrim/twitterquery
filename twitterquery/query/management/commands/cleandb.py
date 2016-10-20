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
		parser.add_argument('-m', '--merge',
							action='store_true',
							help='If present, forces a check on search entries and merges and overlapping ones. This action is performed before all actions except a full delete from the `-a` flag')
		parser.add_argument('-M', '--mergeonly',
							action='store_true',
							help='If present, performs a merge, and only performs a merge. This has precedence over even the `-a` flag option.')

	def handle(self, *args, **options):
		if options['mergeonly']:
			merge()
			return
		elif options['all']:
			print('Deleting all search entries')
			count, deleted = Search.objects.all().delete()
			print('Search cleaning completed\n\t'+str(count)+' searches deleted')
		else:
			if options['merge']:
				merge()
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
					count, deleted = Search.objects.filter(last_accessed__lt=date).delete()
					print('Search cleaning completed\n\t'+str(count)+' searches deleted')
		print('Finding all statuses with no related searches')
		count, deleted = Status.objects.filter(search__isnull=True).delete()
		print('Status cleaning completed\n\t'+str(count)+' statuses deleted')
		print('Finding all photos with no related statuses')
		count, deleted = Photo.objects.filter(status__isnull=True).delete()
		print('Photo cleaning completed\n\t'+str(count)+' photos deleted')
		print('Finding all twitter users with no related statuses')
		count, deleted = TwitterUser.objects.filter(status__isnull=True).delete()
		print('Twitter User cleaning completed\n\t'+str(count)+' users deleted')

def merge():
	queries = {}
	for s in Search.objects.all():
		q = s.query
		print(q)
		if not q in queries:
			queries[q] = []
		queries[q].append(s)
	for q, searches in queries.items():
		print('Merging searches with query "{}"\n\t{} searches found'.format(q, len(searches)))
		if len(searches) > 1:
			prev = searches[0]
			for i in range(1,len(searches)):
				cur = searches[i]
				if prev.min_id <= cur.max_id:
					print('Merging searches:\n\t{}\n\t{}'.format(prev, cur))
					for i in prev.instances.all():
						i.search = cur
						i.save()
					for s in prev.statuses.all():
						s.searches.add(cur)
					cur.min_id = min(cur.min_id, prev.min_id)
					print('deleting '+str(prev))
					prev.delete()
					prev = cur
					print('saving '+str(prev))
					prev.save()

def printerr(*args, **kwargs):
	print(*args, file=stderr, **kwargs)