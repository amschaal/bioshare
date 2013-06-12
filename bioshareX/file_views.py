# Create your views here.
# from django.shortcuts import render_to_response, render
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response, render
from django.core.urlresolvers import reverse
from settings.settings import FILES_ROOT
from models import Share
from django.utils import simplejson
from forms import UploadFileForm, FolderForm

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
def json_form_validate(form,save=True,html=True,template='ajax/crispy_form.html'):
    data={}
    if form.is_valid():
        data['status']='success'
        if save:
            data['objects']=[form.save()]
    else:
        data['errors']={k: v for k, v in form.errors.items()}
        data['html']= render_to_string(template,{'form':form})
    return data
def create_folder(request, share, subdir=None):
    form = FolderForm(request.POST)
    data = json_form_validate(form)
    if form.is_valid():
        pass#data['']
    return HttpResponse(simplejson.dumps(data), mimetype='application/json')
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
