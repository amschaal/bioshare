from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()
# from registration.forms import RegistrationFormUniqueEmail
from bioshareX.forms import RegistrationForm
from registration.backends.default.views import RegistrationView
from django.contrib.auth.views import logout_then_login

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'bioshare.views.home', name='home'),
    # url(r'^bioshare/', include('bioshareX.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
    url(r'^bioshare/', include('bioshareX.urls')),
    url(r'^accounts/register/$', RegistrationView.as_view(form_class=RegistrationForm),name='registration_register'),
    url(r'^accounts/logout/$', logout_then_login,name='auth_logout'),                   
    url(r'^accounts/', include('registration.backends.default.urls')),
)
# urlpatterns += patterns('',
#     url(r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'registration/login.html'}),
#     url('^accounts/reset', 'django.contrib.auth.views.password_reset'),
# )

# urlpatterns += patterns('',
#     url(r'^accounts/login/$', 'django.contrib.auth.views.login', name='login'),#,{'next_page':'home'}
#     url(r'^accounts/logout/$', 'django.contrib.auth.views.logout_then_login', name='logout'),
#     url(r'^accounts/password_change/$', 'django.contrib.auth.views.password_change', name='password_change'),
#     url(r'^accounts/password_change/done/$', 'django.contrib.auth.views.password_change_done', name='password_change_done'),
#     url(r'^accounts/password_reset/$', 'django.contrib.auth.views.password_reset', name='auth_password_reset'),
#     url(r'^accounts/password_reset/done/$', 'django.contrib.auth.views.password_reset_done', name='password_reset_done'),
#     url(r'^accounts/reset/(?P<uidb36>[0-9A-Za-z]{1,13})-(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
#         'django.contrib.auth.views.password_reset_confirm',
#         name='password_reset_confirm'),
#     url(r'^accounts/reset/done/$', 'django.contrib.auth.views.password_reset_complete', name='password_reset_complete'),
# )


# urlpatterns += patterns('',
#     url(r'^', include('bioshareX.urls')),
# )
