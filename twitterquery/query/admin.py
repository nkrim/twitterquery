from django.contrib import admin
from .models import *

from django.db.models.aggregates import *

# Inlines
# -------------------------
class SearchStatusThroughInline(admin.StackedInline):
	model = Search.statuses.through
	extra = 0
	readonly_fields = ('status','search')

class StatusPhotoThroughInline(admin.TabularInline):
	model = Status.photos.through
	extra = 0

# Admin Models
# -------------------------
class AuthAdmin(admin.ModelAdmin):
	list_display = ('key',)
	fieldsets = (
		(None, {
			'fields': (('key', 'secret'), 'bearer')
		}),
	)
	readonly_fields = ('bearer',)

class QueryInstanceAdmin(admin.ModelAdmin):
	list_display = ('pk', 'query', 'limit', 'status_count', 'photo_count', 'max_id', 'time_of')
	list_display_linkes = ('pk', 'query')
	search_fields = ['query']
	list_filter = ('time_of',)
	fieldsets = (
		(None, {
			'fields': ('pk', ('query', 'limit'), ('max_id', 'time_of'), 'search')
		}),
	)
	readonly_fields = ('pk', 'time_of')

	def status_count(self, obj):
		return obj.statuses().count()

	def photo_count(self, obj):
		return obj.photos().count()

class SearchAdmin(admin.ModelAdmin):
	list_display = ('pk', 'query', 'status_count', 'photo_count', 'max_id', 'min_id', 'last_accessed')
	list_display_links = ('pk', 'query')
	search_fields = ['query']
	fieldsets = (
		(None, {
			'fields': ('pk', 'query', ('max_id', 'min_id'), 'last_accessed'),
		}),
	)
	readonly_fields = ('pk','last_accessed')
	inlines = [SearchStatusThroughInline]

	def status_count(self, obj):
		return obj.statuses.count()

	def photo_count(self, obj):
		return Photo.objects.prefetch_related('status__search').filter(status__search=obj).distinct().count()

class TwitterUserAdmin(admin.ModelAdmin):
	list_display = ('screen_name', 'name', 'user_id')
	search_fields = ['screen_name', 'name', 'user_id']
	fieldsets = (
		(None, {
			'fields': ('screen_name', 'name', 'user_id')
		}),
		('Extra Info', {
			'fields': ('followers_count', 'location', 'profile_image_url')
		}),
	)

class StatusAdmin(admin.ModelAdmin):
	list_display = ('status_id', 'photo_count', 'created_by', 'created_at')
	search_fields = ['created_by__screen_name', 'created_by__name', 'status_id', 'text']
	list_filter = ('created_at',)
	fieldsets = (
		(None, {
			'fields': ('status_id', 'created_by', 'created_at', 'text')
		}),
	)
	inlines = [StatusPhotoThroughInline, SearchStatusThroughInline]

	def photo_count(self, obj):
		return obj.photos.count()

class PhotoAdmin(admin.ModelAdmin):
	list_display = ('photo_id', 'status_count', 'photo_url')
	search_fields = ['photo_id', 'status__status_id', 'status__created_by__screen_name', 'status__created_by__name']
	fieldsets = (
		(None, {
			'fields': ('photo_id', 'photo_url', ('height', 'width'))
		}),
	)
	inlines = [StatusPhotoThroughInline]

	def status_count(self, obj):
		return obj.statuses.count()

# Registering Admin Models
# -------------------------
admin.site.register(Authentication, AuthAdmin)
admin.site.register(TwitterUser, TwitterUserAdmin)
admin.site.register(QueryInstance, QueryInstanceAdmin)
admin.site.register(Status, StatusAdmin)
admin.site.register(Search, SearchAdmin)
admin.site.register(Photo, PhotoAdmin)