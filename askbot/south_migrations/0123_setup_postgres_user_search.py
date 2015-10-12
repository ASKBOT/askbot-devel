# encoding: utf-8
import askbot
from askbot.search import postgresql
import os
from south.v2 import DataMigration

class Migration(DataMigration):
    """this migration is the same as 22 and 106
    just ran again to update the postgres search setup
    """

    def forwards(self, orm):
        "Write your forwards methods here."

        db_engine_name = askbot.get_database_engine_name()
        if 'postgresql_psycopg2' in db_engine_name:
            script_path = os.path.join(
                                askbot.get_install_directory(),
                                'search',
                                'postgresql',
                                'user_profile_search_051312.plsql'
                            )
            postgresql.setup_full_text_search(script_path)

    def backwards(self, orm):
        "Write your backwards methods here."
        pass

    models = {}#we don't need orm for this migration
