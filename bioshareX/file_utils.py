import subprocess

def update_file_stats():
    from bioshareX.models import Share
    for share in Share.objects.all():
        try:
            share.get_stats()
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

