# Create your views here.
# from django.shortcuts import render_to_response, render
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response, render
from django.core.urlresolvers import reverse
from settings.settings import FILES_ROOT
from models import Share
from django.utils import simplejson
from forms import UploadFileForm, FolderForm
import os

def handle_uploaded_file(path,file):
    with open(path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)


def upload_file(request, share, subdir=None):
    from os.path import join
    PATH = join(FILES_ROOT,share)
    if subdir is not None:
        PATH = join(PATH,subdir)
    data = {'share':share,'subdir':subdir,'files':[]}#{key:val for key,val in request.POST.iteritems()}
    for name,file in request.FILES.iteritems():
        FILE_PATH = join(PATH,file.name)
        handle_uploaded_file(FILE_PATH,file)
        data['files'].append({'name':file.name,'size':file.size})  
    return HttpResponse(simplejson.dumps(data), mimetype='application/json')

from django.template.loader import render_to_string
def json_form_validate(form,save=False,html=True,template='ajax/crispy_form.html'):
    data={}
    if form.is_valid():
        data['status']='success'
        if save:
            try:
                data['objects']=[form.save()]
            except:
                pass
    else:
        data['status']='error'
        data['errors']={k: v for k, v in form.errors.items()}
        data['html']= render_to_string(template,{'form':form})
    return data
def create_folder(request, share, subdir=None):
    share = Share.objects.get(id=share)
    form = FolderForm(request.POST)
    data = json_form_validate(form)
    if form.is_valid():
        share.create_folder(form.cleaned_data['name'],subdir)
        data['objects']=[{'name':form.cleaned_data['name']}]
    return HttpResponse(simplejson.dumps(data), mimetype='application/json')


class JSONDecorator(object):
        def __init__(self, orig_func):
                self.orig_func = orig_func
        def __call__(self,  *args, **kwargs):
                import json
                json_arg = args[0].REQUEST.get('json',None)
                if json_arg is not None:
                    kwargs['json']=json.loads(json_arg)
                return self.orig_func(*args, **kwargs)

@JSONDecorator
def delete_paths(request, share, subdir=None, json={}):
    share = Share.objects.get(id=share)
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
    return HttpResponse(simplejson.dumps(response), mimetype='application/json')

@JSONDecorator
def archive_files(request, share, subdir=None, json={}):
    share = Share.objects.get(id=share)
    response={}
    details = share.create_archive(items=json['selection'],subdir=subdir)
    response['url']=reverse('download_file',kwargs={'share':share.id,'subpath':details['subpath']})
    return HttpResponse(simplejson.dumps(response), mimetype='application/json')

def download_file(request, share, subpath=None):
    from sendfile import sendfile
    share = Share.objects.get(id=share)
    file_path = os.path.join(share.get_path(),subpath)
    response={'path':file_path}
    return sendfile(request, file_path)
    return HttpResponse(simplejson.dumps(response), mimetype='application/json')
    
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
