from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from bioshareX.models import Share
import os
from bioshareX.utils import search_illegal_symlinks
from django.core.mail import send_mail
from django.db.models import Q


def email_admin(share, message):
    send_mail(
    'Illegal path for share {} found'.format(share.id),
    'Share {}:{} has an illegal path: {}'.format(share.id, share.name, message),
    settings.DEFAULT_FROM_EMAIL,
    [a[1] for a in settings.ADMINS],
    fail_silently=False,
)

class Command(BaseCommand):
    help = 'Check that share paths exist, look for illegal symlinks'

    def handle(self, *args, **options):
        self.stdout.write('Checking share paths...')
        # This is relying on the app to keep track of whether symlinks exist in a share, otherwise should check all shares each time
        for share in Share.objects.filter(Q(symlinks_found__isnull=False)|Q(link_to_path__isnull=False)):
            try:
                message = share.check_paths(check_symlinks=True)
                if share.illegal_path_found:
                    email_admin(share, message)
            except Exception as e:
                self.stdout.write('Exception while checking share {}-{} at path {}: {}'.format(share.id, share.name, share.get_path(), str(e)))
        # for share in Share.objects.exclude(Q(symlinks_found__isnull=False)|Q(link_to_path__isnull=False)):
        #     share.check_paths(check_symlinks=False)