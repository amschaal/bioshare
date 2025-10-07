from django.conf.urls import include
from django.urls import re_path
from rest_framework import routers

from bioshareX import file_views
from bioshareX import views as bioshare_views  # , jsutils
from bioshareX.api import views as api_views

# from bioshareX.api.views import GroupViewSet, MessageViewSet
router = routers.DefaultRouter()
router.register(r'groups', api_views.GroupViewSet,'Group')
router.register(r'messages', api_views.MessageViewSet,'Message')
router.register(r'shares', api_views.ShareViewset,'Share')


urlpatterns = [
    re_path(r'^$', bioshare_views.index, name='index'),
    re_path(r'^messages/?$', bioshare_views.view_messages, name='view_messages'),
    re_path(r'^forbidden/?$', bioshare_views.forbidden, name='forbidden'),
    re_path(r'^create/?$', bioshare_views.create_share, name='create_share'),
    re_path(r'^create_subshare/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', bioshare_views.create_subshare, name='create_subshare'),
    re_path(r'^edit/(?P<share>\w{15})/?$', bioshare_views.edit_share, name='edit_share'),
    re_path(r'^cloud/?$', bioshare_views.tag_cloud, name='tag_cloud'),
#     re_path(r'^list/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', bioshare_views.list_directory, name='list_directory_old'),
#     re_path(r'^view/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', bioshare_views.list_directory, name='list_directory'),
#     re_path(r'^wget/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?wget_index.html$', bioshare_views.wget_listing, name='wget_listing'),
    re_path(r'^list/(?P<share>[-\w]+)/(?:(?P<subdir>.*/))?$', bioshare_views.list_directory, name='list_directory_old'),
    re_path(r'^view/(?P<share>[-\w]+)/(?:(?P<subdir>.*/))?$', bioshare_views.list_directory, name='list_directory'),
    re_path(r'^update_stats/(?P<share>[-\w]+)/?$', bioshare_views.update_stats, name='update_stats'),
    re_path(r'^wget/(?P<share>[-\w]+)/(?:(?P<subdir>.*/))?wget_index.html$', bioshare_views.wget_listing, name='wget_listing'),
    re_path(r'^shares/$', bioshare_views.list_shares, name='list_shares'),
#     re_path(r'^groups/(?P<group_id>[\d]+)/shares/?$', bioshare_views.list_shares, name='list_group_shares'),
    re_path(r'^groups/(?P<group_id>[\d]+)/shares/create/?$', bioshare_views.create_share, name='create_group_share'),
    re_path(r'^permissions/(?P<share>[\da-zA-Z]{15})/?$', bioshare_views.share_permissions, name='share_permissions'),
#     re_path(r'^goto/(?P<share>[\da-zA-Z]{15})/(?:(?P<subpath>.*/?))?$', bioshare_views.go_to_file_or_folder, name='go_to_file_or_folder'),
    re_path(r'^goto/(?P<share>[-\w]+)/(?:(?P<subpath>.*/?))?$', bioshare_views.go_to_file_or_folder, name='go_to_file_or_folder'),
    re_path(r'^ssh_keys/list/?$', bioshare_views.list_ssh_keys, name='list_ssh_keys'),
    re_path(r'^ssh_keys/create/?$', bioshare_views.create_ssh_key, name='create_ssh_key'),
    re_path(r'^groups/?$', bioshare_views.manage_groups, name='groups'),
    re_path(r'^groups/(?P<group_id>[\d]+)/?$', bioshare_views.list_shares, name='group'),
    re_path(r'^groups/(?P<group_id>[\d]+)/manage/?$', bioshare_views.manage_group, name='manage_group'),
    re_path(r'^groups/(?P<group_id>[\d]+)/modify/?$', bioshare_views.create_modify_group, name='modify_group'),
    re_path(r'^groups/create/?$', bioshare_views.create_modify_group, name='create_group'),
#     re_path(r'^account/update_password/?$', 'update_password', name='update_password'),
    re_path(r'^delete_share/(?P<share>[\da-zA-Z]{15})/?$', bioshare_views.delete_share, kwargs={'confirm':False},name='delete_share'),
    re_path(r'^confirm_delete_share/(?P<share>[\da-zA-Z]{15})/?$', bioshare_views.delete_share, kwargs={'confirm':True},name='confirm_delete_share'),
    # re_path(r'^search/files/?$', bioshare_views.search_files, name='search_files'),
    re_path(r'^locked/(?P<share>[-\w]+)/$', bioshare_views.locked, name='locked'),
    re_path(r'^unlock/(?P<share>[-\w]+)/$', bioshare_views.unlock, name='unlock'),
    re_path(r'^view_links/(?P<share>[-\w]+)/$', bioshare_views.view_links, name='view_links')
    # re_path(r'^jsurls.js$', jsutils.jsurls, {}, 'jsurls'), # @todo: replace this
]

# urlpatterns += [
#     re_path(r'^account/update_password/$', auth_views.password_change,  {'password_change_form': PasswordChangeForm,'post_change_redirect':'auth_password_change_done'},name='update_password'),
# ]

urlpatterns += [
    re_path(r'^api/get_permissions/(?P<share>[\da-zA-Z]{15})/?$', api_views.get_permissions, name='api_get_permissions'),
    re_path(r'^api/set_permissions/(?P<share>[\da-zA-Z]{15})/?$', api_views.set_permissions, name='api_set_permissions'),
    re_path(r'^api/update/(?P<share>[\da-zA-Z]{15})/?$', api_views.update_share, name='api_update_share'),
    re_path(r'^api/get_group/?$', api_views.get_group, name='api_get_group'),
    re_path(r'^api/search/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', api_views.search_share, name='api_search_share'),
    re_path(r'^api/share_autocomplete/$', api_views.share_autocomplete, name='api_share_autocomplete'),
    re_path(r'^api/ssh_keys/delete/?$', api_views.delete_ssh_key, name='api_delete_ssh_key'),
    re_path(r'^api/edit_metadata/(?P<share>[\da-zA-Z]{15})/(?P<subpath>.*)/?$', api_views.edit_metadata, name='api_edit_metadata'),
    re_path(r'^api/get_addresses/?$', api_views.get_address_book, name='api_get_address_book'),
    re_path(r'^api/get_user/?$', api_views.get_user, name='api_get_user'),
    re_path(r'^api/get_tags/?$', api_views.get_tags, name='api_tags'),
    re_path(r'^api/share/(?P<share>[\da-zA-Z]{15})/?$', api_views.share_with, name='api_share_with'),
    re_path(r'^api/shares/create/?$', api_views.create_share, name='api_create_share'),
    re_path(r'^api/email_participants/(?P<share>[\da-zA-Z]{15})/(?P<subdir>.*)/?$', api_views.email_participants, name='api_email_participants'),
    re_path(r'^api/share_read_only/(?P<share>[\da-zA-Z]{15})/$', api_views.share_read_only, name='api_share_read_only'),
    re_path(r'^api/logs/$', api_views.ShareLogList.as_view()),
#     re_path(r'^api/shares/$', api_views.ShareList.as_view()),
    re_path(r'^api/', include(router.urls)),
]

urlpatterns += [
    re_path(r'^upload/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.upload_file, name='upload_file'),
    re_path(r'^create_folder/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.create_folder, name='create_folder'),
    re_path(r'^create_symlink/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.create_symlink, name='create_symlink'),
    re_path(r'^unlink/(?P<share>[\da-zA-Z]{15})/(?P<subpath>.*)/?$', file_views.unlink, name='unlink'),
    re_path(r'^rename/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.modify_name, name='modify_name'),
    re_path(r'^delete/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.delete_paths, name='delete_paths'),
    re_path(r'^move/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.move_paths, name='move_paths'),
    re_path(r'^stream_archive/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.download_archive_stream, name='download_archive_stream'),
    re_path(r'^download/(?P<share>[\da-zA-Z]{15})/(?P<subpath>.*)/?$', file_views.download_file, name='download_file'),
    re_path(r'^preview/(?P<share>[\da-zA-Z]{15})/(?P<subpath>.*)/?$', file_views.preview_file, name='preview_file'),
    re_path(r'^directories/(?P<share>[\da-zA-Z]{15})/?$', file_views.get_directories, name='get_directories'),
    re_path(r'^wget/(?P<share>[\da-zA-Z]{15})/(?P<subpath>.*)/?$', file_views.download_file, name='wget_download_file'),
    re_path(r'^md5sum/(?P<share>[\da-zA-Z]{15})/(?P<subpath>.*)/?$', file_views.get_md5sum, name='md5sum'),
]
