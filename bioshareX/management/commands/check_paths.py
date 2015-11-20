from django.core.management.base import BaseCommand
from bioshareX.models import Share
import os

class Command(BaseCommand):
    help = 'Check that share paths exist'

    def handle(self, *args, **options):
        self.stdout.write('Checking share paths...')
        for share in Share.objects.all():
            share.path_exists = share.check_path()
            share.real_path = os.path.realpath(share.get_path())
            share.save()
            if not share.path_exists:
                print "Path '%s' does not exist for share: '%s'" % (share.get_path(),share.name)
