"""Forward-only teardown of askbot.deps.group_messaging.

Postgres-targeted: relies on `DROP TABLE IF EXISTS ... CASCADE`. Also
removes the dep's `django_migrations` rows so Django doesn't keep
referencing an app that no longer exists.

For a MySQL operator: drop the `CASCADE` keyword from each DROP (MySQL
behaviour differs; askbot has no FKs into these tables, so plain
`DROP TABLE IF EXISTS` is sufficient). For SQLite: same — drop `CASCADE`.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('askbot', '0036_migrate_email_validation_required')]
    operations = [
        migrations.RunSQL(
            sql=[
                "DROP TABLE IF EXISTS group_messaging_message CASCADE;",
                "DROP TABLE IF EXISTS group_messaging_messagememo CASCADE;",
                "DROP TABLE IF EXISTS group_messaging_senderlist CASCADE;",
                "DROP TABLE IF EXISTS group_messaging_lastvisittime CASCADE;",
                "DROP TABLE IF EXISTS group_messaging_unreadinboxcounter CASCADE;",
                "DELETE FROM django_migrations WHERE app='group_messaging';",
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
