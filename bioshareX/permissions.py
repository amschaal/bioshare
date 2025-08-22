from django.http.response import Http404
from .utils import email_users
from rest_framework.permissions import SAFE_METHODS, DjangoObjectPermissions
from guardian.shortcuts import (assign_perm, get_perms, get_users_with_perms,
                                remove_perm, get_groups_with_perms)
from .models import Share, ShareUserObjectPermission
from django.contrib.auth.models import User, Group
from django.db.models import Q

from settings.config import SITE_URL

#Requires all permissions in the "perms" list.  These can be either assigned at the model level OR the object level
class ViewObjectPermissions(DjangoObjectPermissions):
    perms = []
    def has_permission(self, request, view):
        return True #Don't require this.  We want object permissions OR global permissions.
    def get_required_permissions(self, method, model_cls):
        return self.perms
    def has_object_permission(self, request, view, obj):
        if DjangoObjectPermissions.has_permission(self, request, view):
            return True
        if hasattr(view, 'get_queryset'):
            queryset = view.get_queryset()
        else:
            queryset = getattr(view, 'queryset', None)

        assert queryset is not None, (
            'Cannot apply DjangoObjectPermissions on a view that '
            'does not set `.queryset` or have a `.get_queryset()` method.'
        )

        model_cls = queryset.model
        user = request.user
        if not user.has_perms(self.perms, obj):
            return False

        return True

class ManageGroupPermission(ViewObjectPermissions):
    perms = ['auth.manage_group']

class SharePermissions(object):
    def __init__(self, share):
        self.share = share
        self.emailed = []
        self.failed = []
        self.created = []
    def create_user(self, username, shared_by=None):
        password = User.objects.make_random_password()
        u = User(username=username,email=username)
        u.set_password(password)
        u.save()
        if shared_by:
            u.profile.created_by = shared_by
            u.profile.save()
        try:
            email_users([u],'share/share_subject.txt','share/share_new_email_body.txt',{'user':u,'password':password,'share':self.share,'sharer':shared_by,'site_url':SITE_URL})
            self.created.append(username)
            self.emailed.append(username)
            return u
        except:
            self.failed.append(username)
            u.delete()
            return False
    def set_group_permissions(self, group, permissions, shared_by=None, email=True):
        if isinstance(group, str):
            group = Group.objects.get(Q(id__iexact=group)|Q(name__iexact=group.strip()))
        current_perms = get_perms(group, self.share)
        removed_perms = list(set(current_perms) - set(permissions))
        added_perms = list(set(permissions) - set(current_perms))
        for u in group.user_set.all():
            if len(self.get_user_permissions(u,user_specific=False)) == 0 and len(added_perms) > 0 and email:
                try:
                    email_users([u],'share/share_subject.txt','share/share_email_body.txt',{'user':u,'share':self.share,'sharer':shared_by,'site_url':SITE_URL})
                    self.emailed.append(u.username)
                except:
                    self.failed.append(u.username)
        for perm in removed_perms:
            remove_perm(perm,group,self.share)
        for perm in added_perms:
            assign_perm(perm,group,self.share)
    def set_user_permissions(self, user, permissions, shared_by=None, email=True):
        new_user = False
        if isinstance(user, str):
            username = user.lower()
            user = User.objects.filter(username__iexact=username).first()
        else:
            username = user.username
        if not user and len(permissions) > 0:
            user = self.create_user(username, shared_by=shared_by)
        if user:
            current_perms = self.get_user_permissions(user,user_specific=True)
            removed_perms = list(set(current_perms) - set(permissions))
            added_perms = list(set(permissions) - set(current_perms))
            if not new_user and len(current_perms) == 0 and email:
                try:
                    email_users([user],'share/share_subject.txt','share/share_email_body.txt',{'user':user,'share':self.share,'sharer':shared_by,'site_url':SITE_URL})
                    self.emailed.append(username)
                except:
                    self.failed.append(username)
            for perm in removed_perms:
                remove_perm(perm,user,self.share)
            for perm in added_perms:
                assign_perm(perm,user,self.share)
            return True
        else:
            return False
    def set_permissions(self, permissions, shared_by=None, email=True):
        emailed = []
        if 'groups' in permissions:
            for group, group_permissions in permissions['groups'].items():
                self.set_group_permissions(group, group_permissions, shared_by, email)
        if 'users' in permissions:
            for username, user_permissions in permissions['users'].items():
                self.set_user_permissions(username, user_permissions, shared_by, email)
    def get_permissions(self,user_specific=False):
        user_perms = self.get_all_user_permissions(user_specific=user_specific)
        groups = get_groups_with_perms(self.share,attach_perms=True)
        group_perms = [{'group':{'name':group.name,'id':group.id},'permissions':permissions} for group, permissions in groups.items()]
        return {'user_perms':user_perms,'group_perms':group_perms}
    def get_user_permissions(self,user,user_specific=False):
        if self.share.locked:
            return []
        if user_specific:
            from bioshareX.utils import fetchall
            perms = [uop.permission.codename for uop in ShareUserObjectPermission.objects.filter(user=user,content_object=self.share).select_related('permission')]
        else:
            if user.username == self.share.owner.username:
                perms = [perm[0] for perm in self.share._meta.permissions]
            else:
                perms = get_perms(user, self.share)
        if not self.share.secure and not user_specific:
            perms = list(set(perms+['view_share_files','download_share_files']))
        if self.share.read_only:
            if 'write_to_share' in perms:
                perms.remove('write_to_share')
            if 'delete_share_files' in perms:
                perms.remove('delete_share_files')
        return perms
    def get_all_user_permissions(self,user_specific=False):
        if not user_specific:
            users = get_users_with_perms(self.share, attach_perms=True, with_group_users=False)
            user_perms = [{'user':{'username':user.username, 'email':user.email, 'first_name':user.first_name, 'last_name':user.last_name},'permissions':permissions} for user, permissions in users.items()]
        else:
            perms = ShareUserObjectPermission.objects.filter(content_object=self.share).select_related('permission','user')
            user_perms={}
            for perm in perms:
                if perm.user.username not in user_perms:
                    user_perms[perm.user.username]={'user':{'username':perm.user.username},'permissions':[]}
                user_perms[perm.user.username]['permissions'].append(perm.permission.codename)
        return user_perms
