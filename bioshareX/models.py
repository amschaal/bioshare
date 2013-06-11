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
def share_post_save(sender, **kwargs):
    if kwargs['created']:
        path = kwargs['instance'].get_path()
        if not os.path.exists(path):
            os.makedirs(path)
post_save.connect(share_post_save, sender=Share)