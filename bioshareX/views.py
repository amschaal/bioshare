# Create your views here.
from django.shortcuts import render_to_response, render, redirect
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseRedirect
from settings.settings import FILES_ROOT, RSYNC_URL
from models import Share, SSHKey, MetaData, Tag, ShareStats
from forms import ShareForm, FolderForm, SSHKeyForm, MetaDataForm, PasswordChangeForm
from guardian.shortcuts import get_perms, get_users_with_perms
from django.utils import simplejson
from bioshareX.utils import share_access_decorator, safe_path_decorator, sizeof_fmt, json_response
from bioshareX.file_utils import istext
from django.contrib.auth.decorators import login_required
from guardian.shortcuts import get_objects_for_user

def index(request):
    # View code here...
    return render(request,'index.html', {"message": "Hi there"})

@safe_path_decorator()
def redirect_old_path(request, id, subpath=''):
    share_id = '00000%s'%id
    return HttpResponseRedirect(reverse('go_to_file_or_folder',kwargs={'share':share_id,'subpath':subpath}))

def tag_cloud(request):
    # View code here...
    return render(request,'viz/cloud.html')
@login_required
def list_shares(request):
    # View code here...
#     shares = Share.objects.filter(owner=request.user)
#     shared_with_me = get_objects_for_user(request.user, 'bioshareX.view_share_files')
    shares = Share.user_queryset(request.user).order_by('-created')
    total_size = sizeof_fmt(sum([s.bytes for s in ShareStats.objects.filter(share__owner=request.user)]))
    stats = ShareStats.objects.filter(share__owner=request.user)
    return render(request,'share/shares.html', {"shares": shares,"total_size":total_size})

def forbidden(request):
    # View code here...
    return render(request,'index.html', {"message": "You have tried to access a forbidden resource."})

@share_access_decorator(['admin'])
def share_permissions(request,share):
#     users = get_users_with_perms(share,attach_perms=True, with_group_users=False)
    return render(request,'share/permissions.html', {"share":share,"request":request})

@share_access_decorator(['admin'])
def edit_share(request,share):
    if request.method == 'POST':
        form = ShareForm(request.user,request.POST,instance=share)
        if form.is_valid():
            share = form.save(commit=False)
            tags = []
            for tag in form.cleaned_data['tags'].split(','):
                tag = tag.strip()
                if len(tag) > 2 :
                    tags.append(Tag.objects.get_or_create(name=tag)[0])
            share.tags = tags
            share.save()
            return HttpResponseRedirect(reverse('list_directory',kwargs={'share':share.id}))
    else:
        tags = ','.join([tag.name for tag in share.tags.all()])
        form = ShareForm(request.user,instance=share)
        form.fields['tags'].initial = tags
    return render(request, 'share/edit_share.html', {'form': form})

@safe_path_decorator(path_param='subdir')
@share_access_decorator(['view_share_files'])
def list_directory(request,share,subdir=None):
    from os import listdir, stat
    from os.path import isfile, join, getsize, normpath
    import time, datetime
    PATH = share.get_path()
    if subdir is not None:
        PATH = join(PATH,subdir)
    share_perms = share.get_user_permissions(request.user)
    if not share.secure:
        share_perms = list(set(share_perms+['view_share_files','download_share_files']))
    file_list=[]
    dir_list=[]
    regex = r'^%s[^/]+/?' % '' if subdir is None else normpath(subdir)+'/'
    metadatas = {}
    for md in MetaData.objects.filter(share=share,subpath__regex=regex):
        metadatas[md.subpath]= md if not request.is_ajax() else md.json()
    for name in listdir(PATH):
        path = join(PATH,name)
        subpath= name if subdir is None else join(subdir,name)
#         metadata = MetaData.get_or_none(share=share,subpath=subpath)
        metadata = metadatas[subpath] if metadatas.has_key(subpath) else {}
        if isfile(path):
            (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = stat(path)
            file={'name':name,'size':sizeof_fmt(size),'bytes':size,'modified':datetime.datetime.fromtimestamp(mtime).strftime("%m/%d/%Y %I:%M %p"),'metadata':metadata,'isText':istext(path)}
            file_list.append(file)
        elif name not in []:#['.removed','.archives']:
            (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = stat(path)
            dir={'name':name,'size':getsize(path),'metadata':metadata,'modified':datetime.datetime.fromtimestamp(mtime).strftime("%m/%d/%Y %I:%M %p")}
            dir_list.append(dir)
    if request.is_ajax():
        return json_response({'files':file_list,'directories':dir_list})
    owner = request.user == share.owner

    return render(request,'list.html', {"files":file_list,"directories":dir_list,"path":PATH,"share":share,"subdir": subdir,'rsync_url':RSYNC_URL,"folder_form":FolderForm(),"metadata_form":MetaDataForm(),"request":request,"owner":owner,"share_perms":share_perms,"share_perms_json":simplejson.dumps(share_perms)})

@login_required
def create_share(request):
    if not request.user.has_perm('bioshareX.add_share'):
        return render(request,'index.html', {"message": "You must have permissions to create a Share.  You may request access from the <a href=\"mailto:amschaal@ucdavis.edu\">webmaster</a>."})
    if request.method == 'POST':
        form = ShareForm(request.user,request.POST)
        if form.is_valid():
            share = form.save(commit=False)
            share.owner=request.user
            share.save()
            return HttpResponseRedirect(reverse('list_directory',kwargs={'share':share.id}))
    else:
        form = ShareForm(request.user)
    return render(request, 'share/new_share.html', {'form': form})

@login_required
def update_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.POST)
        if form.is_valid():
            request.user.set_password(form.cleaned_data['password1'])
            request.user.save()
            return render(request, 'registration/update_password.html', {'success': True})
    else:
        form = PasswordChangeForm()
    return render(request, 'registration/update_password.html', {'form': form})


def list_ssh_keys(request):
    context ={'keys':SSHKey.objects.filter(user=request.user)}
    return render(request,'ssh/list_keys.html',context)

@login_required
def create_ssh_key(request):
    if request.method == 'POST':
        form = SSHKeyForm(request.POST,request.FILES)
        if form.is_valid():
            key = SSHKey(name=form.cleaned_data['name'],key=form.cleaned_data['rsa_key'],user=request.user)
#             key = form.save(commit=False)
#             key.user=request.user
            key.save()
            from settings.settings import AUTHORIZED_KEYS_FILE
            import subprocess
            subprocess.check_call(['sudo','/bin/chmod','660',AUTHORIZED_KEYS_FILE])
            auth_keys = open(AUTHORIZED_KEYS_FILE, "a")
            auth_keys.write(key.create_authorized_key()+'\n')
            auth_keys.close()
            subprocess.check_call(['sudo','/bin/chmod','600',AUTHORIZED_KEYS_FILE])
            return HttpResponseRedirect(reverse('list_ssh_keys'))
    else:
        form = SSHKeyForm()
    return render(request, 'ssh/new_key.html', {'form': form})
from django.contrib.auth.forms import SetPasswordForm

@safe_path_decorator()
@share_access_decorator(['view_share_files'])    
def go_to_file_or_folder(request, share, subpath=None):
    from os.path import isdir, isfile, join
    import os
    path = share.get_path() if subpath is None else join(share.get_path(),subpath)
    if isdir(path):
        return HttpResponseRedirect(reverse('list_directory',kwargs={'share':share.id,'subdir':os.path.normpath(subpath) + os.sep}))
    else:# isfile(path)
        return HttpResponseRedirect(reverse('download_file',kwargs={'share':share.id,'subpath':subpath}))
    
@share_access_decorator(['admin'])
def delete_share(request, share, confirm=False):
    if share.owner != request.user:
        return render(request, 'share/delete_share.html', {'message': 'Only the owner may delete the share.'})
    if confirm:
        share.delete()
        return render(request, 'share/delete_share.html', {'message': 'The share "%s" and all its files have been deleted.'%share.name})
    else:
        return render(request, 'share/delete_share.html', {'share':share,'show_confirm':True})
    
    
@login_required
def search_files(request):
    from utils import find
    query = request.GET.get('query',None)
    results=[]
    if query:
        shares = Share.user_queryset(request.user)
        for s in shares:
            r=find(s,query,prepend_share_id=False)
            results.append({'share':s,'results':r})
    return render(request, 'search/search_files.html', {'query':query,'results':results})
