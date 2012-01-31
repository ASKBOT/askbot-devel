"""Procedures to initialize the full text search in PostgresQL"""
from django.db import connection

def setup_full_text_search(script_path):
    """using postgresql database connection,
    installs the plsql language, if necessary
    and runs the stript, whose path is given as an argument
    """
    fts_init_query = open(script_path).read()

    cursor = connection.cursor()
    try:
        #test if language exists
        cursor.execute("SELECT * FROM pg_language WHERE lanname='plpgsql'")
        lang_exists = cursor.fetchone()
        if not lang_exists:
            cursor.execute("CREATE LANGUAGE plpgsql")
        #run the main query
        cursor.execute(fts_init_query)
    finally:
        cursor.close()
