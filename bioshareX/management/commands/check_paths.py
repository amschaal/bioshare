from django.core.management.base import BaseCommand
from django.utils import timezone
from bioshareX.models import Share
import os

from bioshareX.utils import search_illegal_symlinks

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