from django.conf import settings
from django.conf.urls import include, url
# Uncomment the next two lines to enable the admin:
from django.contrib import admin
from django.urls.conf import path

from bioshareX.forms import (BioshareAuthenticationForm,
                             BiosharePasswordResetForm)

admin.autodiscover()
# ***HACKY***  Monkey patching the authentication form so that the username field says email instead.
from django.contrib.auth.forms import AuthenticationForm
# from registration.forms import RegistrationFormUniqueEmail
# from bioshareX.forms import RegistrationForm, SetPasswordForm
# from registration.backends.default.views import RegistrationView
from django.contrib.auth.views import (  # , login, password_reset_confirm, password_reset
    LoginView, PasswordResetView, logout_then_login)

from bioshareX import views as bioshare_views

from django_ratelimit.decorators import ratelimit, UNSAFE

AuthenticationForm.base_fields['username'].label = 'Email' 


urlpatterns = [
    # Examples:
    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^bioshare/', include('bioshareX.urls')),
    url(r'^accounts/logout/$', logout_then_login, name='logout'),
    # path('accounts/login/', LoginView.as_view(authentication_form=BioshareAuthenticationForm), name='login',kwargs={'authentication_form':BioshareAuthenticationForm}),
    path('accounts/password_reset/', ratelimit(key='user_or_ip', rate='5/h', method=UNSAFE)(PasswordResetView.as_view(form_class=BiosharePasswordResetForm)), name='password_reset', kwargs={'password_reset_form':BiosharePasswordResetForm,'extra_email_context':{'SITE_URL':settings.SITE_URL}}),
#     url(r'^accounts/password_reset/$', password_reset, name='password_reset', kwargs={'password_reset_form':BiosharePasswordResetForm,'extra_email_context':{'SITE_URL':settings.SITE_URL}}),
    path('accounts/login/', ratelimit(key='post:username', rate='10/h', method=UNSAFE)(ratelimit(key='user_or_ip', rate='10/h', method=UNSAFE)(LoginView.as_view(authentication_form=BioshareAuthenticationForm))), name='login',kwargs={'authentication_form':BioshareAuthenticationForm}),
    url(r'^accounts/', include('django.contrib.auth.urls')),
    url(r'^$', bioshare_views.list_shares, name='home'),
    url(r'^Data/(?P<id>[\da-zA-Z]{10})/(?:(?P<subpath>.*/?))?$', bioshare_views.redirect_old_path, name='redirect_old_path'),
]
