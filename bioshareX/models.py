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
    notes = models.TextField()
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
        path = os.path.join(self.get_path(),subpath)
        parent_path = os.path.abspath(os.path.join(path,os.pardir))
        if os.path.exists(path):
            delete_path = os.path.join(parent_path,'.removed')
            if not os.path.exists(delete_path):
                os.makedirs(delete_path)
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
        with ZipFile(zip_path, 'w') as archive:
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