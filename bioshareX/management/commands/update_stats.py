from django.core.management.base import BaseCommand, CommandError
from bioshareX.file_utils import update_file_stats

class Command(BaseCommand):
    help = 'Updates file statistics for all shares'
    def add_arguments(self, parser):
        parser.add_argument("updated_days_ago", type=int)
    def handle(self, *args, **options):
        updated_days_ago = options.get("updated_days_ago", 7)
        update_file_stats(updated_days_ago)
        self.stdout.write('Successfully updated file statistics')