from django.core.management.base import BaseCommand
from django.db import connection
from askbot.models import LocalizedUserProfile

QUERY_TPL = """SELECT count(*), auth_user_id, language_code
FROM {}
GROUP BY auth_user_id, language_code
HAVING count(*) > 1"""

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        deleted_count = 0
        cursor = connection.cursor()
        table_name = LocalizedUserProfile._meta.db_table
        cursor.execute(QUERY_TPL.format(table_name))
        while True:
            data = cursor.fetchone()
            if data is None:
                break

            cnt = data[0]
            uid = data[1]
            lang = data[2]
            dupes = LocalizedUserProfile.objects.filter(auth_user_id=uid, language_code=lang)
            for item in dupes[0:cnt-1]:
                item.delete()
                deleted_count += 1

        print(f'deleted {deleted_count} items')
