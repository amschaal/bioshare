from django import forms
from bioshareX.models import Share, SSHKey
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

class ShareForm(forms.ModelForm):
    class Meta:
        model = Share
        fields = ('name', 'notes')
        
# class SSHKeyForm(forms.ModelForm):
#     class Meta:
#         model = SSHKey
#         fields = ('name', 'key')
        
class SSHKeyForm(forms.Form):
    name = forms.CharField(max_length=50)
    rsa_key  = forms.FileField()
    def clean_rsa_key(self):
        import subprocess
        file = self.cleaned_data['rsa_key']
        if not file:
            raise forms.ValidationError("SSH RSA key required")
        return_code = subprocess.call(['ssh-keygen','-l','-f',file.temporary_file_path()])
        if return_code == 1:
            raise forms.ValidationError("Not a valid SSH RSA key!")
        contents = file.read()
        if contents[:7] != 'ssh-rsa':
            raise forms.ValidationError("Only ssh-rsa keys are accepted")
        if len(SSHKey.objects.filter(key__contains=SSHKey.extract_key(contents))) != 0:
            raise forms.ValidationError("This key is already in use.")
#             if "fred@example.com" not in data:
#                 raise forms.ValidationError("You have forgotten about Fred!")
        
        # Always return the cleaned data, whether you have changed it or
        # not.
        return contents
        
class UploadFileForm(forms.Form):
    title = forms.CharField(max_length=100)
    file  = forms.FileField()
    
class FolderForm(forms.Form):
    name = forms.CharField(max_length=100)

class ChangePasswordForm(forms.Form):
    password1 = forms.CharField(widget=forms.PasswordInput,
                                label=_("Password"))
    password2 = forms.CharField(widget=forms.PasswordInput,
                                label=_("Password (again)"))
    def clean(self):
        """
        Verifiy that the values entered into the two password fields
        match. Note that an error here will end up in
        ``non_field_errors()`` because it doesn't apply to a single
        field.
        
        """
        if 'password1' in self.cleaned_data and 'password2' in self.cleaned_data:
            if self.cleaned_data['password1'] != self.cleaned_data['password2']:
                raise forms.ValidationError(_("The two password fields didn't match."))
        return self.cleaned_data

class RegistrationForm(forms.Form):
    """
    Form for registering a new user account.
    
    Validates that the requested username is not already in use, and
    requires the password to be entered twice to catch typos.
    
    Subclasses should feel free to add any additional validation they
    need, but should avoid defining a ``save()`` method -- the actual
    saving of collected user data is delegated to the active
    registration backend.

    """
    required_css_class = 'required'
#     username = forms.RegexField(regex=r'^[\w.@+-]+$',
#                                 max_length=30,
#                                 label=_("Username"),
#                                 error_messages={'invalid': _("This value may contain only letters, numbers and @/./+/-/_ characters.")})
    email = forms.EmailField(label=_("E-mail"))
    password1 = forms.CharField(widget=forms.PasswordInput,
                                label=_("Password"))
    password2 = forms.CharField(widget=forms.PasswordInput,
                                label=_("Password (again)"))
    
#     def clean_username(self):
#         """
#         Validate that the username is alphanumeric and is not already
#         in use.
#         
#         """
#         existing = User.objects.filter(username__iexact=self.cleaned_data['username'])
#         if existing.exists():
#             raise forms.ValidationError(_("A user with that username already exists."))
#         else:
#             return self.cleaned_data['username']

    def clean(self):
        """
        Verifiy that the values entered into the two password fields
        match. Note that an error here will end up in
        ``non_field_errors()`` because it doesn't apply to a single
        field.
        
        """
        if 'email' in self.cleaned_data:
            self.cleaned_data['username']=self.cleaned_data['email']
        if 'password1' in self.cleaned_data and 'password2' in self.cleaned_data:
            if self.cleaned_data['password1'] != self.cleaned_data['password2']:
                raise forms.ValidationError(_("The two password fields didn't match."))
        return self.cleaned_data
    def clean_email(self):
        """
        Validate that the supplied email address is unique for the
        site.
        
        """
        if User.objects.filter(email__iexact=self.cleaned_data['email']):
            raise forms.ValidationError(_("This email address is already in use. Please supply a different email address."))
        return self.cleaned_data['email']
