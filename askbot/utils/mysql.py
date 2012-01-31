"""Utilities for the MySQL backend"""
from django.db import connection

#in-memory cached variable
SUPPORTS_FTS = None

def supports_full_text_search():
    """True if the database engine is MyISAM"""
    from askbot.models import Post
    global SUPPORTS_FTS
    if SUPPORTS_FTS is None:
        cursor = connection.cursor()
        table_name = Post._meta.db_table
        cursor.execute("SHOW CREATE TABLE %s" % table_name)
        data = cursor.fetchone()
        if 'ENGINE=MyISAM' in data[1]:
            SUPPORTS_FTS = True
        else:
            SUPPORTS_FTS = False
    return SUPPORTS_FTS


# This is needed to maintain compatibility with the old 0004 migration
# Usually South migrations should be self-contained and shouldn't depend on anything but themselves,
# but 0004 is an unfortunate exception
def supports_full_text_search_migr0004():
    global SUPPORTS_FTS
    if SUPPORTS_FTS is None:
        cursor = connection.cursor()
        cursor.execute("SHOW CREATE TABLE question") # In migration 0004 model forum.Question used db table `question`
        data = cursor.fetchone()
        if 'ENGINE=MyISAM' in data[1]:
            SUPPORTS_FTS = True
        else:
            SUPPORTS_FTS = False
    return SUPPORTS_FTS
