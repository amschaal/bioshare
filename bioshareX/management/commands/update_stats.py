from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone
from bioshareX.file_utils import update_file_stats
from bioshareX.models import Share
from datetime import timedelta

def days_ago(days):
    return timezone.now() - timedelta(days=days)

def update_file_stats(queryset, limit=None):
    from bioshareX.models import Share
    if limit:
        print('****{}/{} shares selected.****'.format(min(limit, queryset.count()),queryset.count()))
        queryset = queryset[:limit]
    else:
        print('****{} shares selected.****'.format(queryset.count()))
    for share in queryset:
        try:
            share.get_stats()
            print('Updated {}'.format(share))
        except:
            print('Unable to create stats for share: %s'%share.name)

class Command(BaseCommand):
    help = 'Updates file statistics for all shares'
    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
    def handle(self, *args, **options):
        limit = options.get("limit")
        linked_shares = Share.objects.filter((Q(link_to_path__isnull=False)|Q(symlinks_found__isnull=False))&Q(stats__updated__lte=days_ago(7))) #Periodically update linked data, which could change without modifing updated date
        recently_updated = Share.objects.filter(Q(updated__gte=days_ago(1))|(Q(updated__gte=days_ago(7))&Q(stats__updated__lte=days_ago(7)))) #All recently updated shares
        old_stats = Share.objects.filter(stats__updated__lte=days_ago(30))
        no_stats = Share.objects.filter(stats__isnull=True)
        
        update_file_stats(linked_shares)
        update_file_stats(recently_updated)
        update_file_stats(old_stats, limit)
        update_file_stats(no_stats, limit)
        self.stdout.write('Successfully updated file statistics')