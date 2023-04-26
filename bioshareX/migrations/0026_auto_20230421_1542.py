# Generated by Django 3.2.18 on 2023-04-21 22:42

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('bioshareX', '0025_auto_20210608_0951'),
    ]

    operations = [
        migrations.AddField(
            model_name='share',
            name='illegal_path_found',
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name='filesystem',
            name='type',
            field=models.CharField(choices=[('STANDARD', 'Standard'), ('ZFS', 'ZFS')], default='STANDARD', max_length=20),
        ),
        migrations.AlterField(
            model_name='groupprofile',
            name='group',
            field=models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='profile', to='auth.group'),
        ),
        migrations.AlterField(
            model_name='metadata',
            name='share',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bioshareX.share'),
        ),
        migrations.AlterField(
            model_name='share',
            name='filepath',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, to='bioshareX.filepath'),
        ),
        migrations.AlterField(
            model_name='share',
            name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, to='bioshareX.share'),
        ),
        migrations.AlterField(
            model_name='sharelog',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='sharestats',
            name='share',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='stats', to='bioshareX.share'),
        ),
        migrations.AlterField(
            model_name='sshkey',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]