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

def run_full_text_search(query_set, query_text, text_search_vector_name):
    """runs full text search against the query set and
    the search text. All words in the query text are
    added to the search with the & operator - i.e.
    the more terms in search, the narrower it is.

    It is also assumed that we ar searching in the same
    table as the query set was built against, also
    it is assumed that the table has text search vector
    stored in the column called with value of`text_search_vector_name`.
    """
    table_name = query_set.model._meta.db_table
 
    rank_clause = 'ts_rank(' + table_name + \
                    '.' + text_search_vector_name + \
                    ', plainto_tsquery(%s))'
 
    where_clause = table_name + '.' + \
                    text_search_vector_name + \
                    ' @@ plainto_tsquery(%s)'

    search_query = '&'.join(query_text.split())#apply "AND" operator
    extra_params = (search_query,)
    extra_kwargs = {
        'select': {'relevance': rank_clause},
        'where': [where_clause,],
        'params': extra_params,
        'select_params': extra_params,
    }
    return query_set.extra(**extra_kwargs)

def run_thread_search(query_set, query):
    """runs search for full thread content"""
    return run_full_text_search(query_set, query, 'text_search_vector');

def run_title_search(query_set, query):
    """runs search for title and tags"""
    return run_full_text_search(query_set, query, 'title_search_vector')
