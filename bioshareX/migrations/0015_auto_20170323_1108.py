# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2017-03-23 18:08
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0014_insert_permissions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='share',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='sharegroupobjectpermission',
            name='content_object',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='group_permissions', to='bioshareX.Share'),
        ),
        migrations.AlterField(
            model_name='shareuserobjectpermission',
            name='content_object',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_permissions', to='bioshareX.Share'),
        ),
    ]
