from django.conf.urls import patterns, include, url

urlpatterns = patterns('bioshareX.views',
    url(r'^/?$', 'index', name='home'),
    url(r'^forbidden/?$', 'forbidden', name='forbidden'),
    url(r'^create/?$', 'create_share', name='create_share'),
#     url(r'^list/(?P<share>\w{15})/$', 'list_directory', name='list_directory'),
#     url(r'^list/(?P<share>\w{15})/(?P<subdir>.*/)$', 'list_directory', name='list_sub_directory'),
    url(r'^list/(?P<share>\w{15})/(?:(?P<subdir>.*/))?$', 'list_directory', name='list_directory'),
    url(r'^permissions/(?P<share>\w{15})/?$', 'share_permissions', name='share_permissions'),
    url(r'^goto/(?P<share>\w{15})/(?:(?P<subpath>.*/?))?$', 'go_to_file_or_folder', name='go_to_file_or_folder'),
    
)
urlpatterns += patterns('bioshareX.api',
    url(r'^api/get_permissions/(?P<share>\w{15})/?$', 'get_permissions', name='api_get_permissions'),
    url(r'^api/get_user_permissions/(?P<share>\w{15})/?$', 'get_user_permissions', name='api_get_user_permissions'),
    url(r'^api/set_permissions/(?P<share>\w{15})/?$', 'set_permissions', name='api_set_permissions'),
    url(r'^api/update/(?P<share>\w{15})/?$', 'update_share', name='api_update_share'),
    url(r'^api/get_user/?$', 'get_user', name='api_get_user'),
    url(r'^api/get_group/?$', 'get_group', name='api_get_group'),
    url(r'^api/search/(?P<share>\w{15})/(?:(?P<subdir>.*/))?$', 'search_share', name='api_search_share'),
)

urlpatterns += patterns('bioshareX.file_views',
#     url(r'^upload/(?P<share>\w{15})(?:/?P<subdir>.*/)$', 'upload_file', name='upload_file'),
#     url(r'^upload/?$', 'upload_file', name='upload_file'),
    url(r'^upload/(?P<share>\w{15})/(?:(?P<subdir>.*/))?$', 'upload_file', name='upload_file'),
    url(r'^create_folder/(?P<share>\w{15})/(?:(?P<subdir>.*/))?$', 'create_folder', name='create_folder'),
    url(r'^delete/(?P<share>\w{15})/(?:(?P<subdir>.*/))?$', 'delete_paths', name='delete_paths'),
    url(r'^archive/(?P<share>\w{15})/(?:(?P<subdir>.*/))?$', 'archive_files', name='archive_files'),
    url(r'^download/(?P<share>\w{15})/(?P<subpath>.*)/?$', 'download_file', name='download_file'),
)
