# Generated by Django 3.2.14 on 2023-04-08 17:51

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('askbot', '0021_auto_20221218_1715'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='marked_as_spam',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='post',
            name='marked_as_spam_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='post',
            name='marked_as_spam_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
    ]