from django.core.management.base import BaseCommand, CommandError
from bioshareX.file_utils import clean_archives, clean_removed
from bioshareX.models import Share

class Command(BaseCommand):
    help = 'Delete archives and removed files older than 3 days'

    def handle(self, *args, **options):
        shares = Share.objects.all()
        self.stdout.write('Deleting archives for:')
        for share in shares:
            self.stdout.write('%s: %s'%(share.id,share.name))
            clean_archives(share)
        self.stdout.write('Deleting removed files for:')
        for share in shares:
            self.stdout.write('%s: %s'%(share.id,share.name))
            clean_removed(share)
        self.stdout.write('Cleanup finished!')