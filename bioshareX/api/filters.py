from rest_framework import filters
from django.contrib.auth.models import User, Group
from guardian.shortcuts import get_objects_for_user, get_objects_for_group
from bioshareX.models import Share

class UserShareFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        user = view.request.query_params.get('user',None)
        if not user:
            return queryset
        shares = Share.objects.filter(user_permissions__user__username__icontains=user)
        return queryset.filter(id__in=shares)

class GroupShareFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        group = view.request.query_params.get('group',None)
        if not group:
            return queryset
        shares = Share.objects.filter(group_permissions__group__name__icontains=group)
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
        