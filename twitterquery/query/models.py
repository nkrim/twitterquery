from django.contrib.sites.models import Site
from django.db import models

from urllib.parse import unquote_plus

BASE_URL = 'https://twitter.com'

class Authentication(models.Model):
	# Value fields
	key = models.CharField(max_length=500)
	secret = models.CharField(max_length=500)
	bearer = models.CharField(max_length=500, blank=True, default='')
	# Model relations
	site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='auth', primary_key=True)

class TwitterUser(models.Model):
	# Value fields
	user_id = models.BigIntegerField(primary_key=True)
	screen_name = models.CharField(max_length=50)
	name = models.CharField(max_length=50)
	location = models.CharField(max_length=100, blank=True)
	followers_count = models.PositiveIntegerField()
	profile_image_url = models.URLField()

	def user_id_str(self):
		return str(self.user_id)

	def user_url(self):
		return '{}/{}'.format(BASE_URL, self.screen_name)

	def __str__(self):
		return '@'+self.screen_name

	class Meta:
		ordering = ['screen_name']

class Photo(models.Model):
	# Value fields
	photo_id = models.BigIntegerField(primary_key=True)
	photo_url = models.URLField()
	height = models.PositiveIntegerField()
	width = models.PositiveIntegerField()

	def photo_id_str(self):
		return str(self.photo_id)

	def __str__(self):
		return self.photo_id_str()

	class Meta:
		ordering = ['photo_id']

class Status(models.Model):
	# Value fields
	status_id = models.BigIntegerField(primary_key=True)
	created_at = models.DateTimeField()
	text = models.CharField(max_length=200)
	# Model relations
	created_by = models.ForeignKey(TwitterUser, on_delete=models.CASCADE, related_name='statuses', related_query_name='status')
	photos = models.ManyToManyField(Photo, related_name='statuses', related_query_name='status')

	def status_id_str(self):
		return str(self.status_id)

	def status_url(self):
		return '{}/status/{}'.format(self.created_by.user_url(), self.status_id_str())

	def __str__(self):
		return '{}:{}'.format(self.created_by, self.status_id)

	class Meta:
		ordering = ['-status_id']
		verbose_name_plural = 'Statuses'

class Search(models.Model):
	# Value fields
	query = models.CharField(max_length=500)
	max_id = models.BigIntegerField()
	min_id = models.BigIntegerField()
	# Auto fields
	last_accessed = models.DateTimeField(auto_now=True)
	# Model relations
	statuses = models.ManyToManyField(Status, related_name='searches', related_query_name='search')
	next_search = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, related_name='prev_searches', related_query_name='prev_search')

	def __str__(self):
		return '{}:{} [{},{}]'.format(unquote_plus(self.query), self.pk, self.max_id, self.min_id)

	class Meta:
		ordering = ['-max_id']
		verbose_name_plural = 'Searches'

class QueryInstance(models.Model):
	#Value fields
	query = models.CharField(max_length=500)
	limit = models.PositiveIntegerField(default=10)
	max_id = models.BigIntegerField()
	success = models.BooleanField(default=False)
	# Auto fields
	time_of = models.DateTimeField(auto_now_add=True)
	# Model relations
	search = models.ForeignKey(Search, on_delete=models.CASCADE, related_name='instances', related_query_name='instance')

	def min_id(self):
		statuses = self.statuses()
		return statuses[-1:].status_id if len(statuses) > 0 else self.max_id

	def statuses(self):
		statuses = []
		search = self.search
		count = 0
		while search and count < self.limit:
			status_slice = search.statuses.all()[:self.limit-count]
			statuses += status_slice
			count += len(status_slice)
			search = search.next_search
		return statuses

	def status_count(self):
		return len(self.statuses())

	def photos(self):
		statuses = self.statuses()
		return Photo.objects.prefetch_related('statuses').filter(status__in=statuses).distinct()

	def photo_count(self):
		return self.photos().count()

	def __str__(self):
		return '{} {}'.format(unquote_plus(self.query), self.time_of.strftime('%Y-%m-%d %H.%M.%S'))

	class Meta:
		ordering = ['-time_of']