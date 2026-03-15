"""Data migration: mark the global group for analytics.

The analytics feature requires at least one group with
``used_for_analytics=True``.  The global "everyone" group (which every
user belongs to) is the natural default.  This migration finds it via a
best-effort cascade of candidate names, with a structural fallback, and
flips the flag.
"""
from django.db import connection, migrations, transaction
from django.utils.translation import gettext


def _get_candidate_names():
    """Return deduplicated list of candidate names for the global group."""
    names = []
    seen = set()

    # 1. Livesettings DB value (explicit admin rename)
    #    Wrapped in transaction.atomic() to create a savepoint — if the
    #    livesettings_setting table doesn't exist yet (e.g. during test DB
    #    creation), PostgreSQL aborts the transaction; the savepoint lets
    #    us recover gracefully.
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT value FROM livesettings_setting "
                    "WHERE \"group\"='GROUP_SETTINGS' AND key='GLOBAL_GROUP_NAME'"
                )
                row = cursor.fetchone()
                if row and row[0]:
                    val = row[0].strip()
                    if val and val not in seen:
                        names.append(val)
                        seen.add(val)
    except Exception:
        pass

    # 2. gettext('everyone') — translated using LANGUAGE_CODE
    try:
        translated = gettext('everyone')
        if translated and translated not in seen:
            names.append(translated)
            seen.add(translated)
    except Exception:
        pass

    # 3. English literal fallback
    if 'everyone' not in seen:
        names.append('everyone')

    return names


def _get_largest_non_personal_group(Group):
    """Structural fallback: find the non-personal group with the most members."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT g.id, g.name, COUNT(ug.user_id) AS cnt "
                "FROM auth_group g "
                "LEFT JOIN auth_user_groups ug ON ug.group_id = g.id "
                "WHERE g.name NOT LIKE '_personal_%%' "
                "GROUP BY g.id, g.name "
                "ORDER BY cnt DESC "
                "LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                return Group.objects.get(pk=row[0])
    except Exception:
        pass
    return None


def _is_largest_group(group):
    """Sanity check: *group* must have the highest (or tied) member count."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT MAX(cnt) FROM ("
                "  SELECT COUNT(user_id) AS cnt "
                "  FROM auth_user_groups "
                "  GROUP BY group_id"
                ") sub"
            )
            row = cursor.fetchone()
            max_count = row[0] if row and row[0] is not None else 0

            cursor.execute(
                "SELECT COUNT(user_id) FROM auth_user_groups "
                "WHERE group_id = %s",
                [group.pk],
            )
            row = cursor.fetchone()
            group_count = row[0] if row and row[0] is not None else 0

            return group_count >= max_count
    except Exception:
        return False


def forward(apps, schema_editor):
    """Mark the global group for analytics."""
    try:
        Group = apps.get_model('askbot', 'Group')
    except LookupError:
        return

    group = None

    # Try candidate names
    for name in _get_candidate_names():
        try:
            group = Group.objects.get(name=name)
            break
        except Group.DoesNotExist:
            continue
        except Exception:
            continue

    # Structural fallback
    if group is None:
        group = _get_largest_non_personal_group(Group)

    if group is None:
        return

    # Sanity check
    if not _is_largest_group(group):
        return

    try:
        group.used_for_analytics = True
        group.save(update_fields=['used_for_analytics'])
    except Exception:
        pass


def reverse(apps, schema_editor):
    """Unmark the global group for analytics."""
    try:
        Group = apps.get_model('askbot', 'Group')
    except LookupError:
        return

    for name in _get_candidate_names():
        try:
            group = Group.objects.get(name=name)
            group.used_for_analytics = False
            group.save(update_fields=['used_for_analytics'])
            return
        except Group.DoesNotExist:
            continue
        except Exception:
            continue

    # Structural fallback for reverse too
    group = _get_largest_non_personal_group(Group)
    if group is not None:
        try:
            group.used_for_analytics = False
            group.save(update_fields=['used_for_analytics'])
        except Exception:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('askbot', '0034_alter_event_event_type'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
