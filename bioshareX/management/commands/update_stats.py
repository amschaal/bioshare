from django.core.management.base import BaseCommand, CommandError
from bioshareX.file_utils import update_file_stats

class Command(BaseCommand):
    help = 'Updates file statistics for all shares'

    def handle(self, *args, **options):
        update_file_stats()
        self.stdout.write('Successfully updated file statistics')