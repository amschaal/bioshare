import datetime
import os
import re
import subprocess
from functools import wraps
from os import path

from django.conf import settings
from django.http.response import JsonResponse
from django.shortcuts import redirect, render
from django.template import Context, Template
from django.urls.base import reverse
from rest_framework import status
from scandir import scandir
from bioshareX.exceptions import IllegalPathException

from bioshareX.file_utils import istext


class JSONDecorator(object):
        def __init__(self, orig_func):
                self.orig_func = orig_func
        def __call__(self,  *args, **kwargs):
                import json
                json_arg = args[0].POST.get('json',args[0].GET.get('json',None))
                if json_arg is not None:
                    kwargs['json'] = json.loads(json_arg)
                elif hasattr(args[0], 'data'):
                    kwargs['json'] = args[0].data
                return self.orig_func(*args, **kwargs)
def share_access_decorator_old(perms,share_param='share'):
    def wrap(f):
        def wrapped_f(*args,**kwargs):
            from bioshareX.models import Share
            share = Share.objects.get(id=kwargs[share_param])
            kwargs[share_param]=share
            f(*args,**kwargs)
        return wrapped_f
    return wrap

def ajax_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        return JsonResponse({'status':'error','unauthenticated':True,'errors':['You do not have access to this resource.']},status=status.HTTP_401_UNAUTHORIZED)
    return wrapper

class share_access_decorator(object):

    def __init__(self, perms,share_param='share'):
        """
        If there are decorator arguments, the function
        to be decorated is not passed to the constructor!
        """
        self.perms = perms
        self.share_param  = share_param
    def __call__(self, f):
        """
        If there are decorator arguments, __call__() is only called
        once, as part of the decoration process! You can only give
        it a single argument, which is the function object.
        """
        def wrapped_f(*args,**kwargs):
            from bioshareX.models import Share
            try:
                share = Share.get_by_slug_or_id(kwargs[self.share_param])
            except Share.DoesNotExist:
                return render(args[0],'errors/message.html', {'message':'No share with that ID exists.'},status=500)
            kwargs[self.share_param]=share
            request = args[0]
            user_permissions = share.get_user_permissions(request.user)
            for perm in self.perms:
                if not share.secure and perm in ['view_share_files','download_share_files']:
                    continue
                if not perm in user_permissions:
                    if request.is_ajax():
                        if not request.user.is_authenticated:
                            return JsonResponse({'status':'error','unauthenticated':True,'errors':['You do not have access to this resource.']},status=status.HTTP_401_UNAUTHORIZED)
                            return json_error({'status':'error','unauthenticated':True,'errors':['You do not have access to this resource.']})
                        else:
                            return json_error(['You do not have access to this resource.'])
                    else:
                        if not request.user.is_authenticated:
                            url = reverse('login') + '?next=%s' % request.get_full_path()
                            return redirect(url)
                        return redirect('forbidden')
            return f(*args,**kwargs)
        return wrapped_f

class safe_path_decorator(object):

    def __init__(self, share_param='share',path_param='subpath', write=False):
        """
        If there are decorator arguments, the function
        to be decorated is not passed to the constructor!
        """
        self.share_param  = share_param
        self.path_param  = path_param
        self.write = write
    def __call__(self, f):
        """
        If there are decorator arguments, __call__() is only called
        once, as part of the decoration process! You can only give
        it a single argument, which is the function object.
        """
        def wrapped_f(*args,**kwargs):
            from bioshareX.models import Share
            share = kwargs.get(self.share_param,None)
            if share:
                if not isinstance(kwargs[self.share_param], Share):
                    try:
                        share = Share.get_by_slug_or_id(share)
                    except Share.DoesNotExist:
                        return render(args[0],'errors/message.html', {'message':'No share with that ID exists.'},status=500)
                if not paths_contain(settings.DIRECTORY_WHITELIST,share.get_realpath()):
                    raise Exception('Share has an invalid root path: %s'%share.get_realpath())
            path = kwargs.get(self.path_param,None)
            if path is not None:
                test_path(path)
                if share:
                    full_path = os.path.join(share.get_path(),path)
                    if not paths_contain(settings.DIRECTORY_WHITELIST,full_path):
                        raise Exception('Illegal path encountered, %s, %s'%(share.get_path(),path))
                    if self.write:
                        real_path = os.path.realpath(full_path)
                        if not real_path.startswith(share.get_path()):
                            return json_error(messages=['Write is not allowed for symlinked files and directories.  Encountered path: {}'.format(real_path)])
                            # raise Exception('Write is not allowed for symlinked files and directories.  Encountered path: {}'.format(real_path))
            return f(*args,**kwargs)
        return wrapped_f

class safe_path_decorator_old(object):

    def __init__(self, path_param='subpath'):
        """
        If there are decorator arguments, the function
        to be decorated is not passed to the constructor!
        """
        self.path_param  = path_param
    def __call__(self, f):
        """
        If there are decorator arguments, __call__() is only called
        once, as part of the decoration process! You can only give
        it a single argument, which is the function object.
        """
        def wrapped_f(*args,**kwargs):
            path = kwargs[self.path_param]
            if path is not None:
                test_path(path)
                
            return f(*args,**kwargs)
        return wrapped_f

def get_setting(key, default=None):
    return getattr(settings, key, default)

def test_path(path,allow_absolute=False,share=None):
    illegals = ['..','*']
    for illegal in illegals:
        if illegal in path:
            raise Exception('Illegal path encountered')
    if path.startswith('/') and not allow_absolute:
        raise Exception('Subpath may not start with slash')
    if path.startswith('~') and not allow_absolute:
        raise Exception('Subpath may not start with a "~"')
    if share:
        full_path = os.path.join(share.get_path(),path)
        if not paths_contain(settings.DIRECTORY_WHITELIST,full_path):
            raise Exception('Illegal path encountered, %s, %s'%(share.get_path(),path))

def path_contains(parent_path,child_path,real_path=True):
    if real_path:
        return os.path.join(os.path.realpath(child_path),'').startswith(os.path.join(os.path.realpath(parent_path),''))
    else:
        return os.path.join(child_path,'').startswith(os.path.join(parent_path,''))

def paths_contain(paths,child_path, get_path=False):
    for path in paths:
        if path_contains(path, child_path):
            return path if get_path else True
    return False

def json_response(dict):
    import json

    from django.http.response import HttpResponse
    return HttpResponse(json.dumps(dict), content_type='application/json')
def json_error(messages,http_status=None):
    http_status = http_status or status.HTTP_400_BAD_REQUEST
    return JsonResponse({'status':'error','errors':messages},status=http_status)
#     return json_response({'status':'error','errors':messages})

def dictfetchall(sql,args=[]):
    from django.db import connection
    cursor = connection.cursor()
    cursor.execute(sql, args)
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]

def fetchall(sql,args=[]):
    from django.db import connection
    cursor = connection.cursor()
    cursor.execute(sql, args)
    return cursor.fetchall()


def find_python(pattern, path):
    import fnmatch
    result = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                result.append(os.path.join(root, name))
    return result

def find_in_shares(shares, pattern):
    import subprocess
    paths = [share.get_path() for share in shares]
    output = subprocess.check_output(['find']+paths+['-name',pattern])
    return output.split('\n')

def find(share, pattern, subdir=None,prepend_share_id=True):
    import os
    import subprocess
    path = share.get_path() if subdir is None else os.path.join(share.get_path(),subdir)
    base_path = os.path.realpath(path) 
    output = subprocess.Popen(['find',base_path,'-name',pattern], stdout=subprocess.PIPE).communicate()[0].decode('utf-8')
#     output = subprocess.check_output(['find',path,'-name',pattern])
    paths = output.split('\n')
#     return paths
    results=[]
    for path in paths:
        result = path.split(base_path)
        if len(result) == 2:
#             print os.path.join(share.id,result[1])
            if prepend_share_id:
                results.append('/'+share.id+result[1])
            else:
                results.append(result[1][1:])
                
    return results

def validate_email( email ):
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email
    try:
        validate_email( email )
        return True
    except ValidationError:
        return False

def email_users(users, subject_template=None, body_template=None, ctx_dict={},subject=None,body=None, from_email=settings.DEFAULT_FROM_EMAIL,content_subtype = "html"):
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    if subject:
        t = Template(subject)
        subject = t.render(Context(ctx_dict))
    else:
        subject = render_to_string(subject_template,ctx_dict)
    subject = ''.join(subject.splitlines())
    if body:
        t = Template(body)
        message = t.render(Context(ctx_dict))
    else:
        message = render_to_string(body_template, ctx_dict)
    msg = EmailMessage(subject, message, from_email, [u.email for u in users])
    msg.content_subtype = content_subtype  # Main content is now text/html
    msg.send(fail_silently=False)
#     
# def get_file_info(path):
#     from os.path import basename
#     from os import stat
#     import datetime
#     (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = stat(path)
#     return {'name':file.name,'size':size, 'modified':datetime.datetime.fromtimestamp(mtime).strftime("%b %d, %Y %H:%M")} 
def sizeof_fmt(num):
    num /= 1024.0 #function takes bytes, convert to KB 
    for x in ['KB','MB','GB']:
        if num < 1024.0 and num > -1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')

def zipdir(base, path, zip):
    from os.path import relpath
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = relpath(path=file_path, start=base)
            zip.write(file_path,arcname=rel_path)

def get_size(path):
    total_size = 0
    if os.path.isfile(path):
        return os.path.getsize(path)
    elif os.path.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size

def get_share_stats(share):
    path = os.path.abspath(share.get_path())
    total_size = 0
    if not share.parent: # don't count subshares
        ZFS_PATH = share.get_zfs_path()
        if ZFS_PATH:
            ZFS_PATH = share.get_path()
            total_size = subprocess.check_output(['zfs', 'get', '-H', '-o', 'value', '-p', 'used', ZFS_PATH])
        else:
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
    return {'size':int(total_size)}

def get_total_size(paths=[]):
    total_size = 0
    for path in paths:
        total_size += get_size(path)
    return total_size

def du(path):
    """disk usage in human readable format (e.g. '2,1GB')"""
    return subprocess.check_output(['du','-shL', path]).split()[0].decode('utf-8')

def list_share_dir(share,subdir=None,ajax=False):
    from bioshareX.models import MetaData
    PATH = share.get_path()
    if subdir is not None:
        PATH = os.path.join(PATH,subdir)
    file_list=[]
    directories={}
    regex = r'^%s[^/]+/?' % '' if subdir is None else re.escape(os.path.normpath(subdir))+'/'
    metadatas = {}
    for md in MetaData.objects.prefetch_related('tags').filter(share=share,subpath__regex=regex):
        metadatas[md.subpath]= md if not ajax else md.json()    
    for entry in scandir(PATH):
        subpath= entry.name if subdir is None else os.path.join(subdir,entry.name)
        metadata = metadatas[subpath] if subpath in metadatas else {}
        if entry.is_file():
            (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = entry.stat()
            file={'name':entry.name,'extension':entry.name.split('.').pop() if '.' in entry.name else None,'size':sizeof_fmt(size),'bytes':size,'modified':datetime.datetime.fromtimestamp(mtime).strftime("%m/%d/%Y %H:%M"),'metadata':metadata,'isText':True}
            file_list.append(file)
        else:
            (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = entry.stat()
            dir={'name':entry.name,'size':None,'metadata':metadata,'modified':datetime.datetime.fromtimestamp(mtime).strftime("%m/%d/%Y %H:%M")}
            if entry.is_symlink():
                dir['target'] = os.readlink(entry.path)
            directories[os.path.realpath(entry.path)]=dir
    return (file_list,directories)

def md5sum(path):
    output = subprocess.check_output([settings.MD5SUM_COMMAND,path]).decode('utf-8') #Much more efficient than reading file contents into python and using hashlib
    #IE: output = 4968966191e485885a0ed8854c591720  /tmp/Project/Undetermined_S0_L002_R2_001.fastq.gz
    return re.findall(r'([0-9a-fA-F]{32})',output)[0]

def find_symlink(path): #pretty crude check to make sure the path is not and does not contain any symlinks
    if os.path.isfile(path):
        return os.path.islink(path)
    elif os.path.isdir(path):
        output = subprocess.check_output(['find', path, '-type', 'l', '-ls'])
        return bool(output)

def find_symlinks(path):
    symlinks = {}
    for p in subprocess.check_output(['find', path, '-type', 'l']).decode().split('\n'):
        if p and os.path.islink(p):
            symlinks[p] = os.path.realpath(p)
    return symlinks

def search_illegal_symlinks(path, checked=set()):
    symlinks = find_symlinks(path)
    for link, target in symlinks.items():
        # Fix circular symlink check
        # if target in checked and (os.path.isdir(target) or os.path.islink(target)):
        #     raise IllegalPathException('Circular symlink found, {} -> {}'.format(link, target))
        if not paths_contain(settings.DIRECTORY_WHITELIST, target):
            raise IllegalPathException('Illegal symlink encountered, {} -> {}'.format(link, target))
        checked.add(target)
        search_illegal_symlinks(target, checked) # Doing this depth first.  Maybe consider doing breadth first.