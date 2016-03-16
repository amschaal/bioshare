# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
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
                ('users', models.ManyToManyField(related_name='filesystems', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='MetaData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('subpath', models.CharField(max_length=250, null=True, blank=True)),
                ('notes', models.TextField(null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Share',
            fields=[
                ('id', models.CharField(default=bioshareX.models.pkgen, max_length=15, serialize=False, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('name', models.CharField(max_length=125)),
                ('secure', models.BooleanField(default=True)),
                ('read_only', models.BooleanField(default=False)),
                ('notes', models.TextField()),
                ('link_to_path', models.CharField(max_length=200, null=True, blank=True)),
                ('sub_directory', models.CharField(max_length=200, null=True, blank=True)),
                ('real_path', models.CharField(max_length=200, null=True, blank=True)),
                ('path_exists', models.BooleanField(default=True)),
                ('filesystem', models.ForeignKey(to='bioshareX.Filesystem', on_delete=django.db.models.deletion.PROTECT)),
                ('owner', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('parent', models.ForeignKey(blank=True, to='bioshareX.Share', null=True)),
            ],
            options={
                'permissions': (('view_share_files', 'View share files'), ('delete_share_files', 'Delete share files'), ('download_share_files', 'Download share files'), ('write_to_share', 'Write to share'), ('link_to_path', 'Link to a specific path'), ('admin', 'Administer')),
            },
        ),
        migrations.CreateModel(
            name='ShareFTPUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('password', models.CharField(default=bioshareX.models.pkgen, max_length=15)),
                ('home', models.CharField(max_length=250)),
                ('share', models.OneToOneField(related_name='ftp_user', to='bioshareX.Share')),
            ],
        ),
        migrations.CreateModel(
            name='ShareStats',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('num_files', models.IntegerField(default=0)),
                ('bytes', models.BigIntegerField(default=0)),
                ('updated', models.DateTimeField(null=True)),
                ('share', models.OneToOneField(related_name='stats', to='bioshareX.Share')),
            ],
        ),
        migrations.CreateModel(
            name='SSHKey',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=50)),
                ('key', models.TextField()),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('name', models.CharField(max_length=30, serialize=False, primary_key=True)),
            ],
        ),
        migrations.AddField(
            model_name='share',
            name='tags',
            field=models.ManyToManyField(to='bioshareX.Tag'),
        ),
        migrations.AddField(
            model_name='metadata',
            name='share',
            field=models.ForeignKey(to='bioshareX.Share'),
        ),
        migrations.AddField(
            model_name='metadata',
            name='tags',
            field=models.ManyToManyField(to='bioshareX.Tag'),
        ),
        migrations.AlterUniqueTogether(
            name='metadata',
            unique_together=set([('share', 'subpath')]),
        ),
    ]
