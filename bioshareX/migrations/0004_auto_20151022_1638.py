# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0003_share_read_only'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='share',
            options={'permissions': (('view_share_files', 'View share files'), ('delete_share_files', 'Delete share files'), ('download_share_files', 'Download share files'), ('write_to_share', 'Write to share'), ('link_to_path', 'Link to a specific path'), ('admin', 'Administer'))},
        ),
    ]
