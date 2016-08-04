from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete, pre_save
from django.db.models import Q
from django.conf import settings
import os
from django.utils.html import strip_tags
from bioshareX.utils import test_path, paths_contain, path_contains
from jsonfield import JSONField
import datetime
from guardian.shortcuts import get_users_with_perms

# Create your models here.
def pkgen():
    import string, random
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for x in range(15))

# class BioshareUser(AbstractUser):
#   filesystems = models.ManyToManyField()

class ShareStats(models.Model):
    share = models.OneToOneField('Share',unique=True,related_name='stats')
    num_files = models.IntegerField(default=0)
    bytes = models.BigIntegerField(default=0)
    updated = models.DateTimeField(null=True)
    def hr_size(self):
        from utils import sizeof_fmt
        return sizeof_fmt(self.bytes)
    def update_stats(self):
        from utils import get_share_stats
        from django.utils import timezone
        #         if self.updated is None:
        stats = get_share_stats(self.share)
        self.num_files = stats['files']
        self.bytes = stats['size']
        self.updated = timezone.now()
        self.save()
        
class Filesystem(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField()
    path = models.CharField(max_length=200)
    users = models.ManyToManyField(User, related_name='filesystems')
    def __unicode__(self):
        return '%s: %s' %(self.name, self.path)
class Share(models.Model):
    id = models.CharField(max_length=15,primary_key=True,default=pkgen)
    parent = models.ForeignKey('self',null=True,blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now_add=True,null=True,blank=True)
    owner = models.ForeignKey(User)
    name = models.CharField(max_length=125)
    secure = models.BooleanField(default=True)
    read_only = models.BooleanField(default=False)
    notes = models.TextField()
    tags = models.ManyToManyField('Tag')
    link_to_path = models.CharField(max_length=200,blank=True,null=True)
    sub_directory = models.CharField(max_length=200,blank=True,null=True)
    real_path = models.CharField(max_length=200,blank=True,null=True)
    filesystem = models.ForeignKey(Filesystem, on_delete=models.PROTECT)
    path_exists = models.BooleanField(default=True)
    PERMISSION_VIEW = 'view_share_files'
    PERMISSION_DELETE = 'delete_share_files'
    PERMISSION_DOWNLOAD = 'download_share_files'
    PERMISSION_WRITE = 'write_to_share'
    PERMISSION_LINK_TO_PATH = 'link_to_path'
    PERMISSION_ADMIN = 'admin'
    def __unicode__(self):
        return self.name
    def get_stats(self):
        stats = ShareStats.objects.get_or_create(share=self)[0]
        stats.update_stats()
        return stats
    @staticmethod
    def user_queryset(user,include_stats=True):
        from guardian.shortcuts import get_objects_for_user
        shares = get_objects_for_user(user, 'bioshareX.view_share_files')
        query = Q(id__in=[s.id for s in shares])|Q(owner=user) if user.is_authenticated() else Q(id__in=[s.id for s in shares])
        if include_stats:
            return Share.objects.select_related('stats').filter(query)
        else:
            return Share.objects.filter(query)
    def get_permissions(self,user_specific=False):
        from guardian.shortcuts import get_groups_with_perms
        user_perms = self.get_all_user_permissions(user_specific=user_specific)
        groups = get_groups_with_perms(self,attach_perms=True)
        group_perms = [{'group':{'name':group.name,'id':group.id},'permissions':permissions} for group, permissions in groups.iteritems()]
        return {'user_perms':user_perms,'group_perms':group_perms}
    def get_user_permissions(self,user,user_specific=False):
        if user_specific:
            from utils import fetchall
            perms = fetchall("SELECT p.codename as permission FROM guardian_userobjectpermission uop join auth_user u on uop.user_id = u.id join auth_permission p on uop.permission_id=p.id where uop.object_pk = %s and u.username = %s",[self.id, user.username])
            perms =  [perm[0] for perm in perms]
        else:
            from guardian.shortcuts import get_perms
            if user.username == self.owner.username:
                perms = [perm[0] for perm in self._meta.permissions]
            else:
                perms = get_perms(user, self)
        if not self.secure and not user_specific:
            perms = list(set(perms+['view_share_files','download_share_files']))
        if self.read_only:
            if 'write_to_share' in perms:
                perms.remove('write_to_share')
            if 'delete_share_files' in perms:
                perms.remove('delete_share_files')    
        return perms
    def get_all_user_permissions(self,user_specific=False):
        if not user_specific:
            from guardian.shortcuts import get_users_with_perms
            users = get_users_with_perms(self,attach_perms=True, with_group_users=False)
            user_perms = [{'user':{'username':user.username, 'email':user.email, 'first_name':user.first_name, 'last_name':user.last_name},'permissions':permissions} for user, permissions in users.iteritems()]
        else:
            from utils import dictfetchall
            dict = dictfetchall("SELECT u.username, p.codename as permission FROM guardian_userobjectpermission uop join auth_user u on uop.user_id = u.id join auth_permission p on uop.permission_id=p.id where uop.object_pk = %s",[self.id])
            user_perms={}
            for row in dict:
                if not user_perms.has_key(row['username']):
                    user_perms[row['username']]={'user':{'username':row['username']},'permissions':[]}
                user_perms[row['username']]['permissions'].append(row['permission'])
        return user_perms
    def get_path(self):
        return os.path.join(self.filesystem.path,self.id)
    def get_realpath(self):
        return os.path.realpath(self.get_path())
    def check_path(self):
        return os.path.exists(self.get_path())
    def get_removed_path(self):
        return os.path.join(settings.REMOVED_FILES_ROOT,self.id)
    def get_path_type(self,subpath):
        full_path = os.path.join(self.get_path(),subpath)
        if os.path.isfile(full_path):
            return 'file'
        elif os.path.isdir(full_path):
            return 'directory'
        else:
            return None
    def create_folder(self,name,subdir=None):
        os.umask(settings.UMASK)
        path = self.get_path() if subdir is None else os.path.join(self.get_path(),subdir)
        if os.path.exists(path):
            folder_path = os.path.join(path,name)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
        return folder_path
    def delete_path(self,subpath):
        import shutil
        if subpath is None or subpath == '' or subpath.count('..') != 0:
            return False
        path = os.path.join(self.get_path(),subpath)
        if os.path.exists(path):
            if os.path.isfile(path):
                os.remove(path)
                return True
            elif os.path.isdir(path):
                shutil.rmtree(path)
                return True
        return False
    def add_tags(self,tags,save=True):
        tag_list = []
        for tag in tags:
            tag = tag.strip()
            if len(tag) > 2 :
                tag_list.append(Tag.objects.get_or_create(name=tag)[0])
        self.tags = tag_list
        if save:
            self.save()
    def set_tags(self,tags,save=True):
        print tags
        self.tags.clear()
        self.add_tags(tags,save)
    def move_path(self,item_subpath,destination_subpath=''):
        os.umask(settings.UMASK)
        import shutil
        if destination_subpath.count('..') != 0:
            return False
        destination_path = os.path.join(self.get_path(),destination_subpath)
        item_path = os.path.join(self.get_path(),item_subpath)
        if os.path.exists(destination_path):
            shutil.move(item_path,destination_path)
            return True
        else:
            return False
    def move_share(self,filesystem):
        os.umask(settings.UMASK)
        import shutil
        new_path = os.path.join(filesystem.path, self.id)
        if self.link_to_path and os.path.islink(self.get_path()):
            self.check_link_path()
            self.unlink()
            os.symlink(self.link_to_path,new_path)
        else:
            shutil.move(self.get_path(),new_path)
        self.filesystem = filesystem
    def check_link_path(self):
        if self.parent:
            if not path_contains(self.parent.get_path(), self.link_to_path,real_path=False):
                raise Exception('Subshare must be under the real share.')
        elif self.link_to_path:
            test_path(self.link_to_path,allow_absolute=True)
            if not paths_contain(settings.LINK_TO_DIRECTORIES,self.link_to_path):
                raise Exception('Path not allowed.')
    def create_link(self):
        os.umask(settings.UMASK)
        self.check_link_path()
        if self.link_to_path:
            os.symlink(self.link_to_path,self.get_path())
    def unlink(self):
        path = self.get_path()
        if os.path.islink(path):
            os.unlink(path)
    def create_archive_stream(self,items,subdir=None):
        import zipstream
        from django.http.response import StreamingHttpResponse
    
    
        from settings.settings import ZIPFILE_SIZE_LIMIT_BYTES
        from utils import zipdir, get_total_size
        from os.path import isfile, isdir
        path = self.get_path() if subdir is None else os.path.join(self.get_path(),subdir)
        if not os.path.exists(path):
            raise Exception('Invalid subdirectory provided')
        share_path = self.get_path()
        z = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)
        
        for item in items:
            item_path = os.path.join(path,item)
            if not os.path.exists(item_path):
                raise Exception("File or folder: '%s' does not exist" % (item))
            if isfile(item_path):
                item_name = item#os.path.join(self.id,item)
                z.write(item_path,arcname=item_name)
            elif isdir(item_path):
                zipdir(share_path,item_path,z)
        
        from datetime import datetime
        zip_name = 'archive_'+datetime.now().strftime('%Y_%m_%d__%H_%M_%S')+'.zip'
        response = StreamingHttpResponse(z, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename={}'.format(zip_name)
        return response
Share._meta.permissions = (
            (Share.PERMISSION_VIEW, 'View share files'),
            (Share.PERMISSION_DELETE, 'Delete share files'),
            (Share.PERMISSION_DOWNLOAD, 'Download share files'),
            (Share.PERMISSION_WRITE, 'Write to share'),
            (Share.PERMISSION_LINK_TO_PATH, 'Link to a specific path'),
            (Share.PERMISSION_ADMIN, 'Administer'),
        )    

def share_post_save(sender, **kwargs):
    if kwargs['created']:
        os.umask(settings.UMASK)
        instance = kwargs['instance']
        path = instance.get_path()
        import pwd, grp
        if not os.path.exists(path):
            if instance.link_to_path:
                instance.create_link()
            else:
                from settings.settings import FILES_GROUP, FILES_OWNER
                os.makedirs(path)
                uid = pwd.getpwnam(FILES_OWNER).pw_uid
                gid = grp.getgrnam(FILES_GROUP).gr_gid
        ShareFTPUser.update_share_ftp_users(kwargs['instance'])
        if not instance.real_path:
            instance.real_path = os.path.realpath(instance.get_path())
            instance.save()
#     else:
#         kwargs['instance'].ftp_user.update()
#            os.chown(path, uid, gid)
#            os.chmod(path, int(0775))            
post_save.connect(share_post_save, sender=Share)

@receiver(pre_save, sender=Share)
def share_pre_save(sender, instance, **kwargs):
    try:
        old_share = Share.objects.get(pk=instance.pk)
        if instance.filesystem.pk != old_share.filesystem.pk:
            old_share.move_share(instance.filesystem)
        elif instance.link_to_path and instance.link_to_path != old_share.link_to_path:
            old_share.unlink()
            instance.create_link()
    except Share.DoesNotExist, e:
        pass
        
    
    
# def delete_share(sender, **kwargs):
#     if kwargs['created']:
#         path = kwargs['instance'].get_path()
#         parent_path = os.path.abspath(os.path.join(path,os.pardir))
#         delete_subpath = os.path.join('.deleted',parent_path)
#         import pwd, grp, os, shutil
#         
#         if os.path.exists(path):
#             delete_path = os.path.join(parent_path,'.removed')
#             if not os.path.exists(delete_path):
#                 os.makedirs(delete_path)
#             move_path = os.path.join(delete_path,item)
#             if os.path.exists(move_path):
#                 if os.path.isfile(move_path):
#                     os.remove(move_path)
#                 else:
#                     shutil.rmtree(move_path)
#             shutil.move(path, delete_path)
def share_post_delete(sender, instance, **kwargs):
    path = instance.get_path()
    import shutil
    if os.path.islink(path):
        instance.unlink()
    else:
        if os.path.isdir(path):
            shutil.rmtree(path)
post_delete.connect(share_post_delete, sender=Share)
# class ShareUser(models.Model):
#     share = models.ForeignKey(Share)
#     user = models.ForeignKey(User)
#     date_shared = models.DateTimeField(auto_now_add=True)
#     shared_by = models.ForeignKey(User)

class Tag(models.Model):
    name = models.CharField(blank=False,null=False,max_length=30,primary_key=True)
    def __unicode__(self):
        return self.name
    def to_html(self):
        return '<span class="tag">%s</span>'%self.name
    def clean(self):
        self.name = strip_tags(self.name)
class MetaData(models.Model):
    share = models.ForeignKey(Share)
    subpath = models.CharField(max_length=250,null=True,blank=True)
    notes = models.TextField(blank=True,null=True)
    tags = models.ManyToManyField(Tag)
    class Meta:
        unique_together = (("share", "subpath"),)
    @staticmethod
    def get_or_none(share,subpath):
        try:
            return MetaData.objects.get(share=share,subpath=subpath)
        except MetaData.DoesNotExist:
            return None
#     def get_metadata_json(self,share,subpath):
#         try:
#             return MetaData.objects.get(share=share,subpath=subpath).json()
#         except MetaData.DoesNotExist:
#             return None
    def to_dict(self):
        return {'tags':self.tags.all(),'notes':self.notes}
    def json(self):
        return {'tags':[tag.name for tag in self.tags.all()],'notes':self.notes}
class SSHKey(models.Model):
    user = models.ForeignKey(User)
    name = models.CharField(max_length=50)
    key = models.TextField(blank=False,null=False)
    def create_authorized_key(self):
        key = self.get_key()
        return 'command="%s %s/manage.py rsync %s" ssh-rsa %s %s' % (settings.PYTHON_BIN, settings.CURRENT_DIR, self.user.username, key, self.user.username)
    def get_key(self):
        return self.extract_key(self.key)
    @staticmethod
    def extract_key(full_key):
        import re
        match = re.match('ssh-rsa (?P<key>[A-Za-z0-9\+\/=]{300,}) .*', full_key)
        if match is None:
            raise Exception('Unable to parse key')
        matches = match.groupdict()
        return matches['key']

class ShareFTPUser(models.Model):
    share = models.ForeignKey(Share,related_name="ftp_users")
    user = models.ForeignKey(User,null=True,blank=True)
    password = models.CharField(max_length=15, default=pkgen)
    home = models.CharField(max_length=250)
    @staticmethod
    def create(share,user=None):
        instance = ShareFTPUser.objects.create(share=share)
        instance.home = share.get_path()
        if user:
            instance.user = user
        instance.save()
        return instance
    def update(self,update_password=False):
        self.home = self.share.get_path()
        if update_password:
            self.password = pkgen()
    @staticmethod
    def update_share_ftp_users(share):
        authorized_ids=[share.owner.id]
        for user, permissions in get_users_with_perms(share, attach_perms=True, with_superusers=False, with_group_users=True).iteritems():
            if Share.PERMISSION_VIEW in permissions and Share.PERMISSION_DOWNLOAD in permissions:
                authorized_ids.append(user.id)
        ShareFTPUser.objects.filter(share=share,user__isnull=False).exclude(user__in=authorized_ids).delete()
        for uid in authorized_ids:
            if not ShareFTPUser.objects.filter(share=share,user_id=uid).first():
                ShareFTPUser.create(share,user)
        share_user = ShareFTPUser.objects.filter(share=share,user__isnull=True).first()
        if share.secure and share_user:
            share_user.delete()
        elif not share.secure and not share_user:
            ShareFTPUser.create(share)

class ShareLog(models.Model):
    ACTION_FILE_ADDED = 'File Added'
    ACTION_FOLDER_CREATED = 'Folder Created'
    ACTION_DELETED = 'File(s)/Folder(s) Deleted'
    ACTION_MOVED = 'File(s)/Folder(s) Moved'
    ACTION_RENAMED = 'File/Folder Renamed'
    ACTION_RSYNC = 'Files rsynced'
    ACTION_PERMISSIONS_UPDATED = 'Permissions updated'
    share = models.ForeignKey(Share, related_name="logs")
    user = models.ForeignKey(User, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=30,null=True,blank=True)
    text = models.CharField(max_length=250,null=True,blank=True)
    paths = JSONField()
    @staticmethod
    def create(share,action,user=None,text='',paths=[],subdir=None,share_updated=True):
        if subdir:
            paths = [os.path.join(subdir,path) for path in paths]
        log = ShareLog.objects.create(share=share,user=user,action=action,text=text,paths=paths)
        if share_updated:
            share.updated = datetime.datetime.now()
            share.save()
        return log