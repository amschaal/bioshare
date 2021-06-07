from django.db import models
from django.contrib.auth.models import User, Group
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete, pre_save,\
    m2m_changed
from django.db.models import Q
from django.conf import settings
import os
from django.utils.html import strip_tags
from bioshareX.utils import test_path, paths_contain, path_contains
from jsonfield import JSONField
import datetime
from guardian.shortcuts import get_users_with_perms, get_objects_for_group
from django.core.urlresolvers import reverse
from guardian.models import UserObjectPermissionBase, GroupObjectPermissionBase
import subprocess
from django.utils import timezone
from django.contrib.postgres.fields.array import ArrayField
import re

def pkgen():
    import string, random
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for x in range(15))

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
#         self.num_files = stats['files']
        self.bytes = stats['size']
        self.updated = timezone.now()
        self.save()

class Filesystem(models.Model):
    TYPE_STANDARD = 'STANDARD'
    TYPE_ZFS = 'ZFS'
    TYPES = ((TYPE_STANDARD,'Standard'),(TYPE_ZFS,'ZFS'))
    name = models.CharField(max_length=50)
    description = models.TextField()
    path = models.CharField(max_length=200)
    users = models.ManyToManyField(User, related_name='filesystems')
    type = models.CharField(max_length=20,choices=TYPES,default=TYPE_STANDARD)
    def __unicode__(self):
        return '%s: %s' %(self.name, self.path)

class FilePath(models.Model):
    path = models.CharField(max_length=200)
    name = models.CharField(max_length=50,null=True,blank=True)
    description = models.TextField(null=True,blank=True)
    regexes = ArrayField(models.CharField(max_length=200), blank=False)
    users = models.ManyToManyField(User, related_name='file_paths', blank=True)
    cluster = models.BooleanField(default=False)
    def is_valid(self, path):
        if not path_contains(self.path, path):
            return False
        if not self.regexes or len(self.regexes) == 0:
            return True
        for regex in self.regexes:
            if re.match(regex, path):
                return True
        return False
    def __unicode__(self):
        return '%s: %s' %(self.name, self.path) if self.name else self.path

class Share(models.Model):
    id = models.CharField(max_length=15,primary_key=True,default=pkgen)
    slug = models.SlugField(max_length=50,blank=True,null=True)
    parent = models.ForeignKey('self',null=True,blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now_add=True,null=True,blank=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    name = models.CharField(max_length=125)
    secure = models.BooleanField(default=True)
    read_only = models.BooleanField(default=False)
    notes = models.TextField(null=True,blank=True)
    tags = models.ManyToManyField('Tag')
    link_to_path = models.CharField(max_length=200,blank=True,null=True)
    filepath = models.ForeignKey(FilePath,blank=True,null=True)
    sub_directory = models.CharField(max_length=200,blank=True,null=True)
    real_path = models.CharField(max_length=200,blank=True,null=True)
    filesystem = models.ForeignKey(Filesystem, on_delete=models.PROTECT)
    path_exists = models.BooleanField(default=True)
    last_data_access = models.DateTimeField(null=True)
    PERMISSION_VIEW = 'view_share_files'
    PERMISSION_DELETE = 'delete_share_files'
    PERMISSION_DOWNLOAD = 'download_share_files'
    PERMISSION_WRITE = 'write_to_share'
    PERMISSION_LINK_TO_PATH = 'link_to_path'
    PERMISSION_ADMIN = 'admin'
    def __unicode__(self):
        return self.name
    @property
    def slug_or_id(self):
        return self.slug if self.slug else self.id
    @staticmethod
    def get_by_slug_or_id(slug_or_id):
        return Share.objects.get(Q(id=slug_or_id)|Q(slug=slug_or_id))
    def update_last_modified(self,commit=True):
        self.updated = timezone.now()
        if commit:
            self.save()
    def get_url(self,subpath=None):
        if subpath:
            return reverse('list_directory',kwargs={'share':self.slug_or_id,'subpath':subpath})
        return reverse('list_directory',kwargs={'share':self.slug_or_id})
    def get_stats(self):
        stats = ShareStats.objects.get_or_create(share=self)[0]
        stats.update_stats()
        return stats
    @staticmethod
    def user_queryset(user,include_stats=True):
        from guardian.shortcuts import get_objects_for_user
        shares = get_objects_for_user(user, 'bioshareX.view_share_files')
#         query = Q(id__in=[s.id for s in shares])|Q(owner=user) if user.is_authenticated() else Q(id__in=[s.id for s in shares])
        query = Q(id__in=shares)|Q(owner=user) if user.is_authenticated() else Q(id__in=shares)
        if include_stats:
            return Share.objects.select_related('stats').filter(query)
        else:
            return Share.objects.filter(query)
    #Get a list of users with ANY permission.  Useful for getting lists of emails, etc.
    def get_users_with_permissions(self):
        return list( 
             set(
                 [uop.user for uop in ShareUserObjectPermission.objects.filter(content_object=self).select_related('user')] +
                 list(User.objects.filter(groups__in=ShareGroupObjectPermission.objects.filter(content_object=self).values_list('group_id',flat=True)))
                 )
             )
    def get_permissions(self,user_specific=False):
        from guardian.shortcuts import get_groups_with_perms
        user_perms = self.get_all_user_permissions(user_specific=user_specific)
        groups = get_groups_with_perms(self,attach_perms=True)
        group_perms = [{'group':{'name':group.name,'id':group.id},'permissions':permissions} for group, permissions in groups.iteritems()]
        return {'user_perms':user_perms,'group_perms':group_perms}
    def get_user_permissions(self,user,user_specific=False):
        if user_specific:
            from utils import fetchall
            perms = [uop.permission.codename for uop in ShareUserObjectPermission.objects.filter(user=user,content_object=self).select_related('permission')]
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
            print 'users'
            print users
            user_perms = [{'user':{'username':user.username, 'email':user.email, 'first_name':user.first_name, 'last_name':user.last_name},'permissions':permissions} for user, permissions in users.iteritems()]
        else:
            perms = ShareUserObjectPermission.objects.filter(content_object=self).select_related('permission','user')
            user_perms={}
            for perm in perms:
                if not user_perms.has_key(perm.user.username):
                    user_perms[perm.user.username]={'user':{'username':perm.user.username},'permissions':[]}
                user_perms[perm.user.username]['permissions'].append(perm.permission.codename)
        return user_perms
    def get_path(self):
        return os.path.join(self.filesystem.path,self.id)
    def get_link_path(self, add_trailing_slash=True):
        if self.link_to_path and add_trailing_slash:
            return os.path.join(self.link_to_path, '')
        return None
    def get_zfs_path(self):
        if not getattr(settings,'ZFS_BASE',False) or not self.filesystem.type == Filesystem.TYPE_ZFS:
            return None
        return os.path.join(settings.ZFS_BASE,self.id)
    def get_realpath(self):
        return os.path.realpath(self.get_path())
    def check_path(self,subdir=None):
        path = self.get_path()
        if subdir:
            path = os.path.join(path,subdir)
        return os.path.exists(path)
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
#         total_size = get_total_size([os.path.join(path,item) for item in items])
#         if total_size > ZIPFILE_SIZE_LIMIT_BYTES:
#             raise Exception("%d bytes is above bioshare's limit for creating zipfiles, please use rsync or wget instead" % (total_size))
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
    if kwargs['created'] and not kwargs.get('raw',False):
        os.umask(settings.UMASK)
        instance = kwargs['instance']
        path = instance.get_path()
        import pwd, grp
        if not os.path.exists(path):
            if instance.link_to_path:
                instance.create_link()
            else:
                from settings.settings import FILES_GROUP, FILES_OWNER
                if instance.get_zfs_path():
                    subprocess.check_call(['zfs','create',instance.get_zfs_path()])
                else:
                    os.makedirs(path)
                uid = pwd.getpwnam(FILES_OWNER).pw_uid
                gid = grp.getgrnam(FILES_GROUP).gr_gid
        if not instance.real_path:
            instance.real_path = os.path.realpath(instance.get_path())
            instance.save()
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
        
def share_post_delete(sender, instance, **kwargs):
    path = instance.get_path()
    import shutil
    if os.path.islink(path):
        instance.unlink()
    elif instance.get_zfs_path():
        subprocess.check_call(['zfs','destroy',instance.get_zfs_path()])
    else:
        if os.path.isdir(path):
            shutil.rmtree(path)
post_delete.connect(share_post_delete, sender=Share)

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
    text = models.TextField(null=True,blank=True)
    paths = JSONField()
    @staticmethod
    def create(share,action,user=None,text='',paths=[],subdir=None,share_updated=True):
        if subdir:
            paths = [os.path.join(subdir,path) for path in paths]
        log = ShareLog.objects.create(share=share,user=user,action=action,text=text,paths=paths)
        if share_updated:
            share.update_last_modified()
        return log


class Message(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=50)
    description = models.TextField(null=True,blank=True)
    active = models.BooleanField(default=True)
    expires = models.DateField(null=True,blank=True)
    viewed_by = models.ManyToManyField(User)
    def __unicode__(self):
        return self.title

class GroupProfile(models.Model):
    group = models.OneToOneField(Group,related_name='profile')
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.PROTECT)
    description = models.TextField(blank=True,null=True)


"""
    Make permissions more efficient to check by having a direct foreign key:
    http://django-guardian.readthedocs.io/en/stable/userguide/performance.html#direct-foreign-keys
"""

class ShareUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(Share,related_name='user_permissions')

class ShareGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(Share,related_name='group_permissions')

def group_shares(self):
    return Share.objects.filter(group_permissions__group=self)
Group.shares = property(group_shares)

def user_permission_codes(self):
    return [p.codename for p in self.user_permissions.all()]
User.permissions = user_permission_codes

Group._meta.permissions += (('manage_group', 'Manage group'),)
User._meta.ordering = ['username']

def lowercase_user(sender, instance, **kwargs):
    if instance.username != instance.username.lower() or instance.email != instance.email.lower():
        User.objects.filter(id=instance.id).update(username=instance.username.lower(),email=instance.email.lower())
post_save.connect(lowercase_user, sender=User)