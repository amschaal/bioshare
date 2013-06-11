# Create your views here.
from django.shortcuts import render_to_response, render
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseRedirect
from settings.settings import FILES_ROOT
from models import Share
from forms import ShareForm

def index(request):
    # View code here...
    return render_to_response('index.html', {"message": "Hi there"})

def list_directory(request,share,subdir=None):
    from os import listdir
    from os.path import isfile, join, getsize
    PATH = join(FILES_ROOT,share)
    if subdir is not None:
        PATH = join(PATH,subdir)
    file_list=[]
    dir_list=[]
    for name in listdir(PATH):
        path = join(PATH,name)
        if isfile(path):
            file={'name':name,'size':getsize(path)}
            file_list.append(file)
        else:
            dir={'name':name,'size':getsize(path)}
            dir_list.append(dir)
    return render(request,'list.html', {"files":file_list,"directories":dir_list,"path":PATH,"share":share,"subdir": subdir})

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
    