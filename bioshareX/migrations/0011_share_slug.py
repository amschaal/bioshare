# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-10-07 18:11
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0010_message_viewed_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='share',
            name='slug',
            field=models.SlugField(blank=True, null=True),
        ),
    ]
