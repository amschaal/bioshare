from django.contrib import admin
from unishare.models import Share

class ShareAdmin(admin.ModelAdmin):
    fields = ('name', 'notes')
    def save_model(self, request, obj, form, change):
        obj.owner = request.user
        obj.save()
admin.site.register(Share, ShareAdmin)