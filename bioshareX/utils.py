from django.shortcuts import redirect
from django.core.urlresolvers import reverse
class JSONDecorator(object):
        def __init__(self, orig_func):
                self.orig_func = orig_func
        def __call__(self,  *args, **kwargs):
                import json
                json_arg = args[0].REQUEST.get('json',None)
                if json_arg is not None:
                    kwargs['json']=json.loads(json_arg)
                return self.orig_func(*args, **kwargs)
def share_access_decorator_old(perms,share_param='share'):
    def wrap(f):
#         print "Inside wrap()"
        def wrapped_f(*args,**kwargs):
            from bioshareX.models import Share
            share = Share.objects.get(id=kwargs[share_param])
            kwargs[share_param]=share
#             print "Inside wrapped_f()"
#             print "Decorator arguments:", arg1, arg2, arg3
            f(*args,**kwargs)
#             print "After f(*args)"
        return wrapped_f
    return wrap
            
class share_access_decorator(object):

    def __init__(self, perms,share_param='share'):
        """
        If there are decorator arguments, the function
        to be decorated is not passed to the constructor!
        """
#         print "Inside __init__()"
        self.perms = perms
        self.share_param  = share_param
    def __call__(self, f):
        """
        If there are decorator arguments, __call__() is only called
        once, as part of the decoration process! You can only give
        it a single argument, which is the function object.
        """
#         print "Inside __call__()"
        def wrapped_f(*args,**kwargs):
#             print "Inside wrapped_f()"
#             print "Decorator arguments:", self.arg1, self.arg2, self.arg3
            from bioshareX.models import Share
            share = Share.objects.get(id=kwargs[self.share_param])
            kwargs[self.share_param]=share
            request = args[0]
            if share.owner.username != request.user.username:
                for perm in self.perms:
                    if not share.secure and perm in ['view_share_files','download_share_files']:
                        continue
                    if not request.user.has_perm(perm,share):
                        if request.is_ajax():
                            return json_error(['You do not have access to this resource.'])
                        else:
                            if not request.user.is_authenticated():
                                url = reverse('auth_login') + '?next=%s' % request.get_full_path()
                                return redirect(url)
                            return redirect('forbidden')
    #                 if not request.user.has_perm('admin',share_obj):
    #                     return json_response({'status':'error','error':'You do not have permission to write to this share.'})
            return f(*args,**kwargs)
#             print "After f(*args)"
        return wrapped_f
            
def json_response(dict):
    from django.http.response import HttpResponse
    from django.utils import simplejson
    return HttpResponse(simplejson.dumps(dict), mimetype='application/json')
def json_error(messages):
    return json_response({'status':'error','errors':messages})

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
    import os, fnmatch
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

def find(share, pattern, subdir=None):
    from settings.settings import FILES_ROOT
    import subprocess, os
#     @todo: use -prune option to get rid of .archive and .removed directories
    path = share.get_path() if subdir is None else os.path.join(share.get_path(),subdir)
    base_path = os.path.realpath(path) 
    output = subprocess.Popen(['find',base_path,'-name',pattern], stdout=subprocess.PIPE).communicate()[0]
#     output = subprocess.check_output(['find',path,'-name',pattern])
    paths = output.split('\n')
#     return paths
    results=[]
    for path in paths:
        result = path.split(base_path)
        if len(result) == 2:
            print os.path.join(share.id,result[1])
            results.append('/'+share.id+result[1])
    return results

def validate_email( email ):
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError
    try:
        validate_email( email )
        return True
    except ValidationError:
        return False

def email_users(users, subject_template, body_template, ctx_dict):
    from django.template.loader import render_to_string
    from settings.settings import DEFAULT_FROM_EMAIL 
    from django.core.mail import EmailMessage
    subject = render_to_string(subject_template,ctx_dict)
    # Email subject *must not* contain newlines
    subject = ''.join(subject.splitlines())
    message = render_to_string(body_template, ctx_dict)
    msg = EmailMessage(subject, message, DEFAULT_FROM_EMAIL, [u.email for u in users])
    msg.content_subtype = "html"  # Main content is now text/html
    msg.send()
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
    import os
    from os.path import relpath
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = relpath(path=file_path, start=base)
            zip.write(file_path,arcname=rel_path)
            

def get_size(path):
    import os
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
    import os
    path = os.path.abspath(share.get_path())
    total_size = 0
    total_files = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
            total_files += 1
    return {'size':total_size,'files':total_files}

def get_total_size(paths=[]):
    total_size = 0
    for path in paths:
        total_size += get_size(path)
    return total_size
