from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0031_alter_sharelog_paths'),
    ]

    operations = [
        migrations.AlterField(
            model_name='share',
            name='real_path',
            field=models.CharField(blank=True, db_index=True, max_length=200, null=True),
        ),
        migrations.AddIndex(
            model_name='sharelog',
            index=models.Index(fields=['share', 'timestamp'], name='sharelog_share_ts_idx'),
        ),
    ]
