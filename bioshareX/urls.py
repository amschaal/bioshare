from django.conf.urls import  url, include
from bioshareX import views as bioshare_views, jsutils
from bioshareX import api as api_views
from bioshareX import file_views
from rest_framework import routers
from bioshareX.api import GroupViewSet, MessageViewSet
router = routers.DefaultRouter()
router.register(r'groups', GroupViewSet,'Group')
router.register(r'messages', MessageViewSet,'Message')


urlpatterns = [
    url(r'^$', bioshare_views.index, name='index'),
    url(r'^forbidden/?$', bioshare_views.forbidden, name='forbidden'),
    url(r'^create/?$', bioshare_views.create_share, name='create_share'),
    url(r'^create_subshare/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', bioshare_views.create_subshare, name='create_subshare'),
    url(r'^edit/(?P<share>\w{15})/?$', bioshare_views.edit_share, name='edit_share'),
    url(r'^cloud/?$', bioshare_views.tag_cloud, name='tag_cloud'),
#     url(r'^list/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', bioshare_views.list_directory, name='list_directory_old'),
#     url(r'^view/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', bioshare_views.list_directory, name='list_directory'),
#     url(r'^wget/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?wget_index.html$', bioshare_views.wget_listing, name='wget_listing'),
    url(r'^list/(?P<share>\w+)/(?:(?P<subdir>.*/))?$', bioshare_views.list_directory, name='list_directory_old'),
    url(r'^view/(?P<share>\w+)/(?:(?P<subdir>.*/))?$', bioshare_views.list_directory, name='list_directory'),
    url(r'^wget/(?P<share>\w+)/(?:(?P<subdir>.*/))?wget_index.html$', bioshare_views.wget_listing, name='wget_listing'),
    url(r'^shares/$', bioshare_views.list_shares, name='list_shares'),
    url(r'^search/$', bioshare_views.search_shares, name='search_shares'),
    url(r'^permissions/(?P<share>[\da-zA-Z]{15})/?$', bioshare_views.share_permissions, name='share_permissions'),
#     url(r'^goto/(?P<share>[\da-zA-Z]{15})/(?:(?P<subpath>.*/?))?$', bioshare_views.go_to_file_or_folder, name='go_to_file_or_folder'),
    url(r'^goto/(?P<share>\w+)/(?:(?P<subpath>.*/?))?$', bioshare_views.go_to_file_or_folder, name='go_to_file_or_folder'),
    url(r'^ssh_keys/list/?$', bioshare_views.list_ssh_keys, name='list_ssh_keys'),
    url(r'^ssh_keys/create/?$', bioshare_views.create_ssh_key, name='create_ssh_key'),
    url(r'^groups/manage/?$', bioshare_views.manage_groups, name='manage_groups'),
#     url(r'^account/update_password/?$', 'update_password', name='update_password'),
    url(r'^delete_share/(?P<share>[\da-zA-Z]{15})/?$', bioshare_views.delete_share, kwargs={'confirm':False},name='delete_share'),
    url(r'^confirm_delete_share/(?P<share>[\da-zA-Z]{15})/?$', bioshare_views.delete_share, kwargs={'confirm':True},name='confirm_delete_share'),
    url(r'^search/files/?$', bioshare_views.search_files, name='search_files'),
    url(r'^jsurls.js$', jsutils.jsurls, {}, 'jsurls'),
]

# urlpatterns += [
#     url(r'^account/update_password/$', auth_views.password_change,  {'password_change_form': PasswordChangeForm,'post_change_redirect':'auth_password_change_done'},name='update_password'),
# ]

urlpatterns += [
    url(r'^api/get_permissions/(?P<share>[\da-zA-Z]{15})/?$', api_views.get_permissions, name='api_get_permissions'),
    url(r'^api/set_permissions/(?P<share>[\da-zA-Z]{15})/?$', api_views.set_permissions, name='api_set_permissions'),
    url(r'^api/update/(?P<share>[\da-zA-Z]{15})/?$', api_views.update_share, name='api_update_share'),
    url(r'^api/get_group/?$', api_views.get_group, name='api_get_group'),
    url(r'^api/search/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', api_views.search_share, name='api_search_share'),
    url(r'^api/share_autocomplete/$', api_views.share_autocomplete, name='api_share_autocomplete'),
    url(r'^api/ssh_keys/delete/?$', api_views.delete_ssh_key, name='api_delete_ssh_key'),
    url(r'^api/edit_metadata/(?P<share>[\da-zA-Z]{15})/(?P<subpath>.*)/?$', api_views.edit_metadata, name='api_edit_metadata'),
    url(r'^api/get_addresses/?$', api_views.get_address_book, name='api_get_address_book'),
    url(r'^api/get_user/?$', api_views.get_user, name='api_get_user'),
    url(r'^api/get_tags/?$', api_views.get_tags, name='api_tags'),
    url(r'^api/share/(?P<share>[\da-zA-Z]{15})/?$', api_views.share_with, name='api_share_with'),
    url(r'^api/shares/create/?$', api_views.create_share, name='api_create_share'),
    url(r'^api/email_participants/(?P<share>[\da-zA-Z]{15})/(?P<subdir>.*)/?$', api_views.email_participants, name='api_email_participants'),
    url(r'^api/logs/$', api_views.ShareLogList.as_view()),
    url(r'^api/shares/$', api_views.ShareList.as_view()),
    url(r'^api/', include(router.urls)),
]

urlpatterns += [
    url(r'^upload/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.upload_file, name='upload_file'),
    url(r'^create_folder/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.create_folder, name='create_folder'),
    url(r'^rename/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.modify_name, name='modify_name'),
    url(r'^delete/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.delete_paths, name='delete_paths'),
    url(r'^move/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.move_paths, name='move_paths'),
    url(r'^stream_archive/(?P<share>[\da-zA-Z]{15})/(?:(?P<subdir>.*/))?$', file_views.download_archive_stream, name='download_archive_stream'),
    url(r'^download/(?P<share>[\da-zA-Z]{15})/(?P<subpath>.*)/?$', file_views.download_file, name='download_file'),
    url(r'^preview/(?P<share>[\da-zA-Z]{15})/(?P<subpath>.*)/?$', file_views.preview_file, name='preview_file'),
    url(r'^directories/(?P<share>[\da-zA-Z]{15})/?$', file_views.get_directories, name='get_directories'),
    url(r'^wget/(?P<share>[\da-zA-Z]{15})/(?P<subpath>.*)/?$', file_views.download_file, name='wget_download_file'),
]
