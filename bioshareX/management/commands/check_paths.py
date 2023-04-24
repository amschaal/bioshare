from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from bioshareX.models import Share
import os
from bioshareX.utils import search_illegal_symlinks
from django.core.mail import send_mail



def email_admin(share, message):
    send_mail(
    'Illegal path for share {} found'.format(share.id),
    'Share {}:{} has an illegal path: {}'.format(share.id, share.name, message),
    settings.DEFAULT_FROM_EMAIL,
    [a[1] for a in settings.ADMINS],
    fail_silently=False,
)

class Command(BaseCommand):
    help = 'Check that share paths exist'

    def handle(self, *args, **options):
        self.stdout.write('Checking share paths...')
        for share in Share.objects.all():
            share.path_exists = share.check_path()
            share.real_path = os.path.realpath(share.get_path())
            share.save()
            if not share.path_exists:
                ... 
                # print("Path '%s' does not exist for share: '%s'" % (share.get_path(),share.name))
            else:
                try:
                    search_illegal_symlinks(share.real_path)
                except Exception as e:
                    share.illegal_path_found = timezone.now()
                    share.save()
                    email_admin(share, str(e))