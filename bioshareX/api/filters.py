import datetime

from django.contrib.auth.models import Group, User
from django.db.models.query_utils import Q
from rest_framework import filters
from bioshareX.api.filter_utils import gen_sql_filter_json_array

from bioshareX.models import Share


class UserShareFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        user = view.request.query_params.get('user',None)
        if not user:
            return queryset
        shares = Share.objects.filter(user_permissions__user__username__icontains=user)#.distinct('id').values_list('id',flat=True)
        return queryset.filter(id__in=shares)

class GroupShareFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        group = view.request.query_params.get('group',None)
        if not group:
            return queryset
        shares = Share.objects.filter(group_permissions__group__name__icontains=group)#.distinct('id').values_list('id',flat=True)
        return queryset.filter(id__in=shares)

class ShareTagFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        tags = view.request.query_params.get('tags',None)
        tags_operator = view.request.query_params.get('tags_operator','OR')
        if not tags:
            return queryset
        tags = [tag.strip() for tag in tags.split(',')]
        if tags_operator == 'AND':
            for tag in tags:
                return queryset.filter(tags__name=tag)
        else: #OR
            return queryset.filter(tags__name__in=tags)

class ActiveMessageFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        active = view.request.query_params.get('active',None)
        if not active:
            return queryset
        return queryset.filter(Q(expires__gte=datetime.datetime.today())|Q(expires=None)).exclude(viewed_by__id=request.user.id)

class ContainsSymlinkFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        contains_symlink = view.request.query_params.get('contains_symlinks','false')
        if contains_symlink.lower() not in ['true', True]:
            return queryset
        return queryset.filter(Q(symlinks_found__isnull=False)|Q(link_to_path__isnull=False))

class SymlinkTargetFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        symlink_target = view.request.query_params.get('symlink_target')
        if not symlink_target:
            return queryset
        query = gen_sql_filter_json_array(Share, "meta->'symlinks'", 'target', 'ILIKE', symlink_target)
        return queryset.filter(id__in=query)

class SymlinkWarningFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        if view.request.query_params.get('has_symlink_warning', 'false').lower() != 'true':
            return queryset
        query = gen_sql_filter_json_array(Share, "meta->'symlinks'", 'warning', 'not null')
        return queryset.filter(id__in=query)