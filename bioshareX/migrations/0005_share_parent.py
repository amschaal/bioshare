# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0004_auto_20151022_1638'),
    ]

    operations = [
        migrations.AddField(
            model_name='share',
            name='parent',
            field=models.ForeignKey(blank=True, to='bioshareX.Share', null=True),
        ),
    ]
