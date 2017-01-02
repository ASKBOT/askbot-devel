"""Procedures to initialize the full text search in PostgresQL"""
import askbot
from askbot.utils.translation import get_language
from django.db import connection, models

#mapping of "django" language names to postgres
LANGUAGE_NAMES = {
    'da':    'danish',
    'de':    'german',
    'en':    'english',
    'es':    'spanish',
    'fi':    'finnish',
    'fr':    'french',
    'hu':    'hungarian',
    'it':    'italian',
    'ja':    'japanese',
    'nb':    'norwegian',
    'nl':    'dutch',
    'pt':    'portugese',
    'ro':    'romanian',
    'ru':    'russian',
    'sv':    'swedish',
    'tr':    'turkish',
    'zh-cn': 'chinese',
}

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
    original_qs = query_set
    table_name = query_set.model._meta.db_table

    rank_clause = 'ts_rank(' + table_name + \
                    '.' + text_search_vector_name + \
                    ', plainto_tsquery(%s, %s))'

    where_clause = table_name + '.' + \
                    text_search_vector_name + \
                    ' @@ plainto_tsquery(%s, %s)'

    language_code = get_language()

    #a hack with japanese search for the short queries
    if language_code in ['ja', 'zh-cn'] and len(query_text) in (1, 2):
        mul = 4/len(query_text) #4 for 1 and 2 for 2
        query_text = (query_text + ' ')*mul

    #the table name is a hack, because user does not have the language code
    if askbot.is_multilingual() and table_name == 'askbot_thread':
        where_clause += " AND " + table_name + \
                        '.' + "language_code='" + language_code + "'"

    search_query = '|'.join(query_text.split())#apply "OR" operator
    language_name = LANGUAGE_NAMES.get(language_code, 'english')
    extra_params = (language_name, search_query,)
    extra_kwargs = {
        'select': {'relevance': rank_clause},
        'where': [where_clause,],
        'params': extra_params,
        'select_params': extra_params,
    }

    result_qs = query_set.extra(**extra_kwargs)
    #added to allow search that can be ignored by postgres FTS.
    if not result_qs and len(query_text) < 5:
        return original_qs.filter(
                    models.Q(title__icontains=search_query) |
                    models.Q(tagnames__icontains=search_query) |
                    models.Q(posts__text__icontains = search_query)
                    ).extra(select={'relevance': rank_clause}, select_params=extra_params)
    return result_qs


def run_thread_search(query_set, query):
    """runs search for full thread content"""
    return run_full_text_search(query_set, query, 'text_search_vector');

run_user_search = run_thread_search #an alias

def run_title_search(query_set, query):
    """runs search for title and tags"""
    return run_full_text_search(query_set, query, 'title_search_vector')
