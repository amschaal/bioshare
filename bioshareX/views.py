# Create your views here.
import codecs
import json
import os
import re
from os import listdir
from os.path import isdir, isfile, join

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http.response import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls.base import reverse
from django.views.decorators.cache import never_cache
from django.db import transaction
from guardian.decorators import permission_required
from guardian.shortcuts import assign_perm
from rest_framework.renderers import JSONRenderer

from bioshareX.api.serializers import UserSerializer
from bioshareX.forms import (FolderForm, GroupForm, GroupProfileForm,
                             MetaDataForm, PasswordChangeForm, RenameForm,
                             ShareForm, SSHKeyForm, SubShareForm, SymlinkForm)
from bioshareX.models import GroupProfile, Share, ShareStats, SSHKey
from bioshareX.utils import (check_symlinks_dfs, find, find_symlinks, get_all_symlinks, get_setting, json_response, list_share_dir,
                             safe_path_decorator, share_access_decorator,
                             sizeof_fmt)


def index(request):
    # View code here...
    return render(request,'index.html', {"message": "Hi there"})

def group(request,group_id):
    group = Group.objects.get(id=group_id)
    return render(request,'groups/group.html', {"group": group})

@permission_required('auth.manage_group',(Group,'id','group_id'))
def manage_group(request,group_id):
    group = Group.objects.get(id=group_id)
    return render(request,'groups/manage_group.html', {"group": group})

# @permission_required('auth.manage_groups',(Group,'id','group_id'))
def create_modify_group(request,group_id=None):
    group = Group.objects.get(id=group_id) if group_id else None
    if not request.user.is_staff:# and not (request.user.has_perm('auth.add_group') and not group)
        return forbidden(request)
    profile = GroupProfile.objects.filter(group=group).first() if group else None
    if request.method == 'GET':
        group_form = GroupForm(instance=group)
        profile_form = GroupProfileForm(instance=profile)
    if request.method == 'POST':
        group_form = GroupForm(request.POST,instance=group)
        profile_form = GroupProfileForm(request.POST,initial={'group':group,'created_by':request.user},instance=profile)
        if group_form.is_valid() and profile_form.is_valid():
            group = group_form.save()
            profile_form.save(group,request.user)
            return redirect('manage_group',group_id=group.id)
    return render(request,'groups/create_modify_group.html', {'group': group,'group_form':group_form,'profile_form':profile_form})
@safe_path_decorator()
def redirect_old_path(request, id, subpath=''):
    share_id = '00000%s'%id
    return HttpResponseRedirect(reverse('go_to_file_or_folder',kwargs={'share':share_id,'subpath':subpath}))

def tag_cloud(request):
    # View code here...
    return render(request,'viz/cloud.html')
@login_required
def list_shares(request,group_id=None):
    # View code here...
#     shares = Share.objects.filter(owner=request.user)
#     shared_with_me = get_objects_for_user(request.user, 'bioshareX.view_share_files')
    group = None if not group_id else Group.objects.get(id=group_id)
    if not group:
        total_size = sizeof_fmt(sum([s.bytes for s in ShareStats.objects.filter(share__owner=request.user)]))
    else:
        total_size = sizeof_fmt(sum([s.bytes for s in ShareStats.objects.filter(share__in=group.shares.all())]))
    return render(request,'share/shares.html', {"total_size":total_size,"bad_paths":'bad_paths' in request.GET,"locked":'locked' in request.GET,"group":group})

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
            share = form.save(commit=False) #gets commited in next call?
            share.set_tags(form.cleaned_data['tags'].split(',')) 
            return HttpResponseRedirect(reverse('list_directory',kwargs={'share':share.slug_or_id}))
    else:
        tags = ','.join([tag.name for tag in share.tags.all()])
        form = ShareForm(request.user,instance=share)
        form.fields['tags'].initial = tags
    return render(request, 'share/edit_share.html', {'form': form})

@safe_path_decorator(path_param='subdir')
@share_access_decorator(['view_share_files'])
@never_cache
def list_directory(request,share,subdir=None):
    if not share.check_path(subdir=subdir):
        return render(request,'error.html', {"message": "Unable to locate the files.  It is possible that the directory has been moved, renamed, or deleted.","share":share,"subdir":subdir})
    files,directories,errors = list_share_dir(share,subdir=subdir,ajax=request.is_ajax())
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
    emails = sorted([u.email for u in share.get_users_with_permissions()])
    readme = None
    is_realpath = share.is_realpath(subdir)
    if not is_realpath: # Don't allow any write operations if it isn't a real directory under the share root
        if Share.PERMISSION_DELETE in share_perms:
            share_perms.remove(Share.PERMISSION_DELETE)
        if Share.PERMISSION_WRITE in share_perms:
            share_perms.remove(Share.PERMISSION_WRITE)
    #The following block is for markdown rendering
    if os.path.isfile(os.path.join(PATH,'README.md')):
        import markdown
        input_file = codecs.open(os.path.join(PATH,'README.md'), mode="r", encoding="utf-8")
        text = input_file.read()
        readme = markdown.markdown(text,extensions=['fenced_code','tables','nl2br'])
        download_base = reverse('download_file',kwargs={'share':share.id,'subpath':subdir if subdir else ''})
        readme = re.sub(r'src="(?!http)',r'src="{0}'.format(download_base),readme)
    return render(request,'list.html', {"session_cookie":request.COOKIES.get('sessionid'),"files":files,"directories":directories.values(),"errors":errors,"path":PATH,"share":share,"subshare":subshare,"subdir": subdir, "is_realpath": is_realpath,'rsync_url':get_setting('RSYNC_URL',None),'HOST':get_setting('HOST',None),'SFTP_PORT':get_setting('SFTP_PORT',None),"folder_form":FolderForm(),"link_form":SymlinkForm(request.user),"metadata_form":MetaDataForm(), "rename_form":RenameForm(),"request":request,"owner":owner,"share_perms":share_perms,"all_perms":all_perms,"share_perms_json":json.dumps(share_perms),"shared_users":shared_users,"shared_groups":shared_groups,"emails":emails, "readme":readme})

@safe_path_decorator(path_param='subdir')
@share_access_decorator(['view_share_files','download_share_files'])
def wget_listing(request,share,subdir=None):
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
def create_share(request,group_id=None):
    if not request.user.has_perm('bioshareX.add_share'):
        return render(request,'index.html', {"message": "You must have permissions to create a Share.  You may request access from the <a href=\"mailto:webmaster@genomecenter.ucdavis.edu\">webmaster</a>."})
    group = None if not group_id else Group.objects.get(id=group_id)
    if request.method == 'POST':
        form = ShareForm(request.user,request.POST)
        with transaction.atomic():
            if form.is_valid():
                share = form.save(commit=False)
                if not getattr(share, 'owner',None):
                    share.owner=request.user
                try:
                    share.save()
                    share.set_tags(form.cleaned_data['tags'].split(','))
                except Exception as e:
                    share.delete()
                    return render(request, 'share/new_share.html', {'form': form,'group':group, 'error':str(e)})
                if group:
                    assign_perm(Share.PERMISSION_VIEW,group,share)
                    assign_perm(Share.PERMISSION_DOWNLOAD,group,share)
                return HttpResponseRedirect(reverse('list_directory',kwargs={'share':share.slug_or_id}))
    else:
        form = ShareForm(request.user)
    return render(request, 'share/new_share.html', {'form': form,'group':group})

@safe_path_decorator(path_param='subdir')
@share_access_decorator(['admin'])
def create_subshare(request,share,subdir):
    if not share.is_realpath(subdir):
        raise PermissionError('Linked directories are not eligible to become subshares. {} {}'.format(share.get_path(),subdir))
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
            except Exception as e:
                subshare.delete()
                return render(request, 'share/new_share.html', {'form': form, 'error':str(e),'share':share,'subdir':subdir})
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
    context ={'user':JSONRenderer().render(UserSerializer(request.user,include_perms=True).data).decode('utf-8')}
    return render(request,'groups/groups.html',context)

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
#            subprocess.check_call(['/bin/chmod','600',AUTHORIZED_KEYS_FILE])
            auth_keys = open(AUTHORIZED_KEYS_FILE, "a")
            auth_keys.write(key.create_authorized_key()+'\n')
            auth_keys.close()
#            subprocess.check_call(['/bin/chmod','400',AUTHORIZED_KEYS_FILE])
            return HttpResponseRedirect(reverse('list_ssh_keys'))
    else:
        form = SSHKeyForm()
    return render(request, 'ssh/new_key.html', {'form': form})

@safe_path_decorator()
@share_access_decorator(['view_share_files'])    
def go_to_file_or_folder(request, share, subpath=None):
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

def locked(request, share):
    share = Share.get_by_slug_or_id(share)
    if not share.locked:
        return redirect('list_directory', share=share.id)
    if request.user.is_superuser:
        message = share.check_paths(check_symlinks=True)
        symlinks = get_all_symlinks(share.get_path())
        return render(request,'share/locked.html', {"share":share, "symlinks": symlinks, "message": message})
    else:    
        return render(request,'share/locked.html', {"share":share})

def unlock(request, share):
    share = Share.get_by_slug_or_id(share)
    if not request.user.is_superuser:
        raise PermissionError('Only super users may unlock shares')
    share.check_paths(check_symlinks=True)
    if not share.illegal_path_found:
        share.locked = False
        share.save()
        return redirect('list_directory', share=share.id)
    else:
        return redirect('locked', share=share.id)

@share_access_decorator(['admin'])
def view_links(request, share):
    if share.owner != request.user and not request.user.is_superuser:
        return redirect('list_directory', share=share.id)
    message = share.check_paths(check_symlinks=True)
    symlinks = get_all_symlinks(share.get_path())
    return render(request,'share/links.html', {"share":share, "symlinks": symlinks, "message": message})