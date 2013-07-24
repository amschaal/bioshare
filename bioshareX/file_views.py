# Create your views here.
# from django.shortcuts import render_to_response, render
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response, render, redirect
from django.core.urlresolvers import reverse
from settings.settings import FILES_ROOT
from models import Share
from django.utils import simplejson
from forms import UploadFileForm, FolderForm, json_form_validate
from utils import JSONDecorator, sizeof_fmt, json_error
import os
from utils import share_access_decorator, json_response

def handle_uploaded_file(path,file):
    with open(path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)

@share_access_decorator(['write_to_share'])
def upload_file(request, share, subdir=None):
    from os.path import join
    from os import stat
    import datetime
    PATH = share.get_path()
    if subdir is not None:
        PATH = join(PATH,subdir)
    data = {'share':share.id,'subdir':subdir,'files':[]}#{key:val for key,val in request.POST.iteritems()}
    for name,file in request.FILES.iteritems():
        FILE_PATH = join(PATH,file.name)
        handle_uploaded_file(FILE_PATH,file)
        subpath = file.name if subdir is None else subdir + file.name
        url = reverse('download_file',kwargs={'share':share.id,'subpath':subpath})
        (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = stat(FILE_PATH)
        data['files'].append({'name':file.name,'size':sizeof_fmt(size),'bytes':size, 'url':url,'modified':datetime.datetime.fromtimestamp(mtime).strftime("%b %d, %Y %H:%M")}) 
#         response['url']=reverse('download_file',kwargs={'share':share.id,'subpath':details['subpath']})
#         url 'download_file' share=share.id subpath=subdir|default_if_none:""|add:file.name 
    return json_response(data)

@share_access_decorator(['write_to_share'])
def create_folder(request, share, subdir=None):
    form = FolderForm(request.POST)
    data = json_form_validate(form)
    if form.is_valid():
        share.create_folder(form.cleaned_data['name'],subdir)
        data['objects']=[{'name':form.cleaned_data['name']}]
    return json_response(data)

@share_access_decorator(['delete_share_files'])
@JSONDecorator
def delete_paths(request, share, subdir=None, json={}):
    response={'deleted':[],'failed':[]}
    for item in json['selection']:
        item_path = item if subdir is None else os.path.join(subdir,item)
        try:
            if share.delete_path(item_path):
                response['deleted'].append(item)
            else:
                response['failed'].append(item)
        except:
            response['failed'].append(item)
    return json_response(response)

@share_access_decorator(['download_share_files'])
@JSONDecorator
def archive_files(request, share, subdir=None, json={}):
    response={}
    try:
        details = share.create_archive(items=json['selection'],subdir=subdir)
        response['url']=reverse('download_archive',kwargs={'share':share.id,'subpath':details['subpath']})
        return json_response(response)
    except Exception, e:
        return json_error([e.message])
@share_access_decorator(['download_share_files'])
def download_file(request, share, subpath=None):
    from sendfile import sendfile
    file_path = os.path.join(share.get_path(),subpath)
    response={'path':file_path}
    return sendfile(request, file_path)
    return json_response(response)

@share_access_decorator(['download_share_files'])
def download_archive(request, share, subpath):
    from sendfile import sendfile
    file_path = os.path.join(share.get_archive_path(),subpath)
    response={'path':file_path}
    return sendfile(request, file_path)
    return json_response(response)
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
