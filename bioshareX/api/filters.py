from rest_framework import filters
from django.contrib.auth.models import User, Group
from guardian.shortcuts import get_objects_for_user, get_objects_for_group

class UserShareFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        user = view.request.query_params.get('user',None)
        if not user:
            return queryset
        users = User.objects.filter(username__icontains=user)
        
        share_ids = []
        for u in users:
            u_share_ids = [s.id for s in get_objects_for_user(u, 'bioshareX.view_share_files')]
            #OR
            share_ids += u_share_ids
        return queryset.filter(id__in=share_ids)

class GroupShareFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        group = view.request.query_params.get('group',None)
        if not group:
            return queryset
        groups = Group.objects.filter(name__icontains=group)
        
        share_ids = []
        for g in groups:
            g_share_ids = [s.id for s in get_objects_for_group(g, 'bioshareX.view_share_files')]
            #OR
            share_ids += g_share_ids
        return queryset.filter(id__in=share_ids)

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
        