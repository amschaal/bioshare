import os, time, shutil

def clean_archives(share,days=3):
    path = share.get_archive_path()
    if os.path.isdir(path):
        for f in os.listdir(path):
            fpath = os.path.join(path, f)
            mtime = os.path.getmtime(fpath)
            if ((time.time()-os.path.getmtime(fpath))/(24*3600)) >= days:
                #print 'deleting %s'%fpath
                os.remove(fpath)
                
def clean_removed(share,days=3):
    path = share.get_removed_path()
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for file in files:
                fpath = os.path.join(root, file)
                mtime = os.path.getmtime(fpath)
                if ((time.time()-os.path.getmtime(fpath))/(24*3600)) >= days:
#                     print 'deleting %s'%fpath
                    os.remove(fpath)
            for dir in dirs:
                dpath = os.path.join(root, dir)
                if len(os.listdir(dpath)) == 0:
                    mtime = os.path.getmtime(dpath)
                    if ((time.time()-os.path.getmtime(dpath))/(24*3600)) >= days:
#                         print 'deleting %s'%dpath
                        shutil.rmtree(dpath)

def update_file_stats():
    from bioshareX.models import Share
    for share in Share.objects.all():
        try:
            share.get_stats()
        except:
            print 'Unable to create stats for share: %s'%share.name
import subprocess        
def istext(path):
    return ('text' in  subprocess.Popen(["file", '-b', path], stdout=subprocess.PIPE).stdout.read())

def get_lines(path,from_line=1,to_line=100):
#     return ' '.join(["sed", "'%d,%dp; %dq'" % (from_line,to_line,to_line+1), path])
    return subprocess.Popen(['sed', '-n','%d,%dp; %dq' % (from_line,to_line,to_line+1), path], stdout=subprocess.PIPE).stdout.read()
#     sed '5555,7777p; 7778q' filename
def get_num_lines(path):
    return int(subprocess.Popen(['wc', '-l', path], stdout=subprocess.PIPE).stdout.read().split()[0])

