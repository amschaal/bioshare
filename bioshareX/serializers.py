from bioshareX.models import ShareLog
from rest_framework import serializers
class ShareLogSerializer(serializers.ModelSerializer):
#     name = serializers.SerializerMethodField()
#     def get_name(self, user):
#         return '%s %s'%(user.first_name,user.last_name)
    paths = serializers.JSONField()
        
    class Meta:
        model = ShareLog
