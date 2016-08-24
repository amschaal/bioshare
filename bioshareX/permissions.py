from django.http.response import Http404
from rest_framework.permissions import DjangoModelPermissions, SAFE_METHODS
from django.contrib.auth.models import Group


class ViewObjectPermissions(DjangoModelPermissions):
    def has_object_permission(self, request, view, obj):
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
#         raise Exception(','.join(self.perms))
        if not user.has_perms(self.perms, obj):
            # If the user does not have permissions we need to determine if
            # they have read permissions to see 403, or not, and simply see
            # a 404 response.

            if request.method in SAFE_METHODS:
                # Read permissions already checked and failed, no need
                # to make another lookup.
                raise Http404

            read_perms = self.get_required_object_permissions('GET', model_cls,view)
            if not user.has_perms(read_perms, obj):
                raise Http404

            # Has read permissions.
            return False

        return True

class ManageGroupPermission(ViewObjectPermissions):
    perms = ['manage_group']
#     def has_object_permission(self, request, view, obj):
#         if not request.user.groups.filter(id=obj.id).exists():
#             return False
#         return super(ManageGroupPermission, self).has_object_permission(request,view,obj)