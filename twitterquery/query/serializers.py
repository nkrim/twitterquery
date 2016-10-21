from rest_framework import serializers
from .models import *

class PhotoSerializer(serializers.ModelSerializer):
	photo_id_str = serializers.CharField()

	class Meta:
		model = Photo
		fields = '__all__'

class TwitterUserSerializer(serializers.ModelSerializer):
	user_id_str = serializers.CharField()
	user_url = serializers.URLField()

	class Meta:
		model = TwitterUser
		fields = '__all__'

class StatusSerializer(serializers.ModelSerializer):
	status_id_str = serializers.CharField()
	status_url = serializers.URLField()
	photos = PhotoSerializer(many=True)
	created_by = TwitterUserSerializer()

	class Meta:
		model = Status
		exclude = ('created_by',)

class SearchSerializer(serializers.ModelSerializer):
	statuses = StatusSerializer(many=True)

	class Meta:
		model = Search
		exclude = ('statuses',)

class QueryInstanceSerializer(serializers.ModelSerializer):
	statuses = StatusSerializer(many=True)
	photo_count = serializers.IntegerField()

	class Meta:
		model = QueryInstance
		exclude = ('search',)