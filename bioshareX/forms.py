from django import forms
from bioshareX.models import Share, SSHKey
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.utils.html import strip_tags
from django.core.validators import RegexValidator
from bioshareX.utils import test_path, paths_contain
from django.conf import settings
import os   

class ShareForm(forms.ModelForm):
    name = forms.RegexField(regex=r'^[\w\d\s\'"\.!\?\-:,]+$',error_message=('Please avoid special characters'))
    notes = forms.RegexField(regex=r'^[\w\d\s\'"\.!\?\-@:,]+$',error_message=('Please avoid special characters'),widget=forms.Textarea(attrs={'rows':5,'cols':80}))
    tags = forms.RegexField(regex=r'^[\w\d\s,]+$',required=False,error_message=('Only use comma delimited alphanumeric tags'),widget=forms.Textarea(attrs={'rows':3,'cols':80,'placeholder':"seperate tags by commas, eg: important, chimpanzee"}))
    def __init__(self, user, *args, **kwargs):
        super(ShareForm, self).__init__(*args, **kwargs)
        self.fields['filesystem'].queryset = user.filesystems
        if not user.has_perm('bioshareX.link_to_path'):
            self.fields.pop('link_to_path')
        self.the_instance = kwargs.get('instance',None)
        if self.the_instance:
            if not self.the_instance.link_to_path:
                self.fields.pop('link_to_path')
            if self.the_instance.parent:
                self.fields.pop('filesystem')
                self.fields.pop('link_to_path')
                self.fields.pop('read_only')
    def clean_link_to_path(self):
        path = self.cleaned_data['link_to_path']
        if path == '' or not path:
            path = None
        if path:
            try:
                test_path(path,allow_absolute=True)
            except:
                raise forms.ValidationError('Bad path: "%s"'%path)
            if not os.path.isdir(path):
                raise forms.ValidationError('Path: "%s" does not exist'%path)
            if not paths_contain(settings.LINK_TO_DIRECTORIES,path):
                raise forms.ValidationError('Path not allowed.')
        if self.the_instance:
            if self.the_instance.link_to_path and not path:
                raise forms.ValidationError('It is not possible to change a linked share to a regular share.')
            if not self.the_instance.link_to_path and path:
                raise forms.ValidationError('It is not possible to change a regular share to a linked share.')
        return path
    
    def clean(self):
        cleaned_data = super(ShareForm, self).clean()
        if self.the_instance.parent:
            return cleaned_data
        path = cleaned_data.get('link_to_path',None)
        if path and not cleaned_data.get('read_only',None):
            self.add_error('read_only', forms.ValidationError('Linked shares must be read only.'))
        cleaned_data['read_only'] = True if path else self.cleaned_data['read_only']
        return cleaned_data         
    class Meta:
        model = Share
        fields = ('name', 'notes','filesystem','link_to_path','read_only')

class SubShareForm(forms.ModelForm):
    name = forms.RegexField(regex=r'^[\w\d\s\'"\.!\?\-:,]+$',error_message=('Please avoid special characters'))
    notes = forms.RegexField(regex=r'^[\w\d\s\'"\.!\?\-@:,\/]+$',error_message=('Please avoid special characters'),widget=forms.Textarea(attrs={'rows':5,'cols':80}))
    class Meta:
        model = Share
        fields = ('name', 'notes')
        
class MetaDataForm(forms.Form):
    notes = forms.RegexField(regex=r'^[\w\d\s\'"\.!\?\-@]+$',required=False,error_message=('Please avoid special characters'),widget=forms.Textarea(attrs={'rows':5,'cols':80}))
    tags = forms.RegexField(regex=r'^[\w\d\s,]+$',required=False,error_message=('Only use comma delimited alphanumeric tags'),widget=forms.Textarea(attrs={'rows':3,'cols':80,'placeholder':"seperate tags by commas, eg: important, chimpanzee"}))
#     def clean(self):
#         cleaned_data = super(MetaDataForm, self).clean()
# #         cleaned_data['tags'] = [tag.strip() for tag in cleaned_data['tags'].split(',')]
#         return cleaned_data

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
    name = forms.RegexField(regex=r'^[\w\d\ ]+$',error_message=('Only letters, numbers, and spaces are allowed'))

class RenameForm(forms.Form):
    from_name = forms.RegexField(regex=r'^[^/]+$',error_message=('Only letters, numbers, and spaces are allowed'),widget=forms.HiddenInput())
    to_name = forms.RegexField(regex=r'^[^/]+$',error_message=('Only letters, numbers, and spaces are allowed'))



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

from django.template.loader import render_to_string
def json_form_validate(form,save=False,html=True,template='ajax/crispy_form.html'):
    data={}
    if form.is_valid():
        data['status']='success'
        if save:
            try:
                data['objects']=[form.save()]
            except:
                pass
    else:
        data['status']='error'
        data['errors']=dict((key, value) for (key, value) in form.errors.items())
        data['html']= render_to_string(template,{'form':form})
    return data


from django.contrib import auth

class PasswordChangeForm(auth.forms.PasswordChangeForm):
    MIN_LENGTH = 8

    def clean_new_password1(self):
        password1 = self.cleaned_data.get('new_password1')

        # At least MIN_LENGTH long
        if len(password1) < self.MIN_LENGTH:
            raise forms.ValidationError("The new password must be at least %d characters long." % self.MIN_LENGTH)

        # At least one letter and one non-letter
#         first_isalpha = password1[0].isalpha()
#         if all(c.isalpha() == first_isalpha for c in password1):
#             raise forms.ValidationError("The new password must contain at least one letter and at least one digit or" \
#                                         " punctuation character.")

        # ... any other validation you want ...

        return password1

class SetPasswordForm(auth.forms.SetPasswordForm):
    MIN_LENGTH = 8

    def clean_new_password1(self):
        password1 = self.cleaned_data.get('new_password1')

        # At least MIN_LENGTH long
        if len(password1) < self.MIN_LENGTH:
            raise forms.ValidationError("The new password must be at least %d characters long." % self.MIN_LENGTH)

        # At least one letter and one non-letter
#         first_isalpha = password1[0].isalpha()
#         if all(c.isalpha() == first_isalpha for c in password1):
#             raise forms.ValidationError("The new password must contain at least one letter and at least one digit or" \
#                                         " punctuation character.")

        # ... any other validation you want ...

        return password1