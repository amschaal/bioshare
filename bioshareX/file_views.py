# Create your views here.
# from django.shortcuts import render_to_response, render
import datetime
# from django.utils import simplejson
import json
import os
import re
from os.path import join

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.decorators import permission_required

from bioshareX.file_utils import get_lines, get_num_lines, istext
from bioshareX.forms import FolderForm, RenameForm, SymlinkForm, json_form_validate
from bioshareX.models import Share, ShareLog
from bioshareX.utils import (JSONDecorator, find_symlink, json_error,
                             json_response, md5sum, safe_path_decorator,
                             share_access_decorator, sizeof_fmt, test_path)


def handle_uploaded_file(path,file):
    with open(path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)

def clean_filename(filename):
    filename = re.sub(settings.UNDERSCORE_REGEX,'_', filename)
    filename = re.sub(settings.STRIP_REGEX,'', filename)
    return filename

@share_access_decorator(['write_to_share'])
@safe_path_decorator(path_param='subdir', write=True)
def upload_file(request, share, subdir=None):

    os.umask(settings.UMASK)
    PATH = share.get_path()
    if subdir is not None:
        PATH = join(PATH,subdir)
    data = {'share':share.id,'subdir':subdir,'files':[]}#{key:val for key,val in request.POST.items()}
    for name,file in request.FILES.items():
        filename = clean_filename(file.name)
        FILE_PATH = join(PATH,filename)
        handle_uploaded_file(FILE_PATH,file)
        subpath = filename if subdir is None else subdir + filename
        url = reverse('download_file',kwargs={'share':share.id,'subpath':subpath})
        (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat(FILE_PATH)
        data['files'].append({'name':filename,'extension':filename.split('.').pop() if '.' in filename else '','size':sizeof_fmt(size),'bytes':size, 'url':url,'modified':datetime.datetime.fromtimestamp(mtime).strftime("%m/%d/%Y %H:%M"), 'isText':istext(FILE_PATH)}) 
#         response['url']=reverse('download_file',kwargs={'share':share.id,'subpath':details['subpath']})
#         url 'download_file' share=share.id subpath=subdir|default_if_none:""|add:file.name 
    ShareLog.create(share=share,user=request.user,action=ShareLog.ACTION_FILE_ADDED,paths=[clean_filename(file.name) for file in request.FILES.values()],subdir=subdir)
    return json_response(data)

@share_access_decorator(['write_to_share'])
@safe_path_decorator(path_param='subdir', write=True)
def create_folder(request, share, subdir=None):
    form = FolderForm(request.POST)
    data = json_form_validate(form)
    if form.is_valid():
        try:
            folder_path = share.create_folder(form.cleaned_data['name'],subdir)
        except Exception as e:
            return json_error([str(e)])
        (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat(folder_path)
        data['objects']=[{'name':form.cleaned_data['name'],'modified':datetime.datetime.fromtimestamp(mtime).strftime("%m/%d/%Y %H:%M")}]
        ShareLog.create(share=share,user=request.user,action=ShareLog.ACTION_FOLDER_CREATED,paths=[form.cleaned_data['name']],subdir=subdir)
        return json_response(data)
    else:
        return json_error([error for name, error in form.errors.items()])

@permission_required('bioshareX.link_to_path', raise_exception=True)
@share_access_decorator(['write_to_share'])
@safe_path_decorator(path_param='subdir', write=True)
def create_symlink(request, share, subdir=None):
    form = SymlinkForm(request.user, request.POST)
    data = json_form_validate(form)
    if form.is_valid():
        if subdir:
            link_path = os.path.join(share.get_path(),subdir,form.cleaned_data['name'])
        else:
            link_path = os.path.join(share.get_path(),form.cleaned_data['name'])
        os.symlink(form.cleaned_data['target'], link_path)
        (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat(link_path)
        data['objects']=[{'name':form.cleaned_data['name'],'modified':datetime.datetime.fromtimestamp(mtime).strftime("%m/%d/%Y %H:%M"), 'target': form.cleaned_data['target']}]
        ShareLog.create(share=share,user=request.user,action=ShareLog.ACTION_LINK_CREATED,paths=[form.cleaned_data['name']],subdir=subdir)
        share.check_paths(True)
        return json_response(data)
    else:
        return json_error([error for name, error in form.errors.items()])

@permission_required('bioshareX.link_to_path', raise_exception=True)
@share_access_decorator(['write_to_share'])
@safe_path_decorator(path_param='subpath')
def unlink(request, share, subpath):
    path = os.path.join(share.get_path(), subpath)
    if os.path.islink(path):
        os.unlink(path)
        ShareLog.create(share=share,user=request.user,action=ShareLog.ACTION_LINK_DELETED,paths=subpath)
        share.check_paths(True)
        return json_response({})
    else:
        return json_error(messages=['No symlink at path specified.'])

@share_access_decorator(['write_to_share'])
@safe_path_decorator(path_param='subdir', write=True)
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
        ShareLog.create(share=share,user=request.user,action=ShareLog.ACTION_RENAMED,text='"%s" renamed to "%s"'%(form.cleaned_data['from_name'],form.cleaned_data['to_name']),paths=[from_path],subdir=subdir)
    return json_response(data)


@share_access_decorator(['delete_share_files'])
@safe_path_decorator(path_param='subdir', write=True)
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
    ShareLog.create(share=share,user=request.user,action=ShareLog.ACTION_DELETED,paths=json['selection'],subdir=subdir)
    return json_response(response)

@share_access_decorator(['delete_share_files'])
@safe_path_decorator(path_param='subdir', write=True)
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
        except Exception as e:
            pass
    text = '%s moved from "%s" to "%s"' % (', '.join(response['moved']), subdir if subdir else '', json['destination'])
    ShareLog.create(share=share,user=request.user,action=ShareLog.ACTION_MOVED,text=text,paths=json['selection'],subdir=subdir)
    return json_response(response)

@share_access_decorator(['download_share_files'])
@safe_path_decorator(path_param='subdir')
# @JSONDecorator
def download_archive_stream(request, share, subdir=None):
#     try:
    share.last_data_access = timezone.now()
    share.save()
    selection = request.GET.get('selection','').split(',')
    path = share.get_path()
    if subdir:
        path = os.path.join(path,subdir)
    for item in selection:
        test_path(item)
        if find_symlink(os.path.join(path,item)):
            return json_error(['Item {} is or contained symlinks.  It is not eligible to be archived.'.format(item)])
    try:
        return share.create_archive_stream(items=selection,subdir=subdir)
    except Exception as e:
        return json_error([str(e)])

@share_access_decorator(['download_share_files'])
@safe_path_decorator()    
def download_file(request, share, subpath=None):
    from sendfile import sendfile
    share.last_data_access = timezone.now()
    share.save()
    file_path = os.path.join(share.get_path(),subpath)
    response={'path':file_path}
    return sendfile(request, os.path.realpath(file_path))

@share_access_decorator(['download_share_files'])
@safe_path_decorator()    
def preview_file(request, share, subpath):
    from_line = int(request.GET.get('from',1))
    num_lines = int(request.GET.get('for',100))
    file_path = os.path.join(share.get_path(),subpath)
    try:
        content = get_lines(file_path,from_line,from_line+num_lines-1)
        response = {'share_id':share.id,'subpath':subpath,'content':content,'from':from_line,'for':num_lines,'next':{'from':from_line+num_lines,'for':num_lines}}
        if 'get_total' in request.GET:
            response['total'] = get_num_lines(file_path)
        return json_response(response)
    except Exception as e:
        content = "Unable to preview file.  This file may not be a plain text file, or has unsupported characters."
        response = {'share_id':share.id,'subpath':subpath,'content':content,'from':from_line,'for':num_lines,'next':{'from':from_line+num_lines,'for':num_lines}}
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

@share_access_decorator([Share.PERMISSION_VIEW])
@safe_path_decorator()    
def get_md5sum(request, share, subpath):
    file_path = os.path.join(share.get_path(),subpath)
    try:
        return json_response({'md5sum':md5sum(file_path),'path':subpath})
    except Exception as e:
        return json_error(str(e))