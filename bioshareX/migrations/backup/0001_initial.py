# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import bioshareX.models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Filesystem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=50)),
                ('description', models.TextField()),
                ('path', models.CharField(max_length=200)),
                ('archive_path', models.CharField(max_length=200)),
                ('users', models.ManyToManyField(related_name=b'filesystems', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MetaData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('subpath', models.CharField(max_length=250)),
                ('notes', models.TextField(null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Share',
            fields=[
                ('id', models.CharField(default=bioshareX.models.pkgen, max_length=15, serialize=False, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('name', models.CharField(max_length=125)),
                ('secure', models.BooleanField(default=True)),
                ('notes', models.TextField()),
                ('filesystem', models.ForeignKey(to='bioshareX.Filesystem', on_delete=django.db.models.deletion.PROTECT)),
                ('owner', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'permissions': (('view_share_files', 'View share files'), ('delete_share_files', 'Delete share files'), ('download_share_files', 'Download share files'), ('write_to_share', 'Write to share'), ('admin', 'Administer')),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ShareStats',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('num_files', models.IntegerField(default=0)),
                ('bytes', models.BigIntegerField(default=0)),
                ('updated', models.DateTimeField(null=True)),
                ('share', models.OneToOneField(related_name=b'stats', to='bioshareX.Share')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SSHKey',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=50)),
                ('key', models.TextField()),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('name', models.CharField(max_length=30, serialize=False, primary_key=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='share',
            name='tags',
            field=models.ManyToManyField(to='bioshareX.Tag'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='metadata',
            name='share',
            field=models.ForeignKey(to='bioshareX.Share'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='metadata',
            name='tags',
            field=models.ManyToManyField(to='bioshareX.Tag'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='metadata',
            unique_together=set([('share', 'subpath')]),
        ),
    ]
