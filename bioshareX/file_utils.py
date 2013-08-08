import os, time, shutil

def clean_archives(share,days=2):
    path = os.path.join(share.get_path(),'.archives')
    if os.path.isdir(path):
        for f in os.listdir(path):
            fpath = os.path.join(path, f)
            mtime = os.path.getmtime(fpath)
            if ((time.time()-os.path.getmtime(fpath))/(24*3600)) >= days:
                #print 'deleting %s'%fpath
                os.remove(fpath)
                
def clean_removed(share,days=2):
    path = os.path.join(share.get_path(),'.removed')
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
        share.get_stats()