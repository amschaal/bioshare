# Written by hand to avoid pulling in the parked BigAutoField id conversions
# (see 0032_alter_filepath_id_alter_filesystem_id_and_more.py.django).
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('bioshareX', '0031_alter_sharelog_paths'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailFooter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('content', models.TextField(help_text='HTML content appended to share notification emails.')),
                ('is_default', models.BooleanField(default=False, help_text='Use as the default footer for this group.')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_footers', to='auth.group')),
            ],
            options={
                'ordering': ['group__name', 'title'],
            },
        ),
        migrations.AddField(
            model_name='share',
            name='email_footer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='shares', to='bioshareX.emailfooter'),
        ),
        migrations.AddConstraint(
            model_name='emailfooter',
            constraint=models.UniqueConstraint(condition=models.Q(('is_default', True)), fields=('group',), name='unique_default_footer_per_group'),
        ),
    ]
