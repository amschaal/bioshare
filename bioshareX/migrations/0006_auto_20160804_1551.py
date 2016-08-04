# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-08-04 20:51
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bioshareX', '0005_sharelog_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='shareftpuser',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='shareftpuser',
            name='share',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ftp_users', to='bioshareX.Share'),
        ),
    ]
