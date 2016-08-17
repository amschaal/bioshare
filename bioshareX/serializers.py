from bioshareX.models import ShareLog, Share, Tag, ShareStats
from rest_framework import serializers
from django.contrib.auth.models import User, Group
from django.core.urlresolvers import reverse
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id','first_name','last_name','email','username')
    def __init__(self, *args, **kwargs):
        self.include_perms = kwargs.pop('include_perms', False)
        super(UserSerializer,self).__init__(*args,**kwargs)
    def to_representation(self, instance):
        data = serializers.ModelSerializer.to_representation(self, instance)
        if self.include_perms:
            data['permissions'] = instance.get_all_permissions()
            groups = Group.objects.all() if instance.is_superuser else instance.groups.all()
            data['groups'] = [{'id':g.id,'name':g.name,'permissions':instance.get_all_permissions(g)} for g in groups]
        return data

class GroupSerializer(serializers.ModelSerializer):
#     def __init__(self, *args, **kwargs):
#         self.include_perms = kwargs.pop('include_perms', False)
#         super(UserSerializer,self).__init__(*args,**kwargs)
    def to_representation(self, instance):
        data = serializers.ModelSerializer.to_representation(self, instance)
        if self.include_perms:
            data['permissions'] = instance.get_all_permissions()
            groups = Group.objects.all() if instance.is_superuser else instance.groups.all()
            data['groups'] = [{'id':g.id,'name':g.name,'permissions':instance.get_all_permissions(g)} for g in groups]
        return data
#         return {
#             'score': obj.score,
#             'player_name': obj.player_name
#         }
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
    url = serializers.SerializerMethodField()
    stats = ShareStatsSerializer(many=False,read_only=True)
    tags = TagSerializer(many=True,read_only=True)
    owner = UserSerializer(read_only=True)
    def get_url(self,obj):
        return reverse('list_directory',kwargs={'share':obj.id})
    class Meta:
        model = Share

