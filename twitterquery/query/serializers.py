from rest_framework import serializers
from .models import *

class PhotoSerializer(serializers.ModelSerializer):
	class Meta:
		model = Photo
		fields = '__all__'

class TwitterUserSerializer(serializers.ModelSerializer):
	class Meta:
		model = TwitterUser
		fields = '__all__'

class StatusSerializer(serializers.ModelSerializer):
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