from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0030_userprofile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sharelog',
            name='paths',
            field=models.JSONField(),
        ),
    ]
