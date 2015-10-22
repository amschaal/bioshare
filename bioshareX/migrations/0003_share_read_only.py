# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0002_share_link_to_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='share',
            name='read_only',
            field=models.BooleanField(default=False),
        ),
    ]
