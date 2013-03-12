"""this module serves as a helper for the South orm
by mitigating absence of access to the django model api

since models change with time, this api is implemented in different
versions. Different versions do not need to have all the same functions.
"""
from south.db import db
from django.db import connection

def safe_add_column(table, column, column_data, keep_default = False):
    """when user calls syncdb with askbot the first time
    the auth_user table will be created together with the patched columns
    so, we need to add these columns here in separate transactions
    and roll back if they fail, if we want we could also record - which columns clash
    """
    if db.backend_name=='mysql':
        if len(db.execute('select column_name from information_schema.columns where table_name=%s and column_name=%s', params=[table, column])) == 0:
            db.add_column(table, column, column_data, keep_default = keep_default)
    	
    else:
        try:
            db.start_transaction()
            db.add_column(table, column, column_data, keep_default = keep_default)
            db.commit_transaction()
            return True
	except:
	    db.rollback_transaction()
            return False


def mysql_table_supports_full_text_search(table_name):
    """true, if engine is MyISAM"""
    cursor = connection.cursor()
    cursor.execute("SHOW CREATE TABLE %s" % table_name)
    data = cursor.fetchone()
    return 'ENGINE=MyISAM' in data[1]


def get_drop_index_sql(index_name, table_name):
    """returns sql for dropping index by name on table"""
    return 'ALTER TABLE %s DROP INDEX %s' % (table_name, index_name)


def get_create_full_text_index_sql(index_name, table_name, column_list):
    column_sql = '(%s)' % ','.join(column_list)
    query_template = 'CREATE FULLTEXT INDEX %s on %s %s'
    return query_template % (index_name, table_name, column_sql)


class BaseAPI(object):
    def __init__(self, orm):
        self.orm = orm
