"""Tests database api - the basic data entry 
functions that happen on behalf of users

e.g. ``some_user.do_something(...)``
"""
from django.core import exceptions
from django.core.urlresolvers import reverse
from django.test.client import Client
from django.conf import settings
from django import forms
from askbot.tests.utils import AskbotTestCase
from askbot import models
from askbot import const
from askbot.conf import settings as askbot_settings
import datetime

class DBApiTests(AskbotTestCase):

    def setUp(self):
        self.create_user()
        self.create_user(username = 'other_user')
        self.question = self.post_question()
        self.now = datetime.datetime.now()

    def post_answer(self, user = None, question = None):
        if user is None:
            user = self.user
        if question is None:
            question = self.question

        self.answer = super(DBApiTests, self).post_answer(
                                                user = user,
                                                question = question,
                                            )

    def assert_post_is_deleted(self, post):
        self.assertTrue(post.deleted == True)
        self.assertTrue(isinstance(post.deleted_by, models.User))
        self.assertTrue(post.deleted_at is not None)

    def assert_post_is_not_deleted(self, post):
        self.assertTrue(post.deleted == False)
        self.assertTrue(post.deleted_by == None)
        self.assertTrue(post.deleted_at == None)

    def test_flag_question(self):
        self.user.set_status('m')
        self.user.flag_post(self.question)
        self.assertEquals(
            self.user.get_flags().count(),
            1
        )

    def test_flag_answer(self):
        self.post_answer()
        self.user.set_status('m')
        self.user.flag_post(self.answer)
        self.assertEquals(
            self.user.get_flags().count(),
            1
        )

    def ask_anonymous_question(self):
        q = self.user.post_question(
                        is_anonymous = True,
                        body_text = 'hahahah',
                        title = 'aouaouaosuoa',
                        tags = 'test'
                    )
        return self.reload_object(q)

    def test_post_anonymous_question(self):
        q = self.ask_anonymous_question()
        self.assertTrue(q.is_anonymous)
        rev = q.revisions.all()[0]
        self.assertTrue(rev.is_anonymous)

    def test_post_bodyless_question(self):
        q = self.user.post_question(
            body_text = '',
            title = 'aeuaouaousaotuhao',
            tags = 'test'
        )
        self.assertEquals(q.text.strip(), '')

    def test_reveal_asker_identity(self):
        q = self.ask_anonymous_question()
        self.other_user.set_status('m')
        self.other_user.save()
        self.other_user.edit_question(
                            question = q,
                            title = 'hahah',
                            body_text = 'hoeuaoea',
                            tags = 'aoeuaoeu',
                            revision_comment = 'hahahah'
                        )
        q.thread.remove_author_anonymity()
        q = self.reload_object(q)
        self.assertFalse(q.is_anonymous)
        for rev in q.revisions.all():
            self.assertFalse(rev.is_anonymous)

    def test_accept_best_answer(self):
        self.post_answer(user = self.other_user)
        self.user.accept_best_answer(self.answer)

    def test_delete_question(self):
        self.user.delete_question(self.question)
        self.assert_post_is_deleted(self.question)

    def test_restore_question(self):
        self.question.deleted = True
        self.question.deleted_by = self.user
        self.question.deleted_at = self.now
        self.question.save()
        self.user.restore_post(self.question)
        self.assert_post_is_not_deleted(self.question)

    def test_delete_answer(self):
        self.post_answer(question = self.question)
        self.user.delete_answer(self.answer)
        self.assert_post_is_deleted(self.answer)
        saved_question = models.Post.objects.get_questions().get(id = self.question.id)
        self.assertEquals(0, saved_question.thread.answer_count)

    def test_restore_answer(self):
        self.post_answer()
        self.answer.deleted = True
        self.answer.deleted_by = self.user
        self.answer.deleted_at = self.now
        self.answer.save()
        self.user.restore_post(self.answer)
        self.assert_post_is_not_deleted(self.answer)

    def test_delete_question_with_answer_by_other(self):
        self.post_answer(user = self.other_user)
        self.user.delete_question(self.question)
        self.assert_post_is_deleted(self.question)
        answer_count = self.question.thread.get_answers(user = self.user).count()
        answer = self.question.thread.posts.get_answers()[0]
        self.assert_post_is_not_deleted(answer)
        self.assertTrue(answer_count == 1)
        saved_question = models.Post.objects.get_questions().get(id = self.question.id)
        self.assertTrue(saved_question.thread.answer_count == 1)

    def test_unused_tag_is_auto_deleted(self):
        self.user.retag_question(self.question, tags = 'one-tag')
        tag = models.Tag.objects.get(name='one-tag')
        self.assertEquals(tag.used_count, 1)
        self.assertEquals(tag.deleted, False)
        self.user.retag_question(self.question, tags = 'two-tag')

        count = models.Tag.objects.filter(name='one-tag').count()
        self.assertEquals(count, 0)

    def test_search_with_apostrophe_works(self):
        self.post_question(
            user = self.user,
            body_text = "ahahahahahahah database'"
        )
        matches = models.Post.objects.get_questions().get_by_text_query("database'")
        self.assertTrue(len(matches) == 1)

class UserLikeTests(AskbotTestCase):
    def setUp(self):
        self.create_user()
        self.question = self.post_question(tags = 'one two three')

    def test_user_likes_question_via_tags(self):
        truth_table = (
            ('good', 'like', True),
            ('good', 'dislike', False),
            ('bad', 'like', False),
            ('bad', 'dislike', True),
        )
        tag = models.Tag.objects.get(name = 'one')
        for item in truth_table:
            reason = item[0]
            mt = models.MarkedTag(user = self.user, tag = tag, reason = reason)
            mt.save()
            self.assertEquals(
                self.user.has_affinity_to_question(
                    question = self.question,
                    affinity_type = item[1]
                ),
                item[2]
            )
            mt.delete()

    def test_user_does_not_care_about_question_no_wildcards(self):
        askbot_settings.update('USE_WILDCARD_TAGS', False)
        tag = models.Tag(name = 'five', created_by = self.user)
        tag.save()
        mt = models.MarkedTag(user = self.user, tag = tag, reason = 'good')
        mt.save()
        self.assertFalse(
            self.user.has_affinity_to_question(
                question = self.question,
                affinity_type = 'like'
            )
        )


    def setup_wildcard(self, wildcard = None, reason = None):
        if reason == 'good':
            self.user.interesting_tags = wildcard
            self.user.ignored_tags = ''
        else:
            self.user.ignored_tags = wildcard
            self.user.interesting_tags = ''
        self.user.save()
        askbot_settings.update('USE_WILDCARD_TAGS', True)

    def assert_affinity_is(self, affinity_type, expectation):
        self.assertEquals(
            self.user.has_affinity_to_question(
                question = self.question,
                affinity_type = affinity_type
            ),
            expectation
        )

    def test_user_likes_question_via_wildcards(self):
        self.setup_wildcard('on*', 'good')
        self.assert_affinity_is('like', True)
        self.assert_affinity_is('dislike', False)

        self.setup_wildcard('aouaou* o* on* oeu*', 'good')
        self.assert_affinity_is('like', True)
        self.assert_affinity_is('dislike', False)

        self.setup_wildcard('on*', 'bad')
        self.assert_affinity_is('like', False)
        self.assert_affinity_is('dislike', True)

        self.setup_wildcard('aouaou* o* on* oeu*', 'bad')
        self.assert_affinity_is('like', False)
        self.assert_affinity_is('dislike', True)
        
        self.setup_wildcard('one*', 'good')
        self.assert_affinity_is('like', True)
        self.assert_affinity_is('dislike', False)

        self.setup_wildcard('oneone*', 'good')
        self.assert_affinity_is('like', False)
        self.assert_affinity_is('dislike', False)

class GlobalTagSubscriberGetterTests(AskbotTestCase):
    """tests for the :meth:`~askbot.models.Question.get_global_tag_based_subscribers`
    """
    def setUp(self):
        """create two users"""
        schedule = {'q_all': 'i'}
        self.u1 = self.create_user(
                        username = 'user1',
                        notification_schedule = schedule
                    )
        self.u2 = self.create_user(
                        username = 'user2',
                        notification_schedule = schedule
                    )
        self.question = self.post_question(
                                    user = self.u1,
                                    tags = "good day"
                                )

    def set_email_tag_filter_strategy(self, strategy):
        self.u1.email_tag_filter_strategy = strategy
        self.u1.save()
        self.u2.email_tag_filter_strategy = strategy
        self.u2.save()

    def assert_subscribers_are(self, expected_subscribers = None, reason = None):
        """a special assertion that compares the subscribers
        on the question with the given set"""
        subscriptions = models.EmailFeedSetting.objects.filter(
                                                    feed_type = 'q_all',
                                                    frequency = 'i'
                                                )
        actual_subscribers = self.question.get_global_tag_based_subscribers(
            tag_mark_reason = reason,
            subscription_records = subscriptions
        )
        self.assertEquals(actual_subscribers, expected_subscribers)

    def test_nobody_likes_any_tags(self):
        """no-one had marked tags, so the set 
        of subscribers must be empty
        """
        self.assert_subscribers_are(
            expected_subscribers = set(),
            reason = 'good'
        )

    def test_nobody_dislikes_any_tags(self):
        """since nobody dislikes tags - therefore
        the set must contain two users"""
        self.assert_subscribers_are(
            expected_subscribers = set([self.u1, self.u2]),
            reason = 'bad'
        )

    def test_user_likes_tag(self):
        """user set must contain one person who likes the tag"""
        self.set_email_tag_filter_strategy(const.INCLUDE_INTERESTING)
        self.u1.mark_tags(tagnames = ('day',), reason = 'good', action = 'add')
        self.assert_subscribers_are(
            expected_subscribers = set([self.u1,]),
            reason = 'good'
        )

    def test_user_dislikes_tag(self):
        """user set must have one user who does not dislike a tag"""
        self.set_email_tag_filter_strategy(const.EXCLUDE_IGNORED)
        self.u1.mark_tags(tagnames = ('day',), reason = 'bad', action = 'add')
        self.assert_subscribers_are(
            expected_subscribers = set([self.u2,]),
            reason = 'bad'
        )

    def test_user_likes_wildcard(self):
        """user set must contain one person who likes the tag via wildcard"""
        self.set_email_tag_filter_strategy(const.INCLUDE_INTERESTING)
        askbot_settings.update('USE_WILDCARD_TAGS', True)
        self.u1.mark_tags(wildcards = ('da*',), reason = 'good', action = 'add')
        self.u1.save()
        self.assert_subscribers_are(
            expected_subscribers = set([self.u1,]),
            reason = 'good'
        )

    def test_user_dislikes_wildcard(self):
        """user set must have one user who does not dislike the tag via wildcard"""
        self.set_email_tag_filter_strategy(const.EXCLUDE_IGNORED)
        askbot_settings.update('USE_WILDCARD_TAGS', True)
        self.u1.mark_tags(wildcards = ('da*',), reason = 'bad', action = 'add')
        self.u1.save()
        self.assert_subscribers_are(
            expected_subscribers = set([self.u2,]),
            reason = 'bad'
        )

    def test_user_dislikes_wildcard_and_matching_tag(self):
        """user ignores tag "day" and ignores a wildcard "da*"
        """
        self.set_email_tag_filter_strategy(const.EXCLUDE_IGNORED)
        askbot_settings.update('USE_WILDCARD_TAGS', True)
        self.u1.mark_tags(
            tagnames = ('day',),
            wildcards = ('da*',),
            reason = 'bad',
            action = 'add'
        )
        self.assert_subscribers_are(
            expected_subscribers = set([self.u2,]),
            reason = 'bad'
        )

class CommentTests(AskbotTestCase):
    """unfortunately, not very useful tests,
    as assertions of type "user can" are not inside
    the User.upvote() function
    todo: refactor vote processing code
    """
    def setUp(self):
        self.create_user()
        self.create_user(username = 'other_user')
        self.question = self.post_question()
        self.now = datetime.datetime.now()
        self.comment = self.user.post_comment(
            parent_post = self.question,
            body_text = 'lalalalalalalalal hahahah'
        )

    def test_other_user_can_upvote_comment(self):
        self.other_user.upvote(self.comment)
        models.Post.objects.precache_comments(for_posts=[self.question], visitor = self.other_user)
        comments = self.question._cached_comments
        self.assertEquals(len(comments), 1)
        self.assertEquals(comments[0].upvoted_by_user, True)
        self.assertEquals(comments[0].is_upvoted_by(self.other_user), True)

    def test_other_user_can_cancel_upvote(self):
        self.test_other_user_can_upvote_comment()
        comment = models.Post.objects.get_comments().get(id = self.comment.id)
        self.assertEquals(comment.score, 1)
        self.other_user.upvote(comment, cancel = True)
        comment = models.Post.objects.get_comments().get(id = self.comment.id)
        self.assertEquals(comment.score, 0)
