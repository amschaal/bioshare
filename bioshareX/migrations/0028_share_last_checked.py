# Generated by Django 3.2.18 on 2023-04-26 21:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0027_auto_20230426_1051'),
    ]

    operations = [
        migrations.AddField(
            model_name='share',
            name='last_checked',
            field=models.DateTimeField(null=True),
        ),
    ]
