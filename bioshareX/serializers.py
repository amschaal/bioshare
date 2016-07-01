from bioshareX.models import ShareLog, Share, Tag, ShareStats
from rest_framework import serializers
from django.contrib.auth.models import User
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        fields=('first_name','last_name','email','username','id')
        model = User
class ShareLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    paths = serializers.JSONField()
    class Meta:
        model = ShareLog

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag

class ShareStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareStats
        fields = ('num_files','bytes','updated')
        
class ShareSerializer(serializers.ModelSerializer):
    stats = ShareStatsSerializer(many=False,read_only=True)
    tags = TagSerializer(many=True,read_only=True)
    owner = UserSerializer(read_only=True)
    class Meta:
        model = Share

