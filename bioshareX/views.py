# Create your views here.
from django.shortcuts import render_to_response, render, redirect
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseRedirect
from settings.settings import FILES_ROOT
from models import Share, SSHKey
from forms import ShareForm, FolderForm, SSHKeyForm
from guardian.shortcuts import get_perms, get_users_with_perms
from django.utils import simplejson
from bioshareX.utils import share_access_decorator
from django.contrib.auth.decorators import login_required

def index(request):
    # View code here...
    return render(request,'index.html', {"message": "Hi there"})

def forbidden(request):
    # View code here...
    return render(request,'index.html', {"message": "You have tried to access a forbidden resource."})

@share_access_decorator(['admin'])
def share_permissions(request,share):
#     users = get_users_with_perms(share,attach_perms=True, with_group_users=False)
    return render(request,'share/permissions.html', {"share":share,"request":request})

@share_access_decorator(['view_share_files'])
def list_directory(request,share,subdir=None):
    from os import listdir
    from os.path import isfile, join, getsize
    PATH = share.get_path()
    if subdir is not None:
        PATH = join(PATH,subdir)
    share_perms = share.get_user_permissions(request.user)
    if not share.secure:
        share_perms = list(set(share_perms+['view_share_files','download_share_files']))
    file_list=[]
    dir_list=[]
    for name in listdir(PATH):
        path = join(PATH,name)
        if isfile(path):
            file={'name':name,'size':getsize(path)}
            file_list.append(file)
        elif name not in ['.removed']:#,'.archives'
            dir={'name':name,'size':getsize(path)}
            dir_list.append(dir)
    return render(request,'list.html', {"files":file_list,"directories":dir_list,"path":PATH,"share":share,"subdir": subdir,"folder_form":FolderForm(),"request":request,"share_perms":share_perms,"share_perms_json":simplejson.dumps(share_perms)})

@login_required
def create_share(request):
    if request.method == 'POST':
        form = ShareForm(request.POST)
        if form.is_valid():
            share = form.save(commit=False)
            share.owner=request.user
            share.save()
            return HttpResponseRedirect(reverse('list_directory',kwargs={'share':share.id}))
    else:
        form = ShareForm()
    return render(request, 'share/new_share.html', {'form': form})

def list_ssh_keys(request):
    context ={'keys':SSHKey.objects.filter(user=request.user)}
    return render(request,'ssh/list_keys.html',context)

@login_required
def create_ssh_key(request):
    if request.method == 'POST':
        form = SSHKeyForm(request.POST)
        if form.is_valid():
            key = form.save(commit=False)
            key.user=request.user
            key.save()
            return HttpResponseRedirect(reverse('list_ssh_keys'))
    else:
        form = SSHKeyForm()
    return render(request, 'ssh/new_key.html', {'form': form})



@share_access_decorator(['view_share_files'])    
def go_to_file_or_folder(request, share, subpath=None):
    from os.path import isdir, isfile, join
    path = share.get_path() if subpath is None else join(share.get_path(),subpath)
    if isdir(path):
        return HttpResponseRedirect(reverse('list_directory',kwargs={'share':share.id,'subdir':subpath}))
    else:# isfile(path)
        return HttpResponseRedirect(reverse('download_file',kwargs={'share':share.id,'subpath':subpath}))
