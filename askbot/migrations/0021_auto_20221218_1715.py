# Generated by Django 3.2.14 on 2022-12-18 17:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('askbot', '0020_auto_20221217_2232'),
    ]

    operations = [
        migrations.RenameField(
            model_name='group',
            old_name='can_upload_files',
            new_name='can_upload_attachments',
        ),
        migrations.AddField(
            model_name='group',
            name='can_upload_images',
            field=models.BooleanField(default=False),
        ),
    ]