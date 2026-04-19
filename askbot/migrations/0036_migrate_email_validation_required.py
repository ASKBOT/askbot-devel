"""Data migration: collapse ``REQUIRE_VALID_EMAIL_FOR`` into the boolean
``EMAIL_VALIDATION_REQUIRED``.

New default is ``True`` (email validation required) - the safer default
for fresh installs. Upgrading sites that had the old default
(``'nothing'`` / no row) while carrying real content (any ``Post`` rows)
get an explicit ``False`` row written to preserve their previous
behavior. Sites that had ``'see-content'`` (email was required) have any
stale row removed so the new ``True`` default applies. Fresh installs
(no posts) get no row either and inherit the new ``True`` default.

The forward function is schema-agnostic: it uses
``apps.get_model('livesettings', 'Setting')`` instead of raw SQL against
``livesettings_setting``. That shields the migration from livesettings
schema changes and DB-specific quoting of the reserved word ``group``.

``Post.objects.exists()`` is used (not ``User.objects.exists()``) so the
``createsuperuser`` before ``migrate`` sequence does not falsely mark a
fresh install as an upgrading site. Any real activity on the forum
produces at least one Post.
"""
from django.db import migrations, transaction


OLD_KEY = 'REQUIRE_VALID_EMAIL_FOR'
NEW_KEY = 'EMAIL_VALIDATION_REQUIRED'
GROUP = 'ACCESS_CONTROL'


def forward(apps, schema_editor):
    Setting = apps.get_model('livesettings', 'Setting')
    Site = apps.get_model('sites', 'Site')
    Post = apps.get_model('askbot', 'Post')

    has_posts = Post.objects.exists()

    with transaction.atomic():
        for site in Site.objects.all():
            old_rows = list(Setting.objects.filter(
                site=site, group=GROUP, key=OLD_KEY
            ))
            old_value = old_rows[0].value if old_rows else 'nothing'

            # Preserve old behavior for upgrading sites that had validation
            # off ('nothing' was the old default). Fresh installs (no Post
            # rows) get no row written and inherit the new True default.
            if old_value != 'see-content' and has_posts:
                Setting.objects.update_or_create(
                    site=site, group=GROUP, key=NEW_KEY,
                    defaults={'value': 'False'},
                )
            else:
                # 'see-content' (validation was required) or fresh install:
                # delete any stale NEW_KEY row so the new True default
                # applies cleanly.
                Setting.objects.filter(
                    site=site, group=GROUP, key=NEW_KEY
                ).delete()

            # Always drop the obsolete OLD_KEY row.
            for row in old_rows:
                row.delete()


def reverse(apps, schema_editor):
    """Reverse: reconstruct ``REQUIRE_VALID_EMAIL_FOR`` from the boolean.

    Mapping is the inverse of forward:

    - ``EMAIL_VALIDATION_REQUIRED = False`` (explicit) -> write
      ``REQUIRE_VALID_EMAIL_FOR = 'nothing'``.
    - ``EMAIL_VALIDATION_REQUIRED = True`` / missing -> write
      ``REQUIRE_VALID_EMAIL_FOR = 'see-content'`` only when there are
      posts (an upgrading site). Fresh sites get no row so the old
      ``'nothing'`` default applies.

    The old default was ``'nothing'`` while the new default is ``True``,
    so a naive reverse would silently flip fresh sites from "no
    validation" (pre-migration) to "validation required" (post-reverse).
    Gating the ``'see-content'`` write on ``has_posts`` preserves the
    pre-migration default on fresh installs and round-trips cleanly for
    upgrading sites.
    """
    Setting = apps.get_model('livesettings', 'Setting')
    Site = apps.get_model('sites', 'Site')
    Post = apps.get_model('askbot', 'Post')

    has_posts = Post.objects.exists()

    with transaction.atomic():
        for site in Site.objects.all():
            new_rows = list(Setting.objects.filter(
                site=site, group=GROUP, key=NEW_KEY
            ))
            new_value = new_rows[0].value if new_rows else 'True'

            if new_value == 'False':
                Setting.objects.update_or_create(
                    site=site, group=GROUP, key=OLD_KEY,
                    defaults={'value': 'nothing'},
                )
            elif has_posts:
                Setting.objects.update_or_create(
                    site=site, group=GROUP, key=OLD_KEY,
                    defaults={'value': 'see-content'},
                )
            else:
                Setting.objects.filter(
                    site=site, group=GROUP, key=OLD_KEY
                ).delete()

            for row in new_rows:
                row.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('askbot', '0035_set_global_group_used_for_analytics'),
        ('sites', '0001_initial'),
        ('livesettings', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
