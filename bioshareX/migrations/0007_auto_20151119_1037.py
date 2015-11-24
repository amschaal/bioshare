# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0006_share_sub_directory'),
    ]

    operations = [
        migrations.AddField(
            model_name='share',
            name='path_exists',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='metadata',
            name='subpath',
            field=models.CharField(max_length=250, null=True, blank=True),
        ),
    ]
