# Create your views here.
# from django.shortcuts import render_to_response, render
from django.http.response import HttpResponse
from settings.settings import FILES_ROOT
from models import Share
from django.utils import simplejson
from forms import UploadFileForm
def upload_file(request):
    data = {}#{key:val for key,val in request.POST.iteritems()}
    for name,file in request.FILES.iteritems():
        data[file.name]=file.size    
    return HttpResponse(simplejson.dumps(data), mimetype='application/json')
