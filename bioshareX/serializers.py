from bioshareX.models import ShareLog
from rest_framework import serializers
from django.contrib.auth.models import User
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        fields=('first_name','last_name','email','username','id')
        model = User
class ShareLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
#     name = serializers.SerializerMethodField()
#     def get_name(self, user):
#         return '%s %s'%(user.first_name,user.last_name)
    paths = serializers.JSONField()
        
    class Meta:
        model = ShareLog
