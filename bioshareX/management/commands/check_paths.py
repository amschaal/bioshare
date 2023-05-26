from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from bioshareX.models import Share
import os
from bioshareX.utils import search_illegal_symlinks
from django.core.mail import send_mail
from django.db.models import Q

from datetime import timedelta
MAX_DAYS_BEFORE_CHECK = 7


# def email_admin(share, message):
#     send_mail(
#     'Illegal path for share {} found'.format(share.id),
#     'Share {}:{} has an illegal path: {}'.format(share.id, share.name, message),
#     settings.DEFAULT_FROM_EMAIL,
#     [a[1] for a in settings.ADMINS],
#     fail_silently=False,
# )



class Command(BaseCommand):
    help = 'Check that share paths exist, look for illegal symlinks'
    errors = []
    illegal = []
    def handle(self, *args, **options):
        self.stdout.write('Checking share paths...')
        # This is relying on the app to keep track of whether symlinks exist in a share, otherwise should check all shares each time
        for share in Share.objects.filter(Q(symlinks_found__isnull=False)|Q(link_to_path__isnull=False)):
            self.check_share(share)
        for share in Share.objects.exclude(Q(last_checked__isnull=True)|Q(last_checked__lte=timezone.now()-timedelta(days=MAX_DAYS_BEFORE_CHECK))):
            self.check_share(share)
        self.email_admins()
    def check_share(self, share):
        try:
            message = share.check_paths(check_symlinks=True)
            if share.illegal_path_found:
                msg = 'Share {}:{} has an illegal path: {}'.format(share.id, share.name, message)
                self.stdout.write(msg)
                self.illegal.append(msg)
        except Exception as e:
            msg = 'Exception while checking share {}-{} at path {}: {}'.format(share.id, share.name, share.get_path(), str(e))
            self.stdout.write(msg)
            self.errors.append(msg)
    def email_admins(self):
        body = ''
        if self.illegal:
            body += 'Illegal paths were encountered when checking paths:\n'
            body += '\n'.join(self.illegal)
        if self.errors:
            body += '\n\n Errors were encountered when checking paths:\n'
            body += '\n'.join(self.errors)
        if body:
            send_mail(
                'There were {} shares with illegal paths, and {} errors'.format(len(self.illegal), len(self.errors)),
                body,
                settings.DEFAULT_FROM_EMAIL,
                [a[1] for a in settings.ADMINS],
                fail_silently=False
            )