from rest_framework import serializers
from .models import *

class SearchSerializer(serializers.ModelSerializer):
	class Meta:
		model = Search
		fields = '__all__'
		depth = 2

class TwitterUserSerializer(serializers.ModelSerializer):
	class Meta:
		model = TwitterUser
		fields = '__all__'
		read_only_fields = ('user_id',)

class StatusSerializer(serializers.ModelSerializer):
	class Meta:
		model = Status
		fields = '__all__'
		read_only_fields = ('status_id',)
		depth = 1

class PhotoSerializer(serializers.ModelSerializer):
	class Meta:
		model = Photo
		fields = '__all__'
		read_only_fields = ('photo_id',)