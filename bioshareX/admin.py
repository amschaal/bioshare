from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as OriginalUserAdmin
from django.contrib.auth.models import User
from guardian.admin import GuardedModelAdmin

from bioshareX.models import FilePath, Filesystem, Message, Share, UserProfile


class ShareAdmin(GuardedModelAdmin):
    exclude = ('real_path','path_exists','id','tags')
    search_fields = ('id', 'slug', 'owner__username', 'name','notes','tags__name')
#     def save_model(self, request, obj, form, change):
#         obj.owner = request.user
#         obj.save()
class FilesystemAdmin(GuardedModelAdmin):
    pass

class FSInline(admin.TabularInline):
    """ As you are noticed your profile will be edited as inline form """
    model = Filesystem.users.through
#     fk_name = ""

class FilePathAdmin(GuardedModelAdmin):
    pass

class FPInline(admin.TabularInline):
    model = FilePath.users.through

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'
    readonly_fields = ['created_by']
    extra = 0
    max_num = 1
    fk_name = 'user'

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

class UserAdmin(OriginalUserAdmin):
    """ Just add inlines to the original UserAdmin class """
    inlines = [FSInline, FPInline, UserProfileInline]
#     def formfield_for_manytomany(self, db_field, request, **kwargs):
#         if db_field.name == "cars":
#             kwargs["queryset"] = Car.objects.filter(owner=request.user)
#         return super(MyModelAdmin, self).formfield_for_manytomany(db_field, request, **kwargs)

try:
    admin.site.unregister(User)
finally:
    admin.site.register(User, UserAdmin)

class MessageAdmin(admin.ModelAdmin):
    exclude = ('viewed_by',)

admin.site.register(Share, ShareAdmin)
admin.site.register(Filesystem, FilesystemAdmin)
admin.site.register(FilePath, FilePathAdmin)
admin.site.register(Message,MessageAdmin)
