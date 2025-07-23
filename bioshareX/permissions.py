from django.http.response import Http404
from .utils import email_users
from rest_framework.permissions import SAFE_METHODS, DjangoObjectPermissions
from guardian.shortcuts import (assign_perm, get_perms, get_users_with_perms,
                                remove_perm)
from .models import Share
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
        try:
            email_users([u],'share/share_subject.txt','share/share_new_email_body.txt',{'user':u,'password':password,'share':self.share,'sharer':shared_by,'site_url':SITE_URL})
            self.created.append(username)
            return u
        except:
            self.failed.append(username)
            u.delete()
            return False
    def set_group_permissions(self, group, permissions, shared_by=None):
        if isinstance(group, str):
            group = Group.objects.get(Q(id__iexact=group)|Q(name__iexact=group.strip()))
        current_perms = get_perms(group, self.share)
        removed_perms = list(set(current_perms) - set(permissions))
        added_perms = list(set(permissions) - set(current_perms))
        for u in group.user_set.all():
            if len(self.share.get_user_permissions(u,user_specific=True)) == 0 and len(added_perms) > 0 and permissions['email']:
                try:
                    email_users([u],'share/share_subject.txt','share/share_email_body.txt',{'user':u,'share':self.share,'sharer':shared_by,'site_url':SITE_URL})
                    self.emailed.append(u.username)
                except:
                    self.failed.append(u.username)
        for perm in removed_perms:
            remove_perm(perm,group,self.share)
        for perm in added_perms:
            assign_perm(perm,group,self.share)
    def set_user_permissions(self, user, permissions, shared_by=None):
        if isinstance(user, str):
            username = user.lower()
            user = User.objects.filter(username__iexact=username).first()
        else:
            username = user.username
        if not user and len(permissions) > 0:
            user = self.create_user(username)
        if user:
            current_perms = self.share.get_user_permissions(user,user_specific=True)
            removed_perms = list(set(current_perms) - set(permissions))
            added_perms = list(set(permissions) - set(current_perms))
            for perm in removed_perms:
                remove_perm(perm,user,self.share)
            for perm in added_perms:
                assign_perm(perm,user,self.share)
            return True
        else:
            return False
    def set_permissions(self, permissions, shared_by=None):
        emailed = []
        if 'groups' in permissions:
            for group, permissions in permissions['groups'].items():
                self.set_group_permissions(group, permissions, shared_by)
        if 'users' in permissions:
            for username, permissions in permissions['users'].items():
                self.set_user_permissions(username, permissions, shared_by)
