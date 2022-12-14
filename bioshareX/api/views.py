# Create your views here.
from django.urls import reverse
from django.http.response import JsonResponse, HttpResponse
from settings.settings import AUTHORIZED_KEYS_FILE, SITE_URL
from bioshareX.models import Share, SSHKey, MetaData, Tag
from bioshareX.forms import MetaDataForm, json_form_validate
from guardian.shortcuts import get_perms, get_users_with_perms, remove_perm, assign_perm
from bioshareX.utils import JSONDecorator, json_response, json_error, share_access_decorator, safe_path_decorator, validate_email, fetchall,\
    test_path, du
from django.contrib.auth.models import User, Group
from django.db.models import Q
import os
from rest_framework.decorators import api_view, throttle_classes, action
from bioshareX.forms import ShareForm
from guardian.decorators import permission_required
from bioshareX.utils import ajax_login_required, email_users
from rest_framework import generics, viewsets, status
from bioshareX.models import ShareLog, Message
from bioshareX.api.serializers import ShareLogSerializer, ShareSerializer,\
    GroupSerializer, UserSerializer, MessageSerializer
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from bioshareX.permissions import ManageGroupPermission
from rest_framework.response import Response
from guardian.models import UserObjectPermission
from django.contrib.contenttypes.models import ContentType
import datetime
from bioshareX.api.filters import UserShareFilter, ShareTagFilter,\
    GroupShareFilter, ActiveMessageFilter
from rest_framework.throttling import UserRateThrottle
from django.utils import timezone
import csv

@ajax_login_required
def get_user(request):
    query = request.GET.get('query')
    try:
        user = User.objects.get(Q(username=query)|Q(email=query))
        return JsonResponse({'user':UserSerializer(user).data})
    except Exception as e:
        return JsonResponse({'status':'error','query':query,'errors':[str(e)]},status=status.HTTP_404_NOT_FOUND)

@ajax_login_required
def get_address_book(request):
    try:
        emails = User.objects.filter(shareuserobjectpermission__content_object__in=Share.objects.filter(owner=request.user).values_list('id')).values_list('email').distinct().order_by('email')
        groups = Group.objects.all().order_by('name')
        return json_response({'emails':[email[0] for email in emails], 'groups':[g.name for g in groups]})
    except Exception as e:
        return json_error([str(e)])

@ajax_login_required
def get_tags(request):
    try:
        tags = Tag.objects.filter(name__icontains=request.GET.get('tag'))
        return json_response({'tags':[tag.name for tag in tags]})
    except Exception as e:
        return json_error([str(e)])
    
@share_access_decorator(['admin'])    
def share_with(request,share):
    query = request.POST.get('query',request.GET.get('query'))
    exists = []
    new_users = []
    groups = []
    invalid = []
    try:
        emails = [email.strip().lower() for email in query.split(',')]
        for email in emails:
            if email == '':
                continue
            if email.startswith('group:'):
                name = email.split('group:')[1].lower()
                try:
                    group = Group.objects.get(name__iexact=name)
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
    except Exception as e:
        return json_error([str(e)])

@ajax_login_required
def share_autocomplete(request):
    terms = [term.strip() for term in request.GET.get('query').split()]
    query = reduce(lambda q,value: q&Q(name__icontains=value), terms , Q())
    try:
        share_objs = Share.user_queryset(request.user).filter(query).order_by('-created')[:10]
        shares = [{'id':s.id,'url':reverse('list_directory',kwargs={'share':s.id}),'name':s.name,'notes':s.notes} for s in share_objs]
        return json_response({'status':'success','shares':shares})
    except Exception as e:
        return json_error([str(e)])


def get_group(request):
    query = request.GET.get('query')
    try:
        group = Group.objects.get(name=query)
        return json_response({'group':{'name':group.name}})
    except Exception as e:
        return json_error([str(e)])

@api_view(['GET'])
@share_access_decorator(['admin'])
def get_permissions(request,share):
    data = share.get_permissions(user_specific=True)
    return json_response(data)

@share_access_decorator(['admin'])
@JSONDecorator
def update_share(request,share,json=None):
    share.secure = json['secure']
    share.save()
    return json_response({'status':'okay'})

@api_view(['POST'])
@share_access_decorator(['admin'])
@JSONDecorator
def set_permissions(request,share,json=None):
    from smtplib import SMTPException
    emailed=[]
    created=[]
    failed=[]
#     if not request.user.has_perm('admin',share):
#         return json_response({'status':'error','error':'You do not have permission to write to this share.'})
    if 'groups' in json:
        for group, permissions in json['groups'].items():
            g = Group.objects.get(id__iexact=group)
            current_perms = get_perms(g,share)
            removed_perms = list(set(current_perms) - set(permissions))
            added_perms = list(set(permissions) - set(current_perms))
            for u in g.user_set.all():
                if len(share.get_user_permissions(u,user_specific=True)) == 0 and len(added_perms) > 0 and json['email']:
                    email_users([u],'share/share_subject.txt','share/share_email_body.txt',{'user':u,'share':share,'sharer':request.user,'site_url':SITE_URL})
                    emailed.append(u.username)
            for perm in removed_perms:
                remove_perm(perm,g,share)
            for perm in added_perms:
                assign_perm(perm,g,share)
    if 'users' in json:
        for username, permissions in json['users'].items():
            username = username.lower()
            try:
                u = User.objects.get(username__iexact=username)
                if len(share.get_user_permissions(u,user_specific=True)) == 0 and json['email']:
                    try:
                        email_users([u],'share/share_subject.txt','share/share_email_body.txt',{'user':u,'share':share,'sharer':request.user,'site_url':SITE_URL})
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
                        email_users([u],'share/share_subject.txt','share/share_new_email_body.txt',{'user':u,'password':password,'share':share,'sharer':request.user,'site_url':SITE_URL})
                        created.append(username)
                    except:
                        failed.append(username)
                        u.delete()
            current_perms = share.get_user_permissions(u,user_specific=True)
            removed_perms = list(set(current_perms) - set(permissions))
            added_perms = list(set(permissions) - set(current_perms))
            for perm in removed_perms:
                if u.username not in failed:
                    remove_perm(perm,u,share)
            for perm in added_perms:
                if u.username not in failed:
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
    return json_response(data)

@share_access_decorator(['view_share_files'])
def search_share(request,share,subdir=None):
    from bioshareX.utils import find
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
        form = MetaDataForm(request.POST if request.method == 'POST' else request.GET)
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
    except Exception as e:
        return json_error([str(e)])
@ajax_login_required
def delete_ssh_key(request):
    try:
        id = request.POST.get('id')
        key = SSHKey.objects.get(user=request.user,id=id)
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
    except Exception as e:
        response = {'status':'error','message':'Unable to delete ssh key'+str(e)}
    return json_response(response)

"""
Requires: "name", "notes", "filesystem" arguments.
Optional: "link_to_path", "read_only"

"""
@api_view(['POST'])
@permission_required('bioshareX.add_share', return_403=True)
def create_share(request):
    form = ShareForm(request.user,request.data)
    if form.is_valid():
        share = form.save(commit=False)
        share.owner=request.user
        link_to_path = request.data.get('link_to_path',None)
        if link_to_path:
            if not request.user.has_perm('bioshareX.link_to_path'):
                return JsonResponse({'error':"You do not have permission to link to a specific path."},status=400)
        try:
            share.save()
        except Exception as e:
            share.delete()
            return JsonResponse({'error':str(e)},status=400)
        return JsonResponse({'url':"%s%s"%(SITE_URL,reverse('list_directory',kwargs={'share':share.id})),'id':share.id})
    else:
        return JsonResponse({'errors':form.errors},status=400)

@ajax_login_required
@share_access_decorator(['view_share_files'])
def email_participants(request,share,subdir=None):
    try:
        subject = request.POST.get('subject')
        emails = request.POST.getlist('emails',[])
        users = [u for u in get_users_with_perms(share, attach_perms=False, with_superusers=False, with_group_users=True)]
        if len(emails) > 0:
            users = [u for u in User.objects.filter(id__in=[u.id for u in users]).filter(email__in=emails)]
        body = request.POST.get('body')
        users.append(share.owner)
        email_users(users, ctx_dict={}, subject=subject, body=body,from_email=request.user.email,content_subtype='plain')
        response = {'status':'success','sent_to':[u.email for u in users]}
        return json_response(response)
    except Exception as e:
        return JsonResponse({'errors':[str(e)]},status=400)

class ShareLogList(generics.ListAPIView):
    serializer_class = ShareLogSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = {'action':['icontains'],'user__username':['icontains'],'text':['icontains'],'paths':['icontains'],'share':['exact']}
    def get_queryset(self):
        shares = Share.user_queryset(self.request.user,include_stats=False)
        return ShareLog.objects.filter(share__in=shares)

class ShareViewset(viewsets.ReadOnlyModelViewSet):
    serializer_class = ShareSerializer
    permission_classes = (IsAuthenticated,)
    filter_backends = generics.ListAPIView.filter_backends + [UserShareFilter,ShareTagFilter,GroupShareFilter]
    filterset_fields = {'name':['icontains'],'notes':['icontains'],'owner__username':['icontains'],'path_exists':['exact']}
    ordering_fields = ('name','owner__username','created','updated','stats__num_files','stats__bytes')
    def get_queryset(self):
        return Share.user_queryset(self.request.user,include_stats=False).select_related('owner','stats').prefetch_related('tags','user_permissions__user','group_permissions__group')
    @action(methods=['GET'], detail=True)
    @throttle_classes([UserRateThrottle])
    def directory_size(self, request, *args, **kwargs):
        share = self.get_object()
        subdir = request.query_params.get('subdir','')
        test_path(subdir,share=share)
        size = du(os.path.join(share.get_path(),subdir))
        return Response({'share':share.id,'subdir':subdir,'size':size})
    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated])
    def export(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="shares_{}.csv"'.format(str(timezone.now())[:19].replace(' ','_'))
        writer = csv.writer(response, delimiter='\t')
        writer.writerow(['id','name','url','users','groups','bytes','tags','owner','slug','created','updated','secure','read_only','notes','path_exists'])
        for r in serializer.data:
            writer.writerow([r['id'],r['name'].encode('ascii', 'replace'),r['url'],', '.join(r['users']),', '.join(r['groups']),r['stats'].get('bytes') if r['stats'] else '',', '.join([t['name'].encode('ascii', 'replace') for t in r['tags']]),r['owner'].get('username'),r['slug'],r['created'],r['updated'],r['secure'],r['read_only'],r['notes'].encode('ascii', 'replace'),r['path_exists'] ])
        return response
class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GroupSerializer
    permission_classes = (IsAuthenticated,DjangoModelPermissions,)
    filterset_fields = {'name':['icontains']}
    model = Group
    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.is_staff:
            return Group.objects.all()
        else:
            return self.request.user.groups.all()
    @action(methods=['POST'], detail=True,permission_classes=[ManageGroupPermission])
    def update_users(self, request, *args, **kwargs):
        users =  request.data.get('users')
        group = self.get_object()
#         old_users = GroupSerializer(group).data['users']
#         old_user_ids = [u['id'] for u in old_users]
#         remove_users = set(old_user_ids) - set(user_ids)
#         add_users = set(user_ids) - set(old_user_ids)
        
        group.user_set = [u['id'] for u in users]
        #clear permissions
        ct = ContentType.objects.get_for_model(Group)
        UserObjectPermission.objects.filter(content_type=ct,object_pk=group.id).delete()
        #assign permissions
        for user in users:
            if 'manage_group' in user['permissions']:
                user = User.objects.get(id=user['id'])
                assign_perm('manage_group', user, group)
        return self.retrieve(request,*args,**kwargs)#Response({'status':'success'})
#     @detail_route(['POST'])
#     def remove_user(self,request,*args,**kwargs):
# #         user = request.query_params.get('user')
# #         self.get_object().user_set.remove(user)
#         return Response({'status':'success'})

class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = (IsAuthenticated,)
    filter_backends = (ActiveMessageFilter,)
    model = Message
    def get_queryset(self):
        return Message.objects.all().order_by('-created')
#         return Message.objects.filter(active=True).filter(Q(expires__gte=datetime.datetime.today())|Q(expires=None)).exclude(viewed_by__id=self.request.user.id)
    @action(methods=['POST','GET'], detail=True, permission_classes=[IsAuthenticated])
    def dismiss(self, request, pk=None):
        message = self.get_object()
        message.viewed_by.add(request.user)
        message.save()
        return Response({'status':'Message dismissed'})
