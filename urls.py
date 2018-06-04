from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
from django.conf import settings
from bioshareX.forms import BiosharePasswordResetForm,\
    BioshareAuthenticationForm
admin.autodiscover()
# from registration.forms import RegistrationFormUniqueEmail
# from bioshareX.forms import RegistrationForm, SetPasswordForm
# from registration.backends.default.views import RegistrationView
from django.contrib.auth.views import logout_then_login, password_reset,login#, login, password_reset_confirm, password_reset
from bioshareX import views as bioshare_views

# ***HACKY***  Monkey patching the authentication form so that the username field says email instead.
from django.contrib.auth.forms import AuthenticationForm
AuthenticationForm.base_fields['username'].label = 'Email' 


urlpatterns = [
    # Examples:
    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^bioshare/', include('bioshareX.urls')),
    url(r'^accounts/logout/$', logout_then_login, name='logout'),
    url(r'^accounts/login/$', login, name='login',kwargs={'authentication_form':BioshareAuthenticationForm}),
    url(r'^accounts/password_reset/$', password_reset, name='password_reset', kwargs={'password_reset_form':BiosharePasswordResetForm,'extra_email_context':{'SITE_URL':settings.SITE_URL}}),
    url(r'^accounts/', include('django.contrib.auth.urls')),
    url(r'^$', bioshare_views.list_shares, name='home'),
    url(r'^Data/(?P<id>[\da-zA-Z]{10})/(?:(?P<subpath>.*/?))?$', bioshare_views.redirect_old_path, name='redirect_old_path'),
]
