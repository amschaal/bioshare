# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import bioshareX.models


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShareFTPUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('password', models.CharField(default=bioshareX.models.pkgen, max_length=15)),
                ('home', models.CharField(max_length=250)),
                ('share', models.ForeignKey(to='bioshareX.Share')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
