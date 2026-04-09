from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import askbot.models.post_confirmation


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('askbot', '0035_set_global_group_used_for_analytics'),
    ]

    operations = [
        migrations.CreateModel(
            name='PostConfirmation',
            fields=[
                ('key', models.CharField(
                    default=askbot.models.post_confirmation._make_key,
                    max_length=64,
                    primary_key=True,
                    serialize=False,
                )),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('expires_on', models.DateTimeField(blank=True)),
                ('post', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='confirmations',
                    to='askbot.post',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='post_confirmations',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'app_label': 'askbot',
            },
        ),
    ]
