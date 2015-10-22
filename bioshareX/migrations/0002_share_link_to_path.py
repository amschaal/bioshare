# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='share',
            name='link_to_path',
            field=models.CharField(max_length=200, null=True, blank=True),
        ),
    ]
