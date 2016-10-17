from django.db import models
from django.contrib.sites.models import Site

from urllib.parse import unquote_plus

class Authentication(models.Model):
	# Value fields
	key = models.CharField(max_length=500)
	secret = models.CharField(max_length=500)
	bearer = models.CharField(max_length=500, blank=True, default='')
	# Model relations
	site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='auth', primary_key=True)

class TwitterUser(models.Model):
	# Value fields
	user_id = models.CharField(max_length=100, primary_key=True)
	screen_name = models.CharField(max_length=50)
	name = models.CharField(max_length=50)
	location = models.CharField(max_length=100, blank=True)
	followers_count = models.PositiveIntegerField()
	profile_image_url = models.URLField()

	def __str__(self):
		return '@'+self.screen_name

class Status(models.Model):
	# Value fields
	status_id = models.CharField(max_length=100, primary_key=True)
	created_at = models.DateTimeField()
	text = models.CharField(max_length=200)
	# Model relations
	created_by = models.ForeignKey(TwitterUser, on_delete=models.CASCADE, related_name='statuses', related_query_name='status')

	def __str__(self):
		return '{}:{}'.format(self.created_by, self.status_id)

	class Meta:
		ordering = ['-status_id']
		verbose_name_plural = 'Statuses'

class Search(models.Model):
	# Value fields
	query = models.CharField(max_length=500)
	limit = models.PositiveIntegerField(default=15)
	# Auto fields
	time_of = models.DateTimeField(auto_now_add=True)
	# Model relations
	statuses = models.ManyToManyField(Status, related_name='searches', related_query_name='search')

	def __str__(self):
		return '{} {}'.format(unquote_plus(self.query), self.time_of.strftime('%Y-%m-%d %H:%M:%S'))

	class Meta:
		ordering = ['-time_of']
		verbose_name_plural = 'Searches'

class Photo(models.Model):
	# Value fields
	photo_id = models.CharField(max_length=100, primary_key=True)
	photo_url = models.URLField()
	expanded_url = models.URLField()
	height = models.PositiveIntegerField()
	width = models.PositiveIntegerField()
	# Model relations
	status = models.ForeignKey(Status, on_delete=models.CASCADE, related_name='photos', related_query_name='photo')