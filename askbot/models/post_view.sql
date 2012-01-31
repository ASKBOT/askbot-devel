/*

SQL for creating a database VIEW for the unmanaged `Post` model

Tested with: SQLite3

Important: String literals should be wrapped in single quotes (http://www.sqlite.org/lang_keywords.html)

*/

-- DROP VIEW IF EXISTS askbot_post;

CREATE VIEW askbot_post AS

/*

Answers

*/

SELECT
    answer.id + 1000000 AS id,   -- fake unique ID - has to stay consistent with Post.parent_id for answer comments (defined below) !

    /* Some required pseudo-fields */
    'answer' AS post_type,

    NULL AS parent_id,
    joined_question.thread_id AS thread_id,

    answer.id AS self_answer_id,
    NULL AS self_question_id,
    NULL AS self_comment_id,

    /* Shared fields from content.Content */
    answer.author_id,
    answer.added_at,

    answer.deleted,
    answer.deleted_at,
    answer.deleted_by_id,

    answer.wiki,
    answer.wikified_at,

    answer.locked,
    answer.locked_by_id,
    answer.locked_at,

    answer.score,
    answer.vote_up_count,
    answer.vote_down_count,

    answer.comment_count,
    answer.offensive_flag_count,

    answer.last_edited_at,
    answer.last_edited_by_id,

    answer.html,
    answer.text,

    answer.summary,

    answer.is_anonymous

FROM answer

INNER JOIN question as joined_question
ON joined_question.id=answer.question_id

UNION

/*

Questions

*/

SELECT
    question.id AS id,   -- fake unique ID - has to stay consistent with Post.parent_id for question comments (defined below) !

    /* Some required pseudo-fields */
    'question' AS post_type,

    NULL AS parent_id,
    question.thread_id,

    NULL AS self_answer_id,
    question.id AS self_question_id,
    NULL AS self_comment_id,

    /* Shared fields from content.Content */
    question.author_id,
    question.added_at,

    question.deleted,
    question.deleted_at,
    question.deleted_by_id,

    question.wiki,
    question.wikified_at,

    question.locked,
    question.locked_by_id,
    question.locked_at,

    question.score,
    question.vote_up_count,
    question.vote_down_count,

    question.comment_count,
    question.offensive_flag_count,

    question.last_edited_at,
    question.last_edited_by_id,

    question.html,
    question.text,

    question.summary,

    question.is_anonymous

FROM question


UNION

/*

Comments to Questions

*/


SELECT
    comment.id + 2000000 AS id,   -- fake unique ID

    /* Some required pseudo-fields */
    'comment' AS post_type,

    joined_question.id AS parent_id,   -- has to stay consistent with Post.is for joined_questions !!
    joined_question.thread_id AS thread_id,

    NULL AS self_answer_id,
    NULL AS self_question_id,
    comment.id AS self_comment_id,

    /* Shared fields from content.Content */
    comment.user_id AS author_id,
    comment.added_at,

    0 AS deleted,
    NULL AS deleted_at,
    NULL AS deleted_by_id,

    0 AS wiki,
    NULL AS wikified_at,

    0 AS locked,
    NULL AS locked_by_id,
    NULL AS locked_at,

    comment.score,
    comment.score AS vote_up_count,
    0 AS vote_down_count,

    0 AS comment_count,
    comment.offensive_flag_count,

    NULL AS last_edited_at,
    NULL AS last_edited_by_id,

    comment.html,
    comment.comment AS text,

    '' AS summary,

    0 AS is_anonymous

FROM comment

INNER JOIN django_content_type AS ct
ON ct.id=comment.content_type_id AND ct.app_label='askbot' AND ct.model='question'

INNER JOIN question AS joined_question
ON joined_question.id=comment.object_id


UNION

/*

Comments to Answers

*/


SELECT
    comment.id + 2000000 AS id,   -- fake unique ID

    /* Some required pseudo-fields */
    'comment' AS post_type,

    joined_answer.id + 1000000 AS parent_id, -- has to stay consistent with Post.is for joined_questions !!
    joined_question.thread_id AS thread_id,

    NULL AS self_answer_id,
    NULL AS self_question_id,
    comment.id AS self_comment_id,

    /* Shared fields from content.Content */
    comment.user_id AS author_id,
    comment.added_at,

    0 AS deleted,
    NULL AS deleted_at,
    NULL AS deleted_by_id,

    0 AS wiki,
    NULL AS wikified_at,

    0 AS locked,
    NULL AS locked_by_id,
    NULL AS locked_at,

    comment.score,
    comment.score AS vote_up_count,
    0 AS vote_down_count,

    0 AS comment_count,
    comment.offensive_flag_count,

    NULL AS last_edited_at,
    NULL AS last_edited_by_id,

    comment.html,
    comment.comment AS text,

    '' AS summary,

    0 AS is_anonymous

FROM comment

INNER JOIN django_content_type AS ct
ON ct.id=comment.content_type_id AND ct.app_label='askbot' AND ct.model='answer'

INNER JOIN answer AS joined_answer
ON joined_answer.id=comment.object_id

INNER JOIN question AS joined_question
ON joined_question.id=joined_answer.question_id

; -- End of SQL statement
