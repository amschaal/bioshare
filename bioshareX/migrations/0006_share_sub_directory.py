# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0005_share_parent'),
    ]

    operations = [
        migrations.AddField(
            model_name='share',
            name='sub_directory',
            field=models.CharField(max_length=200, null=True, blank=True),
        ),
    ]
