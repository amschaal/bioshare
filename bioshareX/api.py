# Create your views here.
from django.shortcuts import render_to_response, render, redirect
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseRedirect, HttpResponse
from settings.settings import FILES_ROOT, AUTHORIZED_KEYS_FILE
from models import Share, SSHKey
from forms import ShareForm, FolderForm
from guardian.shortcuts import get_perms, get_users_with_perms, get_groups_with_perms, remove_perm, assign_perm
from django.utils import simplejson
from utils import JSONDecorator, json_response, json_error, share_access_decorator, validate_email
from django.contrib.auth.models import User, Group
from django.db.models import Q

def get_user(request):
    query = request.REQUEST.get('query')
    try:
        user = User.objects.get(Q(username=query)|Q(email=query))
        return json_response({'user':{'username':user.username,'email':user.email}})
    except Exception, e:
        return json_error([e.message])

def share_with_emails(request):
    query = request.REQUEST.get('query')
    exists = []
    new_users = []
    invalid = []
    try:
        emails = [email.strip() for email in query.split(',')]
        for email in emails:
            if validate_email(email):
                try:
                    user = User.objects.get(email=email)
                    exists.append({'user':{'username':email}})
                except:
                    new_users.append({'user':{'username':email}})
            else:
                invalid.append(email)
        return json_response({'exists':exists,'new_users':new_users,'invalid':invalid})
    except Exception, e:
        return json_error([e.message])


def get_group(request):
    query = request.REQUEST.get('query')
    try:
        group = Group.objects.get(name=query)
        return json_response({'group':{'name':group.name}})
    except Exception, e:
        return json_error([e.message])
    
@share_access_decorator(['admin'])
def get_permissions(request,share):
    data = share.get_permissions(user_specific=True)
    return json_response(data)

def get_user_permissions(request,share):
    try:
        share = Share.objects.get(id=share)
        user = User.objects.get(username=request.GET.get('username'))
        data = share.get_user_permissions(user)
        return json_response({'permissions':data, 'status':'success'})
    except Exception, e:
        return json_response({'permissions':[], 'status':'error'})

@share_access_decorator(['admin'])
@JSONDecorator
def update_share(request,share,json=None):
    share.secure = json['secure']
    share.save()
    return json_response({'status':'okay'})

@share_access_decorator(['admin'])
@JSONDecorator
def set_permissions(request,share,json=None):
    from bioshareX.utils import email_users
    from django.contrib.sites.models import get_current_site
    site = get_current_site(request)
#     if not request.user.has_perm('admin',share_obj):
#         return json_response({'status':'error','error':'You do not have permission to write to this share.'})
    if json.has_key('groups'):
        for group, permissions in json['groups'].iteritems():
            g = Group.objects.get(name=group)
            current_perms = get_perms(g,share)
            removed_perms = list(set(current_perms) - set(permissions))
            added_perms = list(set(permissions) - set(current_perms))
            for perm in removed_perms:
                remove_perm(perm,g,share)
            for perm in added_perms:
                assign_perm(perm,g,share)
    if json.has_key('users'):
        for username, permissions in json['users'].iteritems():
            try:
                u = User.objects.get(username=username)
                
                if len(share.get_user_permissions(u,user_specific=True)) == 0:
                    email_users([u],'share/share_subject.txt','share/share_email_body.txt',{'user':u,'share':share,'sharer':request.user,'site':site})
            except:
                if len(permissions) > 0:
                    password = User.objects.make_random_password()
                    u = User(username=username,email=username)
                    u.set_password(password)
                    u.save()
                    email_users([u],'share/share_subject.txt','share/share_new_email_body.txt',{'user':u,'password':password,'share':share,'sharer':request.user,'site':site})
            current_perms = share.get_user_permissions(u,user_specific=True)
            removed_perms = list(set(current_perms) - set(permissions))
            added_perms = list(set(permissions) - set(current_perms))
            for perm in removed_perms:
                remove_perm(perm,u,share)
            for perm in added_perms:
                assign_perm(perm,u,share)
    data = share.get_permissions(user_specific=True)
    data['json']=json
    return json_response(data)

@share_access_decorator(['view_share_files'])
def search_share(request,share,subdir=None):
    from utils import find
    query = request.GET.get('query',False)
    response={}
    if query:
        from os.path import join
        path = share.get_path() if subdir is None else join(share.get_path(),subdir)
        response['results'] = find(path,query)
    else:
        response = {'status':'error'}
    return json_response(response)

def delete_ssh_key(request):
    try:
        id = request.POST.get('id')
        key = SSHKey.objects.get(user=request.user,id=id)
        import subprocess, re
        subprocess.call(['sudo','/bin/chmod','660',AUTHORIZED_KEYS_FILE])
        keystring = key.get_key()
        remove_me = keystring.replace('/','\/')#re.escape(key.extract_key())
        command = ['/bin/sed','-i','/%s/d'%remove_me,AUTHORIZED_KEYS_FILE]
        subprocess.call(command)
        subprocess.call(['sudo','/bin/chmod','600',AUTHORIZED_KEYS_FILE])
        key.delete()
        SSHKey.objects.filter(key__contains=keystring).delete()
        response = {'status':'success','deleted':id}
    except Exception, e:
        response = {'status':'error','message':'Unable to delete ssh key'+str(e)}
    return json_response(response)