from django.contrib import admin
from bioshareX.models import Share
from guardian.admin import GuardedModelAdmin
class ShareAdmin(GuardedModelAdmin):
    pass
#     excl = ('name', 'notes')
#     def save_model(self, request, obj, form, change):
#         obj.owner = request.user
#         obj.save()
admin.site.register(Share, ShareAdmin)
