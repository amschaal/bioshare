from django.conf.urls import patterns, include, url

urlpatterns = patterns('bioshareX.views',
    url(r'^/?$', 'index', name='home'),
    url(r'^create/?$', 'create_share', name='create_share'),
#     url(r'^list/(?P<share>\w{15})/$', 'list_directory', name='list_directory'),
#     url(r'^list/(?P<share>\w{15})/(?P<subdir>.*/)$', 'list_directory', name='list_sub_directory'),
    url(r'^list/(?P<share>\w{15})/(?:(?P<subdir>.*/))?$', 'list_directory', name='list_directory'),
)

urlpatterns += patterns('bioshareX.file_views',
#     url(r'^upload/(?P<share>\w{15})(?:/?P<subdir>.*/)$', 'upload_file', name='upload_file'),
#     url(r'^upload/?$', 'upload_file', name='upload_file'),
    url(r'^upload/(?P<share>\w{15})/(?:(?P<subdir>.*/))?$', 'upload_file', name='upload_file'),
    url(r'^create_folder/(?P<share>\w{15})/(?:(?P<subdir>.*/))?$', 'create_folder', name='create_folder'),
    url(r'^delete/(?P<share>\w{15})/(?:(?P<subdir>.*/))?$', 'delete_paths', name='delete_paths'),
)
