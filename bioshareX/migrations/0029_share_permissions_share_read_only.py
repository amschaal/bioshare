from django.db import migrations

def add_new_permission(apps, schema_editor):
    # Get the model and ContentType
    Share = apps.get_model('bioshareX', 'Share')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')

    content_type = ContentType.objects.get_for_model(Share)

    Permission.objects.get_or_create(
        codename="share_read_only",
        name="Share read only",
        content_type=content_type,
    )

class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0028_share_last_checked')
    ]

    operations = [
        migrations.RunPython(add_new_permission),
    ]
