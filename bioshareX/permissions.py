from django.http.response import Http404
from rest_framework.permissions import SAFE_METHODS, DjangoObjectPermissions


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
