from django.db import models
from django.contrib.auth.models import User, AbstractUser
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete, pre_save
from django.db.models import Q
from settings.settings import FILES_ROOT, ARCHIVE_ROOT, REMOVED_FILES_ROOT
import os
from django.utils.html import strip_tags
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
    archive_path = models.CharField(max_length=200)
    users = models.ManyToManyField(User, related_name='filesystems')
    def __unicode__(self):
        return '%s: %s' %(self.name, self.path)
class Share(models.Model):
    id = models.CharField(max_length=15,primary_key=True,default=pkgen)
    created = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User)
    name = models.CharField(max_length=125)
    secure = models.BooleanField(default=True)
    notes = models.TextField()
    tags = models.ManyToManyField('Tag')
    filesystem = models.ForeignKey(Filesystem, on_delete=models.PROTECT)
    def __unicode__(self):
        return self.name
    class Meta:
        permissions = (
            ('view_share_files', 'View share files'),
            ('delete_share_files', 'Delete share files'),
            ('download_share_files', 'Download share files'),
            ('write_to_share', 'Write to share'),
            ('admin', 'Administer'),
        )
    def get_stats(self):
        stats = ShareStats.objects.get_or_create(share=self)[0]
        stats.update_stats()
        return stats
    @staticmethod
    def user_queryset(user):
        from guardian.shortcuts import get_objects_for_user
        shares = get_objects_for_user(user, 'bioshareX.view_share_files')
        return Share.objects.select_related('stats').filter(Q(id__in=[s.id for s in shares])|Q(owner=user))
    def get_permissions(self,user_specific=False):
        from guardian.shortcuts import get_groups_with_perms
        user_perms = self.get_all_user_permissions(user_specific=user_specific)
        groups = get_groups_with_perms(self,attach_perms=True)
        group_perms = [{'group':{'name':group.name},'permissions':permissions} for group, permissions in groups.iteritems()]
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
        if not self.secure:
            perms = list(set(perms+['view_share_files','download_share_files']))
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
    def get_archive_path(self):
        return os.path.join(self.filesystem.archive_path,self.id)
    def get_removed_path(self):
        return os.path.join(REMOVED_FILES_ROOT,self.id)
    def get_path_type(self,subpath):
        full_path = os.path.join(self.get_path(),subpath)
        if os.path.isfile(full_path):
            return 'file'
        elif os.path.isdir(full_path):
            return 'directory'
        else:
            return None
    def create_folder(self,name,subdir=None):
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
    def move_share(self,filesystem):
        import shutil
#         old_path = self.get_path()
#         temp_dir = "%s_temp" % (old_path)
#         new_path = os.path.join(filesystem.path, self.id)
#         new_archive_path = os.path.join(filesystem.archive_path, self.id)
#         if not os.path.isdir(new_path):
#             os.mkdir(new_path)
#         if not os.path.isdir(new_archive_path):
#             os.mkdir(new_archive_path)
#         shutil.move(old_path, temp_dir)
#         os.symlink(new_path, old_path)
#         shutil.move(temp_dir,new_path)
#         shutil.move(self.get_archive_path(),new_archive_path)
#         self.filesystem = filesystem
#         self.save()
#         os.unlink(old_path)
        new_path = os.path.join(filesystem.path, self.id)
        new_archive_path = os.path.join(filesystem.archive_path, self.id)
        shutil.move(self.get_path(),new_path)
        if os.path.isdir(self.get_archive_path()):
            shutil.move(self.get_archive_path(),new_archive_path)
        self.filesystem = filesystem
#         self.save()
    def create_archive(self,items,subdir=None):
        from settings.settings import ZIPFILE_SIZE_LIMIT_BYTES
        from utils import zipdir, get_total_size
        from os.path import isfile, isdir
        path = self.get_path() if subdir is None else os.path.join(self.get_path(),subdir)
        if not os.path.exists(path):
            raise Exception('Invalid subdirectory provided')
        share_path = self.get_path()
        archive_path = self.get_archive_path()#os.path.join(share_path,'.archives')
        if not os.path.exists(archive_path):
            os.makedirs(archive_path)
        from datetime import datetime
        zip_name = 'archive_'+datetime.now().strftime('%Y_%m_%d__%H_%M_%S')+'.zip'
        zip_path = os.path.join(archive_path,zip_name)
        from zipfile import ZipFile
        archive =  ZipFile(zip_path, 'w')
        size = get_total_size([os.path.join(path,item) for item in items])
        if size > ZIPFILE_SIZE_LIMIT_BYTES:
            raise Exception("%d bytes is above bioshare's limit for creating zipfiles, please use rsync instead" % (size))
        for item in items:
            item_path = os.path.join(path,item)
            if not os.path.exists(item_path):
                raise Exception("File or folder: '%s' does not exist" % (item))
            if isfile(item_path):
                item_name = item#os.path.join(self.id,item)
                archive.write(item_path,arcname=item_name)
            elif isdir(item_path):
                zipdir(share_path,item_path,archive)
        details = {'namelist':archive.namelist(),'name':zip_name}
        archive.close()
        return {'name':zip_name,'subpath':zip_name}
def share_post_save(sender, **kwargs):
    if kwargs['created']:
        path = kwargs['instance'].get_path()
        import pwd, grp, os
        if not os.path.exists(path):
            from settings.settings import FILES_GROUP, FILES_OWNER
            os.makedirs(path)
            uid = pwd.getpwnam(FILES_OWNER).pw_uid
            gid = grp.getgrnam(FILES_GROUP).gr_gid
            os.chown(path, uid, gid)
            os.chmod(path, int(0775))            
post_save.connect(share_post_save, sender=Share)

@receiver(pre_save, sender=Share)
def share_pre_save(sender, instance, **kwargs):
    try:
        old_share = Share.objects.get(pk=instance.pk)
        if instance.filesystem.pk != old_share.filesystem.pk:
            old_share.move_share(instance.filesystem)
    except:
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
def share_post_delete(sender, **kwargs):
    path = kwargs['instance'].get_path()
    archive_path = kwargs['instance'].get_archive_path()
    import shutil
    if os.path.isdir(path):
        shutil.rmtree(path)
    if os.path.isdir(archive_path):
        shutil.rmtree(archive_path)
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
    subpath = models.CharField(max_length=250)
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
        return 'command="/var/www/virtualenv/bioshare/include/bioshare/sshwrapper.py %s" ssh-rsa %s %s' % (self.user.username,key,self.user.username)
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
