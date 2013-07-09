from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from settings.settings import FILES_ROOT
import os
# Create your models here.
def pkgen():
    import string, random
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for x in range(15))
class Share(models.Model):
    id = models.CharField(max_length=15,primary_key=True,default=pkgen)
    created = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User)
    name = models.CharField(max_length=100)
    secure = models.BooleanField(default=True)
    notes = models.TextField()
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
        return os.path.join(FILES_ROOT,self.id)
    def create_folder(self,name,subdir=None):
        path = self.get_path() if subdir is None else os.path.join(self.get_path(),subdir)
        if os.path.exists(path):
            folder_path = os.path.join(path,name)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
#     def delete_folder(self,subdir):
#         import shutil
#         if subdir is None or subdir == '' or subdir.count('..') != 0:
#             return False
#         path = os.path.join(self.get_path(),subdir)
#         parent_path = os.path.abspath(os.path.join(path,os.pardir))
#         if os.path.exists(path):
#             delete_path = os.path.join(parent_path,'.removed')
#             if not os.path.exists(delete_path):
#                 os.makedirs(delete_path)
#             shutil.move(path, delete_path)
    def delete_path(self,subpath):
        import shutil
        if subpath is None or subpath == '' or subpath.count('..') != 0:
            return False
        item = os.path.basename(subpath) if os.path.basename(subpath) != '' else os.path.split(os.path.dirname(subpath))[1]
        path = os.path.join(self.get_path(),subpath)
        parent_path = os.path.abspath(os.path.join(path,os.pardir))
        if os.path.exists(path):
            delete_path = os.path.join(parent_path,'.removed')
            if not os.path.exists(delete_path):
                os.makedirs(delete_path)
            move_path = os.path.join(delete_path,item)
            if os.path.exists(move_path):
                if os.path.isfile(move_path):
                    os.remove(move_path)
                else:
                    shutil.rmtree(move_path)
            shutil.move(path, delete_path)
            return True
    def create_archive(self,items,subdir=None):
        path = self.get_path() if subdir is None else os.path.join(self.get_path(),subdir)
        if not os.path.exists(path):
            raise Exception('Invalid subdirectory provided')
        archive_path = os.path.join(self.get_path(),'.archives')
        if not os.path.exists(archive_path):
            os.makedirs(archive_path)
        from datetime import datetime
        zip_name = 'archive_'+datetime.now().strftime('%Y_%m_%d__%H_%M_%S')+'.zip'
        zip_path = os.path.join(archive_path,zip_name)
        from zipfile import ZipFile
        archive =  ZipFile(zip_path, 'w')
        for item in items:
            item_path = os.path.join(path,item)
            if not os.path.exists(item_path):
                raise Exception("File or folder: '%s' does not exist" % (item))
            archive.write(item_path)
        details = {'namelist':archive.namelist(),'name':zip_name}
        archive.close()
        return {'name':zip_name,'subpath':'.archives/'+zip_name}
def share_post_save(sender, **kwargs):
    if kwargs['created']:
        path = kwargs['instance'].get_path()
        if not os.path.exists(path):
            os.makedirs(path)
post_save.connect(share_post_save, sender=Share)