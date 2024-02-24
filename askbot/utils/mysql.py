"""
This module served as a helper for the South orm
by mitigating absence of access to the django model api

Moved to askbot/utils/mysql.py in case these methods might be useful
"""
from django.db import connection

def mysql_table_supports_full_text_search(table_name):
    """true, if engine is MyISAM"""
    cursor = connection.cursor()
    cursor.execute("SHOW CREATE TABLE %s" % table_name)
    data = cursor.fetchone()
    return 'ENGINE=MyISAM' in data[1]


def get_drop_index_sql(index_name, table_name):
    """returns sql for dropping index by name on table"""
    return f'ALTER TABLE {table_name} DROP INDEX {index_name}'


def get_create_full_text_index_sql(index_name, table_name, column_list):
    column_sql = '(%s)' % ','.join(column_list)
    query_template = 'CREATE FULLTEXT INDEX %s on %s %s'
    return query_template % (index_name, table_name, column_sql)
