"""Forward-only teardown of askbot.deps.group_messaging.

Drops the five model tables plus the two auto-created M2M through tables,
in child-first order so plain DROP TABLE works on SQLite and MySQL.
On Postgres we append CASCADE as a safety net in case a deployment has
added its own FKs into these tables.

Also removes the dep's django_migrations rows so Django stops referencing
an app that no longer exists.
"""
from django.db import migrations


TABLES_IN_DROP_ORDER = [
    # M2M through tables first — they reference Message / SenderList.
    'group_messaging_message_recipients',
    'group_messaging_senderlist_senders',
    # Tables with FKs into Message.
    'group_messaging_lastvisittime',
    'group_messaging_messagememo',
    # SenderList is independent of Message.
    'group_messaging_senderlist',
    # Message has a self-FK; safe to drop once the children above are gone.
    'group_messaging_message',
    # Independent of the rest.
    'group_messaging_unreadinboxcounter',
]


def drop_group_messaging_tables(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    suffix = ' CASCADE' if vendor == 'postgresql' else ''
    with schema_editor.connection.cursor() as cursor:
        for table in TABLES_IN_DROP_ORDER:
            cursor.execute(f'DROP TABLE IF EXISTS {table}{suffix};')
        cursor.execute(
            "DELETE FROM django_migrations WHERE app='group_messaging';"
        )


class Migration(migrations.Migration):
    dependencies = [('askbot', '0036_migrate_email_validation_required')]
    operations = [
        migrations.RunPython(
            drop_group_messaging_tables,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
