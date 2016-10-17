from django.contrib import admin
from .models import *

# Inlines
# -------------------------
class SearchStatusThroughInline(admin.StackedInline):
	model = Search.statuses.through
	extra = 0

class PhotoInline(admin.TabularInline):
	model = Photo
	fields = ('photo_id', ('photo_url', 'expanded_url'))
	extra = 0
	verbose_name_plural = 'Photos'

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

class SearchAdmin(admin.ModelAdmin):
	list_display = ('pk', 'query', 'time_of', 'limit', )
	list_display_links = ('pk', 'query')
	search_fields = ['query']
	list_filter = ['time_of']
	fieldsets = (
		(None, {
			'fields': ('pk', 'query', 'limit', 'retweets', 'time_of'),
		}),
	)
	readonly_fields = ('pk', 'time_of',)
	inlines = [SearchStatusThroughInline]

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
	list_display = ('status_id', 'created_by', 'created_at')
	search_fields = ['created_by__screen_name', 'created_by__name' 'status_id', 'text']
	list_filter = ('created_at',)
	fieldsets = (
		(None, {
			'fields': ('status_id', 'created_by', 'created_at', 'text')
		}),
	)
	inlines = [PhotoInline, SearchStatusThroughInline]

class PhotoAdmin(admin.ModelAdmin):
	list_display = ('photo_id', 'status', 'photo_url')
	search_fields = ['photo_id', 'status__status_id', 'status__created_by__screen_name', 'status__created_by__name']
	fieldsets = (
		(None, {
			'fields': ('status', 'photo_id', ('photo_url', 'expanded_url'), ('height', 'width'))
		}),
	)

# Registering Admin Models
# -------------------------
admin.site.register(Authentication, AuthAdmin)
admin.site.register(TwitterUser, TwitterUserAdmin)
admin.site.register(Status, StatusAdmin)
admin.site.register(Search, SearchAdmin)
admin.site.register(Photo, PhotoAdmin)