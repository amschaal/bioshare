# Create your views here.
from django.shortcuts import render_to_response, render, redirect
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseRedirect, HttpResponse,\
    JsonResponse
from settings.settings import FILES_ROOT, AUTHORIZED_KEYS_FILE
from models import Share, SSHKey, MetaData, Tag
from forms import MetaDataForm, json_form_validate
from guardian.shortcuts import get_perms, get_users_with_perms, get_groups_with_perms, remove_perm, assign_perm
import json
from utils import JSONDecorator, json_response, json_error, share_access_decorator, safe_path_decorator, validate_email, fetchall
from django.contrib.auth.models import User, Group
from django.db.models import Q
import os
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view
from bioshareX.forms import ShareForm
from guardian.decorators import permission_required
from django.contrib.sites.models import get_current_site
from bioshareX.utils import ajax_login_required

@ajax_login_required
def get_user(request):
    query = request.REQUEST.get('query')
    try:
        user = User.objects.get(Q(username=query)|Q(email=query))
        return json_response({'user':{'username':user.username,'email':user.email}})
    except Exception, e:
        return json_error([e.message])

@ajax_login_required
def get_address_book(request):
    try:
        emails = fetchall("SELECT u.email FROM biosharex.guardian_userobjectpermission p join auth_user u on p.user_id = u.id where object_pk in (select id from bioshareX_share where owner_id = %d) group by email;" % int(request.user.id))
        groups = Group.objects.all()
        return json_response({'emails':[email[0] for email in emails], 'groups':[g.name for g in groups]})
    except Exception, e:
        return json_error([e.message])

@ajax_login_required
def get_tags(request):
    try:
        tags = Tag.objects.filter(name__icontains=request.GET.get('tag'))
        return json_response({'tags':[tag.name for tag in tags]})
    except Exception, e:
        return json_error([e.message])
    
@share_access_decorator(['admin'])    
def share_with(request,share):
    query = request.REQUEST.get('query')
    exists = []
    new_users = []
    groups = []
    invalid = []
    try:
        emails = [email.strip() for email in query.split(',')]
        for email in emails:
            if email == '':
                continue
            if email.startswith('Group:'):
                name = email.split('Group:')[1]
                try:
                    group = Group.objects.get(name=name)
                    groups.append({'group':{'id':group.id,'name':group.name}})
                except:
                    invalid.append(name)
            elif validate_email(email):
                try:
                    user = User.objects.get(email=email)
                    exists.append({'user':{'username':email}})
                except:
                    new_users.append({'user':{'username':email}})
            else:
                invalid.append(email)
        return json_response({'exists':exists, 'groups':groups,'new_users':new_users,'invalid':invalid})
    except Exception, e:
        return json_error([e.message])

@ajax_login_required
def share_autocomplete(request):
    terms = [term.strip() for term in request.REQUEST.get('query').split()]
    query = reduce(lambda q,value: q&Q(name__icontains=value), terms , Q())
    try:
        share_objs = Share.user_queryset(request.user).filter(query).order_by('-created')[:10]
        shares = [{'id':s.id,'url':reverse('list_directory',kwargs={'share':s.id}),'name':s.name,'notes':s.notes} for s in share_objs]
        return json_response({'status':'success','shares':shares})
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

# @ajax_login_required
# @share_access_decorator(['admin'])
def get_user_permissions(request,share):
    try:
        share = Share.objects.get(id=share)
        user = User.objects.get(username=request.GET.get('username'))
        data = share.get_user_permissions(user)
        return json_response({'permissions':data, 'status':'success'})
    except Exception, e:
        return json_response({'permissions':[], 'status':'error'})
    
# @share_access_decorator(['view_share_files'])
def get_share_metadata(request,share):
    try:
        share = Share.objects.get(id=share)
        return json_response({'id':share.id, 'name':share.name, 'path': share.get_path()})
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
    from smtplib import SMTPException
    emailed=[]
    created=[]
    failed=[]
    site = get_current_site(request)
#     if not request.user.has_perm('admin',share):
#         return json_response({'status':'error','error':'You do not have permission to write to this share.'})
    if json.has_key('groups'):
        for group, permissions in json['groups'].iteritems():
            g = Group.objects.get(id=group)
            current_perms = get_perms(g,share)
            removed_perms = list(set(current_perms) - set(permissions))
            added_perms = list(set(permissions) - set(current_perms))
            for u in g.user_set.all():
                if len(share.get_user_permissions(u,user_specific=True)) == 0 and len(added_perms) > 0 and json['email']:
                    email_users([u],'share/share_subject.txt','share/share_email_body.txt',{'user':u,'share':share,'sharer':request.user,'site':site})
                    emailed.append(u.username)
            for perm in removed_perms:
                remove_perm(perm,g,share)
            for perm in added_perms:
                assign_perm(perm,g,share)

    print 'JSON'
    print json
    if json.has_key('users'):
        for username, permissions in json['users'].iteritems():
            try:
                u = User.objects.get(username=username)
                if len(share.get_user_permissions(u,user_specific=True)) == 0 and json['email']:
                    try:
                        email_users([u],'share/share_subject.txt','share/share_email_body.txt',{'user':u,'share':share,'sharer':request.user,'site':site})
                        emailed.append(username)
                    except:
                        failed.append(username)
            except:
                if len(permissions) > 0:
                    password = User.objects.make_random_password()
                    u = User(username=username,email=username)
                    u.set_password(password)
                    u.save()
                    try:
                        email_users([u],'share/share_subject.txt','share/share_new_email_body.txt',{'user':u,'password':password,'share':share,'sharer':request.user,'site':site})
                        created.append(username)
                    except:
                        failed.append(username)
                        u.delete()
            current_perms = share.get_user_permissions(u,user_specific=True)
            print 'CURRENT'
            print share.get_user_permissions(u,user_specific=True)
            print current_perms
            removed_perms = list(set(current_perms) - set(permissions))
            added_perms = list(set(permissions) - set(current_perms))
            for perm in removed_perms:
                remove_perm(perm,u,share)
            for perm in added_perms:
                assign_perm(perm,u,share)
    data = share.get_permissions(user_specific=True)
    data['messages']=[]
    if len(emailed) > 0:
        data['messages'].append({'type':'info','content':'%s has/have been emailed'%', '.join(emailed)})
    if len(created) > 0:
        data['messages'].append({'type':'info','content':'Accounts has/have been created and emails have been sent to the following email addresses: %s'%', '.join(created)})
    if len(failed) > 0:
        data['messages'].append({'type':'info','content':'Delivery has failed to the following addresses: %s'%', '.join(failed)})
    data['json']=json
    print 'RESPONSE'
    print data
    return json_response(data)

@share_access_decorator(['view_share_files'])
def search_share(request,share,subdir=None):
    from utils import find
    query = request.GET.get('query',False)
    response={}
    if query:
        response['results'] = find(share,"*%s*"%query,subdir)
    else:
        response = {'status':'error'}
    return json_response(response)

@safe_path_decorator()
@share_access_decorator(['write_to_share'])
def edit_metadata(request, share, subpath):
    try:
        if share.get_path_type(subpath) is None:
            raise Exception('The specified file or folder does not exist in this share.')
        metadata = MetaData.objects.get_or_create(share=share, subpath=subpath)[0]
        form = MetaDataForm(request.REQUEST)
        data = json_form_validate(form)
        if not form.is_valid():
            return json_response(data)#return json_error(form.errors)
        tags = []
        for tag in form.cleaned_data['tags'].split(','):
            tag = tag.strip()
            if len(tag) >2 :
                tags.append(Tag.objects.get_or_create(name=tag)[0])
        metadata.tags = tags
        metadata.notes = form.cleaned_data['notes']
        metadata.save()
        name = os.path.basename(os.path.normpath(subpath))
        return json_response({'name':name,'notes':metadata.notes,'tags':[tag.name for tag in tags]})
    except Exception, e:
        return json_error([str(e)])
def delete_ssh_key(request):
    try:
        id = request.POST.get('id')
        key = SSHKey.objects.get(user=request.user,id=id)
        import subprocess, re
#        subprocess.call(['/bin/chmod','600',AUTHORIZED_KEYS_FILE])
        keystring = key.get_key()
#         remove_me = keystring.replace('/','\\/')#re.escape(key.extract_key())
#         command = ['/bin/sed','-i','/%s/d'%remove_me,AUTHORIZED_KEYS_FILE]
#         subprocess.check_call(command)
        f = open(AUTHORIZED_KEYS_FILE,"r")
        lines = f.readlines()
        f.close()
        f = open(AUTHORIZED_KEYS_FILE,"w")
        for line in lines:
            if line.find(keystring) ==-1:
                f.write(line)
        f.close()
#        subprocess.call(['/bin/chmod','400',AUTHORIZED_KEYS_FILE])
        key.delete()
        SSHKey.objects.filter(key__contains=keystring).delete()
        response = {'status':'success','deleted':id}
    except Exception, e:
        response = {'status':'error','message':'Unable to delete ssh key'+str(e)}
    return json_response(response)

"""
Requires: "name", "notes", "filesystem" arguments.
Optional: "link_to_path", "read_only"

"""
@api_view(['POST'])
@permission_required('bioshareX.add_share', return_403=True)
def create_share(request):
    print request.data
    form = ShareForm(request.user,request.data)
    if form.is_valid():
        share = form.save(commit=False)
        share.owner=request.user
        link_to_path = request.data.get('link_to_path',None)
        if link_to_path:
            if not request.user.has_perm('bioshareX.link_to_path'):
                return JsonResponse({'error':"You do not have permission to link to a specific path."},status=400)
            share.link_to_path = link_to_path
        try:
            share.save()
        except Exception, e:
            share.delete()
            print e.message
            return JsonResponse({'error':e.message},status=400)
        site = get_current_site(request)
        return JsonResponse({'url':"https://%s%s"%(site.domain,reverse('list_directory',kwargs={'share':share.id})),'id':share.id})
    else:
        print form.errors
        return JsonResponse({'errors':form.errors},status=400)