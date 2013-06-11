# Create your views here.
# from django.shortcuts import render_to_response, render
from django.http.response import HttpResponse
from settings.settings import FILES_ROOT
from models import Share
from django.utils import simplejson
from forms import UploadFileForm

def handle_uploaded_file(path,file):
    with open(path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)


def upload_file(request, share, subdir=None):
    from os.path import join
    PATH = join(FILES_ROOT,share)
    if subdir is not None:
        PATH = join(PATH,subdir)
    data = {'share':share,'subdir':subdir}#{key:val for key,val in request.POST.iteritems()}
    for name,file in request.FILES.iteritems():
        FILE_PATH = join(PATH,file.name)
        handle_uploaded_file(FILE_PATH,file)
        data[file.name]=file.size    
    return HttpResponse(simplejson.dumps(data), mimetype='application/json')
