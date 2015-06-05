# Create your views here.
# from django.shortcuts import render_to_response, render
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response, render, redirect
from django.core.urlresolvers import reverse
from settings.settings import FILES_ROOT
from models import Share
# from django.utils import simplejson
import json
from forms import UploadFileForm, FolderForm, json_form_validate, RenameForm
from utils import JSONDecorator, test_path, sizeof_fmt, json_error
from file_utils import istext
import os
from utils import share_access_decorator, safe_path_decorator, json_response
import datetime

def handle_uploaded_file(path,file):
    with open(path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)

@safe_path_decorator(path_param='subdir')
@share_access_decorator(['write_to_share'])
def upload_file(request, share, subdir=None):
    from os.path import join
    PATH = share.get_path()
    if subdir is not None:
        PATH = join(PATH,subdir)
    data = {'share':share.id,'subdir':subdir,'files':[]}#{key:val for key,val in request.POST.iteritems()}
    for name,file in request.FILES.iteritems():
        FILE_PATH = join(PATH,file.name)
        handle_uploaded_file(FILE_PATH,file)
        subpath = file.name if subdir is None else subdir + file.name
        url = reverse('download_file',kwargs={'share':share.id,'subpath':subpath})
        (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat(FILE_PATH)
        data['files'].append({'name':file.name,'size':sizeof_fmt(size),'bytes':size, 'url':url,'modified':datetime.datetime.fromtimestamp(mtime).strftime("%m/%d/%Y %I:%M %p"), 'isText':istext(FILE_PATH)}) 
#         response['url']=reverse('download_file',kwargs={'share':share.id,'subpath':details['subpath']})
#         url 'download_file' share=share.id subpath=subdir|default_if_none:""|add:file.name 
    return json_response(data)

@safe_path_decorator(path_param='subdir')
@share_access_decorator(['write_to_share'])
def create_folder(request, share, subdir=None):
    form = FolderForm(request.POST)
    data = json_form_validate(form)
    if form.is_valid():
        folder_path = share.create_folder(form.cleaned_data['name'],subdir)
        (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat(folder_path)
        data['objects']=[{'name':form.cleaned_data['name'],'modified':datetime.datetime.fromtimestamp(mtime).strftime("%m/%d/%Y %I:%M %p")}]
    return json_response(data)

@safe_path_decorator(path_param='subdir')
@share_access_decorator(['write_to_share'])
def modify_name(request, share, subdir=None):
    import os
    form = RenameForm(request.POST)
    data = json_form_validate(form)
    if form.is_valid():
        if subdir is None:
            from_path = os.path.join(share.get_path(),form.cleaned_data['from_name'])
            to_path = os.path.join(share.get_path(),form.cleaned_data['to_name'])
        else:
            from_path = os.path.join(share.get_path(),subdir,form.cleaned_data['from_name'])
            to_path = os.path.join(share.get_path(),subdir,form.cleaned_data['to_name'])
        os.rename(from_path, to_path)
        data['objects']=[{'from_name':form.cleaned_data['from_name'],'to_name':form.cleaned_data['to_name']}]
    return json_response(data)


@safe_path_decorator(path_param='subdir')
@share_access_decorator(['delete_share_files'])
@JSONDecorator
def delete_paths(request, share, subdir=None, json={}):
    response={'deleted':[],'failed':[]}
    for item in json['selection']:
        test_path(item)
        item_path = item if subdir is None else os.path.join(subdir,item)
        try:
            if share.delete_path(item_path):
                response['deleted'].append(item)
            else:
                response['failed'].append(item)
        except:
            response['failed'].append(item)
    return json_response(response)

@safe_path_decorator(path_param='subdir')
@share_access_decorator(['delete_share_files'])
@JSONDecorator
def move_paths(request, share, subdir=None, json={}):
    response={'moved':[],'failed':[]}
    for item in json['selection']:
        test_path(item)
        item_subpath = item if subdir is None else os.path.join(subdir,item)
        try:
            if share.move_path(item_subpath,json['destination']):
                response['moved'].append(item)
            else:
                response['failed'].append(item)
        except Exception, e:
            print e.message
    return json_response(response)

@safe_path_decorator(path_param='subdir')
@share_access_decorator(['download_share_files'])
@JSONDecorator
def archive_files(request, share, subdir=None, json={}):
    response={}
    try:
        for item in json['selection']:
            test_path(item)
        details = share.create_archive(items=json['selection'],subdir=subdir)
        response['url']=reverse('download_archive',kwargs={'share':share.id,'subpath':details['subpath']})
        return json_response(response)
    except Exception, e:
        return json_error([e.message])
    
@safe_path_decorator()    
@share_access_decorator(['download_share_files'])
def download_file(request, share, subpath=None):
    from sendfile import sendfile
    file_path = os.path.join(share.get_path(),subpath)
    response={'path':file_path}
    return sendfile(request, os.path.realpath(file_path))

@safe_path_decorator()
@share_access_decorator(['download_share_files'])
def download_archive(request, share, subpath):
    from sendfile import sendfile
    file_path = os.path.join(share.get_archive_path(),subpath)
    response={'path':file_path}
    return sendfile(request, os.path.realpath(file_path))
#     return HttpResponse(simplejson.dumps(data), mimetype='application/json')
#     if request.method == 'POST':
#         form = FolderForm(request.POST)
#         if form.is_valid():
#             share = form.save(commit=False)
#             share.owner=request.user
#             share.save()
#             return HttpResponseRedirect(reverse('list_directory',kwargs={'share':share.id}))
#     else:
#         form = FolderForm()
#     return render(request, 'share/new_folder.html', {'form': form})

@safe_path_decorator()    
@share_access_decorator(['download_share_files'])
def preview_file(request, share, subpath):
    from file_utils import get_lines, get_num_lines
    from_line = int(request.GET.get('from',1))
    num_lines = int(request.GET.get('for',100))
    file_path = os.path.join(share.get_path(),subpath)
    response = {'share_id':share.id,'subpath':subpath,'content':get_lines(file_path,from_line,from_line+num_lines-1),'from':from_line,'for':num_lines,'next':{'from':from_line+num_lines,'for':num_lines}}
    if 'get_total' in request.GET:
        response['total'] = get_num_lines(file_path)
    return json_response(response)

@share_access_decorator(['download_share_files'])
def get_directories(request, share):
    import os
    response=[]
    directory = request.GET.get('directory','')
    full_path = os.path.join(share.get_path(),directory)
    dirs = [name for name in os.listdir(full_path) if os.path.isdir(os.path.join(full_path, name))]
    for dir in dirs:
        key = os.path.join(directory,dir)
        response.append({"title": dir, "isFolder": True, "isLazy": True, "key": key})
    return json_response(response)
#     return sendfile(request, os.path.realpath(file_path))
