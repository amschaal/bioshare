# Create your views here.
from django.shortcuts import render_to_response, render, redirect
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseRedirect, HttpResponseForbidden
from models import Share, SSHKey, MetaData, Tag, ShareStats
from forms import ShareForm, FolderForm, SSHKeyForm, MetaDataForm, PasswordChangeForm, RenameForm
from guardian.shortcuts import get_perms, get_users_with_perms
#from django.utils import simplejson
import json
from bioshareX.utils import share_access_decorator, safe_path_decorator, sizeof_fmt, json_response,\
    get_setting, list_share_dir
from bioshareX.file_utils import istext
from django.contrib.auth.decorators import login_required
from guardian.shortcuts import get_objects_for_user
import os
from bioshareX.forms import SubShareForm
from django.contrib.auth.models import User
import operator
from django.db.models.query_utils import Q
from bioshareX.api.serializers import UserSerializer
from rest_framework.renderers import JSONRenderer
import re

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
    total_size = sizeof_fmt(sum([s.bytes for s in ShareStats.objects.filter(share__owner=request.user)]))
    return render(request,'share/shares.html', {"total_size":total_size,"bad_paths":request.GET.has_key('bad_paths')})

def forbidden(request):
    # View code here...
    return render(request,'index.html', {"message": "You have tried to access a forbidden resource."})

@share_access_decorator(['admin'])
def share_permissions(request,share):
#     users = get_users_with_perms(share,attach_perms=True, with_group_users=False)
    return render(request,'share/permissions.html', {"share":share,"request":request})

@share_access_decorator(['admin'])
def edit_share(request,share):
    if share.owner != request.user and not request.user.is_superuser:
        return HttpResponseForbidden('Only share owners or admins may edit a share')
    if request.method == 'POST':
        form = ShareForm(request.user,request.POST,instance=share)
        if form.is_valid():
            share = form.save(commit=False)
            share.set_tags(form.cleaned_data['tags'].split(','))
            return HttpResponseRedirect(reverse('list_directory',kwargs={'share':share.slug_or_id}))
    else:
        tags = ','.join([tag.name for tag in share.tags.all()])
        form = ShareForm(request.user,instance=share)
        form.fields['tags'].initial = tags
    return render(request, 'share/edit_share.html', {'form': form})

@safe_path_decorator(path_param='subdir')
@share_access_decorator(['view_share_files'])
def list_directory(request,share,subdir=None):
    if not share.check_path():
        return render(request,'index.html', {"message": "Unable to locate the files for this share.  Please contact the site administrator."})
    files,directories = list_share_dir(share,subdir=subdir,ajax=request.is_ajax())
    if request.is_ajax():
        return json_response({'files':files,'directories':directories.values()})
    #Find any shares that point at this directory
    for s in Share.user_queryset(request.user).filter(real_path__in=directories.keys()).exclude(id=share.id):
        directories[s.real_path]['share']=s
    share_perms = share.get_user_permissions(request.user)
    PATH = share.get_path()
    subshare = None
    if subdir is not None:
        PATH = os.path.join(PATH,subdir)
        subshare = Share.objects.filter(parent=share,sub_directory=subdir).first()
    owner = request.user == share.owner
    all_perms = share.get_permissions(user_specific=True)
    shared_users = all_perms['user_perms'].keys()
    shared_groups = [g['group']['name'] for g in all_perms['group_perms']]
    emails = [u.email for u in get_users_with_perms(share, attach_perms=False, with_superusers=False, with_group_users=True)]
    return render(request,'list.html', {"session_cookie":request.COOKIES.get('sessionid'),"files":files,"directories":directories.values(),"path":PATH,"share":share,"subshare":subshare,"subdir": subdir,'rsync_url':get_setting('RSYNC_URL',None),'HOST':get_setting('HOST',None),'SFTP_PORT':get_setting('SFTP_PORT',None),"folder_form":FolderForm(),"metadata_form":MetaDataForm(), "rename_form":RenameForm(),"request":request,"owner":owner,"share_perms":share_perms,"all_perms":all_perms,"share_perms_json":json.dumps(share_perms),"shared_users":shared_users,"shared_groups":shared_groups,"emails":emails})

@safe_path_decorator(path_param='subdir')
@share_access_decorator(['view_share_files','download_share_files'])
def wget_listing(request,share,subdir=None):
    from os import listdir
    from os.path import isfile, join
    PATH = share.get_path()
    if subdir is not None:
        PATH = join(PATH,subdir)
    file_list=[]
    dir_list=[]
    for name in listdir(PATH):
        path = join(PATH,name)
        if isfile(path):
            file_list.append(name)
        elif name not in []:#['.removed','.archives']:
            dir_list.append(name)
    return render(request,'wget_listing.html', {"files":file_list,"directories":dir_list,"path":PATH,"share":share,"subdir": subdir})

@login_required
def create_share(request):
    if not request.user.has_perm('bioshareX.add_share'):
        return render(request,'index.html', {"message": "You must have permissions to create a Share.  You may request access from the <a href=\"mailto:webmaster@genomecenter.ucdavis.edu\">webmaster</a>."})
    if request.method == 'POST':
        form = ShareForm(request.user,request.POST)
        if form.is_valid():
            share = form.save(commit=False)
            if not getattr(share, 'owner',None):
                share.owner=request.user
            try:
                share.save()
                share.set_tags(form.cleaned_data['tags'].split(','))
            except Exception, e:
                share.delete()
                return render(request, 'share/new_share.html', {'form': form, 'error':e.message})
            return HttpResponseRedirect(reverse('list_directory',kwargs={'share':share.slug_or_id}))
    else:
        form = ShareForm(request.user)
    return render(request, 'share/new_share.html', {'form': form})

@safe_path_decorator(path_param='subdir')
@share_access_decorator(['admin'])
def create_subshare(request,share,subdir):
    path = os.path.join(share.get_path(),subdir)
    if not os.path.exists(path):
        return render(request,'index.html', {"message": "Unable to create share.  The specified path does not exist."})
    if request.method == 'POST':
        form = SubShareForm(request.POST)
        if form.is_valid():
            subshare = form.save(commit=False)
            subshare.owner = request.user
            subshare.link_to_path = path
            subshare.sub_directory = subdir
            subshare.filesystem = share.filesystem
            subshare.parent = share
            if share.read_only:
                subshare.read_only = True
            try:
                subshare.save()
            except Exception, e:
                subshare.delete()
                return render(request, 'share/new_share.html', {'form': form, 'error':e.message,'share':share,'subdir':subdir})
            return HttpResponseRedirect(reverse('list_directory',kwargs={'share':subshare.slug_or_id}))
    else:
        name = os.path.basename(os.path.normpath(subdir))
        notes = "Shared from '%s': %s" % (share.name, subdir)
        form = SubShareForm(initial={'name':'%s: %s'%(share.name,name),'filesystem':share.filesystem,'notes':notes})
    return render(request, 'share/new_share.html', {'form': form,'share':share,'subdir':subdir})

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

@login_required
def manage_groups(request):
    context ={'user':JSONRenderer().render(UserSerializer(request.user,include_perms=True).data)}
    return render(request,'account/manage_groups.html',context)

@login_required
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
#            subprocess.check_call(['/bin/chmod','600',AUTHORIZED_KEYS_FILE])
            auth_keys = open(AUTHORIZED_KEYS_FILE, "a")
            auth_keys.write(key.create_authorized_key()+'\n')
            auth_keys.close()
#            subprocess.check_call(['/bin/chmod','400',AUTHORIZED_KEYS_FILE])
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
        return HttpResponseRedirect(reverse('list_directory',kwargs={'share':share.slug_or_id,'subdir':os.path.normpath(subpath) + os.sep}))
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

@login_required
def view_messages(request):
    return render(request, 'account/messages.html', {})

