from datetime import timedelta
import subprocess
from django.utils import timezone

def update_file_stats(last_modified_days=7):
    from bioshareX.models import Share
    last_modified = timezone.now() - timedelta(days=last_modified_days)
    shares = Share.objects.filter(updated__gte=last_modified)
    print('****{} shares selected.****'.format(shares.count()))
    for share in shares:
        try:
            share.get_stats()
            print('Updated {}'.format(share))
        except:
            print('Unable to create stats for share: %s'%share.name)
     
def istext(path):
    return ('text' in  subprocess.Popen(["file", '-b', path], stdout=subprocess.PIPE).communicate()[0].decode('utf-8'))

def get_lines(path,from_line=1,to_line=100):
#     return ' '.join(["sed", "'%d,%dp; %dq'" % (from_line,to_line,to_line+1), path])
    return subprocess.Popen(['sed', '-n','%d,%dp; %dq' % (from_line,to_line,to_line+1), path], stdout=subprocess.PIPE).communicate()[0].decode('utf-8')
#     sed '5555,7777p; 7778q' filename
def get_num_lines(path):
    return int(subprocess.Popen(['wc', '-l', path], stdout=subprocess.PIPE).communicate()[0].split()[0])

