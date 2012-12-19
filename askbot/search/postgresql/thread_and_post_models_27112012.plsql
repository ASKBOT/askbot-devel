/* function testing for existence of a column in a table
   if table does not exists, function will return "false" */
CREATE OR REPLACE FUNCTION column_exists(colname text, tablename text)
RETURNS boolean AS 
$$
DECLARE
    q text;
    onerow record;
BEGIN

    q = 'SELECT attname FROM pg_attribute WHERE attrelid = ( SELECT oid FROM pg_class WHERE relname = '''||tablename||''') AND attname = '''||colname||''''; 

    FOR onerow IN EXECUTE q LOOP
        RETURN true;
    END LOOP;

    RETURN false;
END;
$$ LANGUAGE plpgsql;

/* function adding tsvector column to table if it does not exists */
CREATE OR REPLACE FUNCTION add_tsvector_column(colname text, tablename text)
RETURNS boolean AS
$$
DECLARE
    q text;
BEGIN
    IF NOT column_exists(colname, tablename) THEN
        q = 'ALTER TABLE ' || tablename || ' ADD COLUMN ' || colname || ' tsvector';
        EXECUTE q;
        RETURN true;
    ELSE
        q = 'UPDATE ' || tablename || ' SET ' || colname || '=NULL';
        EXECUTE q;
        RETURN false;
    END IF;
END;
$$ LANGUAGE plpgsql;

/* aggregate function that concatenates tsvectors */
CREATE OR REPLACE FUNCTION tsv_add(tsv1 tsvector, tsv2 tsvector)
RETURNS tsvector AS
$$
BEGIN
    RETURN tsv1 || tsv2;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION setup_aggregates() RETURNS boolean AS
$$
DECLARE
    onerow record;
BEGIN
    FOR onerow IN SELECT * FROM pg_proc WHERE proname = 'concat_tsvectors' AND proisagg LOOP
        DROP AGGREGATE concat_tsvectors(tsvector);
    END LOOP;
    CREATE AGGREGATE concat_tsvectors (
        BASETYPE = tsvector,
        SFUNC = tsv_add,
        STYPE = tsvector,
        INITCOND = ''
    );
    RETURN true;
END;
$$ LANGUAGE plpgsql;

SELECT setup_aggregates();

/* calculates text search vector for the individual thread row
DOES not include question body post, answers or comments */
CREATE OR REPLACE FUNCTION get_thread_tsv(title text, tagnames text)
RETURNS tsvector AS
$$
BEGIN
    /* todo add weight depending on votes */
    RETURN  setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(tagnames, '')), 'A');
END;
$$ LANGUAGE plpgsql;

/* calculates text seanch vector for the individual question row */
CREATE OR REPLACE FUNCTION get_post_tsv(text text, post_type text)
RETURNS tsvector AS
$$
BEGIN
    /* todo adjust weights to reflect votes */
    IF post_type='question' THEN
        RETURN setweight(to_tsvector('english', coalesce(text, '')), 'B');
    ELSIF post_type='answer' THEN
        /* todo reflect whether the answer acepted or has many points */
        RETURN setweight(to_tsvector('english', coalesce(text, '')), 'C');
    ELSIF post_type='comment' THEN
        RETURN setweight(to_tsvector('english', coalesce(text, '')), 'D');
    ELSE
        RETURN to_tsvector('');
    END IF;
END;
$$ LANGUAGE plpgsql;

/* calculates text search vector for the question body part by thread id
here we extract question title and the text by thread_id and then
calculate the text search vector. In the future question
title will be moved to the askbot_thread table and this function
will be simpler.
*/
CREATE OR REPLACE FUNCTION get_thread_question_tsv(thread_id integer)
RETURNS tsvector AS
$$
DECLARE
    query text;
    onerow record;
BEGIN
    query = 'SELECT text FROM askbot_post WHERE thread_id=' || thread_id ||
            ' AND post_type=''question'' AND deleted=false';
    FOR onerow in EXECUTE query LOOP
        RETURN get_post_tsv(onerow.text, 'question');
    END LOOP;
    RETURN to_tsvector('');
END;
$$ LANGUAGE plpgsql;

DROP FUNCTION IF EXISTS get_dependent_comments_tsv(object_id integer, tablename text);
CREATE OR REPLACE FUNCTION get_dependent_comments_tsv(parent_id integer)
RETURNS tsvector AS
$$
DECLARE
    query text;
    onerow record;
BEGIN
    query = 'SELECT concat_tsvectors(text_search_vector) FROM askbot_post' ||
        ' WHERE parent_id=' || parent_id || 
        ' AND post_type=''comment'' AND deleted=false';
    FOR onerow IN EXECUTE query LOOP
        RETURN onerow.concat_tsvectors;
    END LOOP;
    RETURN to_tsvector('');
END;
$$ LANGUAGE plpgsql;

DROP FUNCTION IF EXISTS get_dependent_answers_tsv(question_id integer);
CREATE OR REPLACE FUNCTION get_dependent_answers_tsv(thread_id integer)
RETURNS tsvector AS
$$
DECLARE
    query text;
    onerow record;
BEGIN
    query = 'SELECT concat_tsvectors(text_search_vector) ' ||
       'FROM askbot_post WHERE thread_id = ' || thread_id ||
       ' AND deleted=false';
    FOR onerow IN EXECUTE query LOOP
        RETURN onerow.concat_tsvectors;
    END LOOP;
    RETURN to_tsvector('');
END;
$$ LANGUAGE plpgsql;

/* create tsvector columns in the content tables
 need to isolate these into own transactions, b/c of a weird mix
 of triggers/update and alter table statements
*/
SELECT add_tsvector_column('text_search_vector', 'askbot_thread');
COMMIT;
BEGIN;
SELECT add_tsvector_column('text_search_vector', 'askbot_post');
COMMIT;
BEGIN;
SELECT add_tsvector_column('title_search_vector', 'askbot_thread');
COMMIT;
BEGIN;

/* populate tsvectors with data */
-- post tsvectors
UPDATE askbot_post set text_search_vector = get_post_tsv(text, 'comment') WHERE post_type='comment';
UPDATE askbot_post SET text_search_vector = get_post_tsv(text, 'answer') WHERE post_type='answer';
UPDATE askbot_post SET text_search_vector = get_post_tsv(text, 'question') WHERE post_type='question';
UPDATE askbot_post as q SET text_search_vector = text_search_vector ||
    get_dependent_comments_tsv(q.id) WHERE post_type IN ('question', 'answer');

--thread tsvector
UPDATE askbot_thread SET text_search_vector = get_thread_tsv(title, tagnames);
UPDATE askbot_thread as t SET text_search_vector = text_search_vector ||
    get_dependent_answers_tsv(t.id) ||
    get_thread_question_tsv(t.id);
UPDATE askbot_thread SET title_search_vector = get_thread_tsv(title, tagnames);

/* one trigger per table for tsv updates */

/* set up update triggers */
CREATE OR REPLACE FUNCTION thread_update_trigger() RETURNS trigger AS
$$
DECLARE
    title_tsv tsvector;
BEGIN
    title_tsv = get_thread_tsv(new.title, new.tagnames);
    new.title_search_vector = title_tsv;
    new.text_search_vector = title_tsv ||
                             get_thread_question_tsv(new.id) ||
                             get_dependent_answers_tsv(new.id);
    RETURN new;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS thread_search_vector_update_trigger on askbot_thread;
CREATE TRIGGER thread_search_vector_update_trigger 
BEFORE UPDATE ON askbot_thread FOR EACH ROW EXECUTE PROCEDURE thread_update_trigger();

CREATE OR REPLACE FUNCTION thread_insert_trigger() RETURNS trigger AS
$$
BEGIN
    new.text_search_vector = get_thread_tsv(new.title, new.tagnames);
    RETURN new;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS thread_search_vector_insert_trigger on askbot_thread;
CREATE TRIGGER thread_search_vector_insert_trigger
BEFORE INSERT ON askbot_thread FOR EACH ROW EXECUTE PROCEDURE thread_insert_trigger();

/* post trigger */
CREATE OR REPLACE FUNCTION post_trigger() RETURNS trigger AS
$$
BEGIN
    IF new.post_type = 'question' THEN
        new.text_search_vector = get_post_tsv(new.text, 'question') ||
                                 get_dependent_comments_tsv(new.id);
    ELSIF new.post_type = 'answer' THEN
        new.text_search_vector = get_post_tsv(new.text, 'answer') ||
                                 get_dependent_comments_tsv(new.id);
    ELSIF new.post_type = 'comment' THEN
        new.text_search_vector = get_post_tsv(new.text, 'comment');
    END IF;
    UPDATE askbot_thread SET id=new.thread_id WHERE id=new.thread_id;
    return new;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS post_search_vector_update_trigger on askbot_post;
CREATE TRIGGER post_search_vector_update_trigger 
BEFORE INSERT OR UPDATE ON askbot_post FOR EACH ROW EXECUTE PROCEDURE post_trigger();

DROP INDEX IF EXISTS askbot_search_idx;
CREATE INDEX askbot_search_idx ON askbot_thread USING gin(text_search_vector);
