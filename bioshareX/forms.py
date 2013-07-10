from django import forms
from bioshareX.models import Share, SSHKey

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


