from django.db import migrations

# Share's guardian permissions are attached to Share._meta *after* the class
# body in models.py, and migration 0003 recorded AlterModelOptions(options={})
# for Share, wiping them from the migration state.  post_migrate
# create_permissions() reads the state model, so fresh databases never get
# these Permission rows (long-lived databases have them because they predate
# 0003).  The manage_group permission monkey-patched onto auth.Group was never
# in any migration state at all.  Create them all idempotently, mirroring 0029
# which did the same for share_read_only.

SHARE_PERMISSIONS = (
    ('view_share_files', 'View share files'),
    ('delete_share_files', 'Delete share files'),
    ('download_share_files', 'Download share files'),
    ('write_to_share', 'Write to share'),
    ('link_to_path', 'Link to a specific path'),
    ('admin', 'Administer'),
    ('share_read_only', 'Share read only'),
)


def insert_custom_permissions(apps, schema_editor):
    Share = apps.get_model('bioshareX', 'Share')
    Group = apps.get_model('auth', 'Group')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')

    share_ct = ContentType.objects.get_for_model(Share)
    for codename, name in SHARE_PERMISSIONS:
        Permission.objects.get_or_create(content_type=share_ct, codename=codename,
                                         defaults={'name': name})
    group_ct = ContentType.objects.get_for_model(Group)
    Permission.objects.get_or_create(content_type=group_ct, codename='manage_group',
                                     defaults={'name': 'Manage group'})


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0033_merge_email_footer_and_worker_indexes'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(insert_custom_permissions, migrations.RunPython.noop),
    ]
