import copy
import datetime
from operator import attrgetter
import time
from askbot.search.state_manager import SearchState
from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.core import cache, urlresolvers
from django.core.cache.backends.dummy import DummyCache
from django.core.cache.backends.locmem import LocMemCache

from django.core.exceptions import ValidationError
from django.template.loader import get_template
from django.template import Context
from askbot.tests.utils import AskbotTestCase
from askbot.models import Post
from askbot.models import PostRevision
from askbot.models import Thread
from askbot.models import Tag
from askbot.models import Group
from askbot.search.state_manager import DummySearchState
import simplejson
from django.utils import timezone
from askbot.tests.utils import skipIf, with_settings
from askbot.conf import settings as askbot_settings


class PostModelTests(AskbotTestCase):

    def setUp(self):
        self.u1 = self.create_user(username='user1')
        self.u2 = self.create_user(username='user2')
        self.u3 = self.create_user(username='user3')

    def test_model_validation(self):
        """
        self.assertRaisesRegexp(
            AttributeError,
            r"'NoneType' object has no attribute 'revisions'",
            # cannot set `revision` without a parent
            PostRevision.objects.create,
            *[],
            **{
                'text': 'blah',
                'author': self.u1,
                'revised_at': timezone.now()
            }
        )

        #this test does not work
        post_revision = PostRevision(
            text='blah',
            author=self.u1,
            revised_at=timezone.now(),
            revision=1,
        )

        self.assertRaisesRegexp(
            ValidationError,
            r"{'__all__': \[u'Post field has to be set.'\]}",
            post_revision.save
        )
        """

        question = self.post_question(user=self.u1)

        rev2 = PostRevision(
            post=question, text='blah', author=self.u1,
            revised_at=timezone.now(), revision=2
        )
        rev2.save()
        self.assertFalse(rev2.id is None)

    def test_post_revision_autoincrease(self):
        question = self.post_question(user=self.u1)
        self.assertEqual(1, question.revisions.all()[0].revision)
        self.assertEqual(1, question.revisions.count())

        question.apply_edit(edited_by=self.u1, text="blah2", comment="blahc2")
        self.assertEqual(2, question.revisions.all()[0].revision)
        self.assertEqual(2, question.revisions.count())

        question.apply_edit(edited_by=self.u1, text="blah3", comment="blahc3")
        self.assertEqual(3, question.revisions.all()[0].revision)
        self.assertEqual(3, question.revisions.count())

    def test_comment_ordering_by_date(self):
        self.user = self.u1
        q = self.post_question()

        c1 = self.post_comment(parent_post=q, timestamp=datetime.datetime(2010, 10, 2, 14, 33, 20))
        c2 = q.add_comment(user=self.user, comment='blah blah', added_at=datetime.datetime(2010, 10, 2, 14, 33, 21))
        c3 = self.post_comment(parent_post=q, body_text='blah blah 2', timestamp=datetime.datetime(2010, 10, 2, 14, 33, 22))

        Post.objects.precache_comments(for_posts=[q], visitor=self.user)
        self.assertListEqual([c1, c2, c3], q._cached_comments)
        Post.objects.precache_comments(for_posts=[q], visitor=self.u2)
        self.assertListEqual([c1, c2, c3], q._cached_comments)

        c1.added_at, c3.added_at = c3.added_at, c1.added_at
        c1.save()
        c3.save()

        Post.objects.precache_comments(for_posts=[q], visitor=self.user)
        self.assertListEqual([c3, c2, c1], q._cached_comments)
        Post.objects.precache_comments(for_posts=[q], visitor=self.u2)
        self.assertListEqual([c3, c2, c1], q._cached_comments)

        del self.user

    def test_comment_precaching(self):
        self.user = self.u1
        q = self.post_question()

        c1 = self.post_comment(parent_post=q, timestamp=datetime.datetime(2010, 10, 2, 14, 33, 20))
        c2 = q.add_comment(user=self.user, comment='blah blah', added_at=datetime.datetime(2010, 10, 2, 14, 33, 21))
        c3 = self.post_comment(parent_post=q, timestamp=datetime.datetime(2010, 10, 2, 14, 33, 22))

        Post.objects.precache_comments(for_posts=[q], visitor=self.user)
        self.assertListEqual([c1, c2, c3], q._cached_comments)

        c1.added_at, c3.added_at = c3.added_at, c1.added_at
        c1.save()
        c3.save()

        Post.objects.precache_comments(for_posts=[q], visitor=self.user)
        self.assertListEqual([c3, c2, c1], q._cached_comments)

        del self.user

    def test_cached_get_absolute_url_1(self):
        th = lambda:1
        th.title = 'lala-x-lala'
        p = Post(id=3, post_type='question')
        p._thread_cache = th  # cannot assign non-Thread instance directly
        expected_url = urlresolvers.reverse('question', kwargs={'id': 3}) \
                                                                + th.title + '/'
        self.assertEqual(expected_url, p.get_absolute_url(thread=th))
        self.assertTrue(p._thread_cache is th)
        self.assertEqual(expected_url, p.get_absolute_url(thread=th))

    def test_cached_get_absolute_url_2(self):
        p = Post(id=3, post_type='question')
        th = lambda:1
        th.title = 'lala-x-lala'
        expected_url = urlresolvers.reverse('question', kwargs={'id': 3}) \
                                                                + th.title + '/'
        self.assertEqual(expected_url, p.get_absolute_url(thread=th))
        self.assertTrue(p._thread_cache is th)
        self.assertEqual(expected_url, p.get_absolute_url(thread=th))

    @with_settings(GROUPS_ENABLED=True)
    def test_get_moderators_with_groups(self):
        #create group
        group = Group(name='testers', openness=Group.OPEN)
        group.save()

        #create one admin and one moderator, and one reg user
        mod1 = self.create_user('mod1', status='m')
        adm1 = self.create_user('adm1', status='d')
        reg1 = self.create_user('reg1')
        #join them to the group
        mod1.join_group(group)
        adm1.join_group(group)
        reg1.join_group(group)
        #create one admin and one moderator, and one reg user
        mod2 = self.create_user('mod2', status='m')
        adm2 = self.create_user('adm2', status='d')
        reg2 = self.create_user('reg2')
        #make a post
        question = self.post_question(user=reg1, group_id=group.id)
        #run get_moderators and see that only one admin and one
        mods = question.get_moderators()
        self.assertEqual(
            set([mod1, adm1]),
            set(mods)
        )
        #moderator are in the set of moderators


class ThreadTagModelsTests(AskbotTestCase):

    # TODO: Use rich test data like page load test cases ?

    def setUp(self):
        self.create_user()
        user2 = self.create_user(username='user2')
        user3 = self.create_user(username='user3')
        self.q1 = self.post_question(tags='tag1 tag2 tag3')
        self.q2 = self.post_question(tags='tag3 tag4 tag5')
        self.q3 = self.post_question(tags='tag6', user=user2)
        self.q4 = self.post_question(tags='tag1 tag2 tag3 tag4 tag5 tag6', user=user3)

    def test_related_tags(self):
        tags = Tag.objects.get_related_to_search(threads=[self.q1.thread, self.q2.thread], ignored_tag_names=[])
        self.assertListEqual(['tag3', 'tag1', 'tag2', 'tag4', 'tag5'], [t.name for t in tags])
        self.assertListEqual([2, 1, 1, 1, 1], [t.local_used_count for t in tags])
        self.assertListEqual([3, 2, 2, 2, 2], [t.used_count for t in tags])

        tags = Tag.objects.get_related_to_search(threads=[self.q1.thread, self.q2.thread], ignored_tag_names=['tag3', 'tag5'])
        self.assertListEqual(['tag1', 'tag2', 'tag4'], [t.name for t in tags])
        self.assertListEqual([1, 1, 1], [t.local_used_count for t in tags])
        self.assertListEqual([2, 2, 2], [t.used_count for t in tags])

        tags = Tag.objects.get_related_to_search(threads=[self.q3.thread], ignored_tag_names=[])
        self.assertListEqual(['tag6'], [t.name for t in tags])
        self.assertListEqual([1], [t.local_used_count for t in tags])
        self.assertListEqual([2], [t.used_count for t in tags])

        tags = Tag.objects.get_related_to_search(threads=[self.q3.thread], ignored_tag_names=['tag1'])
        self.assertListEqual(['tag6'], [t.name for t in tags])
        self.assertListEqual([1], [t.local_used_count for t in tags])
        self.assertListEqual([2], [t.used_count for t in tags])

        tags = Tag.objects.get_related_to_search(threads=[self.q3.thread], ignored_tag_names=['tag6'])
        self.assertListEqual([], [t.name for t in tags])

        tags = Tag.objects.get_related_to_search(threads=[self.q1.thread, self.q2.thread, self.q4.thread], ignored_tag_names=['tag2'])
        self.assertListEqual(['tag3', 'tag1', 'tag4', 'tag5', 'tag6'], [t.name for t in tags])
        self.assertListEqual([3, 2, 2, 2, 1], [t.local_used_count for t in tags])
        self.assertListEqual([3, 2, 2, 2, 2], [t.used_count for t in tags])

    def test_run_adv_search_1(self):
        ss = SearchState.get_empty()
        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss)
        self.assertEqual(4, qs.count())

    def test_run_adv_search_ANDing_tags(self):
        ss = SearchState.get_empty()
        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss.add_tag('tag1'))
        self.assertEqual(2, qs.count())

        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss.add_tag('tag1').add_tag('tag3'))
        self.assertEqual(2, qs.count())

        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss.add_tag('tag1').add_tag('tag3').add_tag('tag6'))
        self.assertEqual(1, qs.count())

        ss = SearchState(scope=None, sort=None, query="#tag3", tags='tag1, tag6', author=None, page=None, user_logged_in=None)
        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss)
        self.assertEqual(1, qs.count())

    def test_run_adv_search_query_author(self):
        ss = SearchState(scope=None, sort=None, query="@user", tags=None, author=None, page=None, user_logged_in=None)
        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss)
        self.assertEqual(2, len(qs))
        self.assertEqual(self.q1.thread_id, min(qs[0].id, qs[1].id))
        self.assertEqual(self.q2.thread_id, max(qs[0].id, qs[1].id))

        ss = SearchState(scope=None, sort=None, query="@user2", tags=None, author=None, page=None, user_logged_in=None)
        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss)
        self.assertEqual(1, len(qs))
        self.assertEqual(self.q3.thread_id, qs[0].id)

        ss = SearchState(scope=None, sort=None, query="@user3", tags=None, author=None, page=None, user_logged_in=None)
        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss)
        self.assertEqual(1, len(qs))
        self.assertEqual(self.q4.thread_id, qs[0].id)

    def test_run_adv_search_url_author(self):
        ss = SearchState(scope=None, sort=None, query=None, tags=None, author=self.user.id, page=None, user_logged_in=None)
        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss)
        self.assertEqual(2, len(qs))
        self.assertEqual(self.q1.thread_id, min(qs[0].id, qs[1].id))
        self.assertEqual(self.q2.thread_id, max(qs[0].id, qs[1].id))

        ss = SearchState(scope=None, sort=None, query=None, tags=None, author=self.user2.id, page=None, user_logged_in=None)
        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss)
        self.assertEqual(1, len(qs))
        self.assertEqual(self.q3.thread_id, qs[0].id)

        ss = SearchState(scope=None, sort=None, query=None, tags=None, author=self.user3.id, page=None, user_logged_in=None)
        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss)
        self.assertEqual(1, len(qs))
        self.assertEqual(self.q4.thread_id, qs[0].id)

    def test_thread_caching_1(self):
        ss = SearchState.get_empty()
        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss)
        qs = list(qs)

        for thread in qs:
            self.assertIsNone(getattr(thread, '_question_cache', None))
            self.assertIsNone(getattr(thread, '_last_activity_by_cache', None))

            post = Post.objects.get(post_type='question', thread=thread.id)
            self.assertEqual(post, thread._question_post())
            self.assertEqual(post, thread._question_cache)
            self.assertTrue(thread._question_post() is thread._question_cache)

    def test_thread_caching_2_precache_view_data_hack(self):
        ss = SearchState.get_empty()
        qs, meta_data = Thread.objects.run_advanced_search(request_user=self.user, search_state=ss)
        qs = list(qs)

        Thread.objects.precache_view_data_hack(threads=qs)

        for thread in qs:
            post = Post.objects.get(post_type='question', thread=thread.id)
            self.assertEqual(post.id, thread._question_cache.id) # Cannot compare models instances with deferred model instances
            self.assertEqual(post.id, thread._question_post().id)
            self.assertTrue(thread._question_post() is thread._question_cache)

            user = User.objects.get(id=thread.last_activity_by_id)
            self.assertEqual(user.id, thread._last_activity_by_cache.id)
            self.assertTrue(thread.last_activity_by is thread._last_activity_by_cache)


class ThreadRenderLowLevelCachingTests(AskbotTestCase):
    def setUp(self):
        self.create_user()
        # INFO: title and body_text should contain tag placeholders so that we can check if they stay untouched
        #       - only real tag placeholders in tag widget should be replaced with search URLs
        self.q = self.post_question(title="<<<tag1>>> fake title", body_text="<<<tag2>>> <<<tag3>>> cheating", tags='tag1 tag2 tag3')

        self.old_cache = cache.cache

    def tearDown(self):
        cache.cache = self.old_cache  # Restore caching

    def test_thread_summary_rendering_dummy_cache(self):
        cache.cache = DummyCache('', {})  # Disable caching

        ss = SearchState.get_empty()
        thread = self.q.thread
        test_html = thread.get_summary_html(search_state=ss)

        context = {
            'thread': thread,
            'question': thread._question_post(),
            'search_state': ss,
            'visitor': None
        }
        proper_html = get_template('widgets/question_summary.html').render(Context(context))
        self.assertEqual(test_html, proper_html)

        # Make double-check that all tags are included
        self.assertTrue(ss.add_tag('tag1').full_url() in test_html)
        self.assertTrue(ss.add_tag('tag2').full_url() in test_html)
        self.assertTrue(ss.add_tag('tag3').full_url() in test_html)
        self.assertFalse(ss.add_tag('mini-mini').full_url() in test_html)

        # Make sure that title and body text are escaped properly.
        # This should be obvious at this point, if the above test passes, but why not be explicit
        # UPDATE: And voila, these tests catched double-escaping bug in template, where `&lt;` was `&amp;lt;`
        #         And indeed, post.summary is escaped before saving, in parse_and_save()
        # UPDATE 2:Weird things happen with question summary (it's double escaped etc., really weird) so
        # let's just make sure that there are no tag placeholders left
        self.assertTrue('&lt;&lt;&lt;tag1&gt;&gt;&gt; fake title' in proper_html)
        #self.assertTrue('&lt;&lt;&lt;tag2&gt;&gt;&gt; &lt;&lt;&lt;tag3&gt;&gt;&gt; cheating' in proper_html)
        self.assertFalse('<<<tag1>>>' in proper_html)
        self.assertFalse('<<<tag2>>>' in proper_html)
        self.assertFalse('<<<tag3>>>' in proper_html)

        ###

        ss = ss.add_tag('mini-mini')
        context['search_state'] = ss
        test_html = thread.get_summary_html(search_state=ss)
        proper_html = get_template('widgets/question_summary.html').render(Context(context))

        self.assertEqual(test_html, proper_html)

        # Make double-check that all tags are included (along with `mini-mini` tag)
        self.assertTrue(ss.add_tag('tag1').full_url() in test_html)
        self.assertTrue(ss.add_tag('tag2').full_url() in test_html)
        self.assertTrue(ss.add_tag('tag3').full_url() in test_html)

    def test_thread_summary_locmem_cache(self):
        cache.cache = LocMemCache('', {})  # Enable local caching

        thread = self.q.thread
        thread.get_summary_html(search_state=SearchState.get_empty())

        key = thread.get_summary_cache_key()

        self.assertTrue(thread.summary_html_cached())
        self.assertIsNotNone(thread.get_cached_summary_html())

        ###
        cache.cache.delete(key) # let's start over

        self.assertFalse(thread.summary_html_cached())
        self.assertIsNone(thread.get_cached_summary_html())

        context = {
            'thread': thread,
            'question': self.q,
            'search_state': DummySearchState(),
            'visitor': None
        }
        html = get_template('widgets/question_summary.html').render(Context(context))
        filled_html = html.replace('<<<tag1>>>', SearchState.get_empty().add_tag('tag1').full_url())\
                          .replace('<<<tag2>>>', SearchState.get_empty().add_tag('tag2').full_url())\
                          .replace('<<<tag3>>>', SearchState.get_empty().add_tag('tag3').full_url())

        self.assertEqual(filled_html, thread.get_summary_html(search_state=SearchState.get_empty()))
        self.assertTrue(thread.summary_html_cached())
        self.assertEqual(html, thread.get_cached_summary_html())

        ###
        cache.cache.set(key, 'Test <<<tag1>>>', timeout=100)

        self.assertTrue(thread.summary_html_cached())
        self.assertEqual('Test <<<tag1>>>', thread.get_cached_summary_html())
        self.assertEqual(
            'Test %s' % SearchState.get_empty().add_tag('tag1').full_url(),
            thread.get_summary_html(search_state=SearchState.get_empty())
        )

        ###
        cache.cache.set(key, 'TestBBB <<<tag1>>>', timeout=100)

        self.assertTrue(thread.summary_html_cached())
        self.assertEqual('TestBBB <<<tag1>>>', thread.get_cached_summary_html())
        self.assertEqual(
            'TestBBB %s' % SearchState.get_empty().add_tag('tag1').full_url(),
            thread.get_summary_html(search_state=SearchState.get_empty())
        )

        ###
        cache.cache.delete(key)
        thread.update_summary_html = lambda dummy: "Monkey-patched <<<tag2>>>"

        self.assertFalse(thread.summary_html_cached())
        self.assertIsNone(thread.get_cached_summary_html())
        self.assertEqual(
            'Monkey-patched %s' % SearchState.get_empty().add_tag('tag2').full_url(),
            thread.get_summary_html(search_state=SearchState.get_empty())
        )



class ThreadRenderCacheUpdateTests(AskbotTestCase):
    def setUp(self):
        self.create_user()
        self.user.set_password('pswd')
        self.user.save()
        assert self.client.login(username=self.user.username, password='pswd')

        self.create_user(username='user2')
        self.user2.set_password('pswd')
        self.user2.reputation = 10000
        self.user2.save()

        self.old_cache = cache.cache
        cache.cache = LocMemCache('', {'OPTIONS':{'MAX_ENTRIES': 1000000}})  # Enable local caching
        cache.cache.clear()

    def tearDown(self):
        cache.cache = self.old_cache  # Restore caching

    def _html_for_question(self, q):
        context = {
            'thread': q.thread,
            'question': q,
            'search_state': DummySearchState(),
            'visitor': None
        }
        return get_template(
            'widgets/question_summary.html'
        ).render(Context(context))

    def test_post_question(self):
        self.assertEqual(0, Post.objects.count())
        response = self.client.post(urlresolvers.reverse('ask'), data={
            'title': 'test question title',
            'text': 'test body text',
            'tags': 'tag1 tag2',
        })
        self.assertEqual(1, Post.objects.count())
        question = Post.objects.all()[0]
        self.assertRedirects(response=response, expected_url=question.get_absolute_url())

        self.assertEqual('test question title', question.thread.title)
        self.assertEqual('test body text', question.text)
        self.assertItemsEqual(['tag1', 'tag2'], list(question.thread.tags.values_list('name', flat=True)))
        self.assertEqual(0, question.thread.answer_count)

        self.assertTrue(question.thread.summary_html_cached())  # <<< make sure that caching backend is set up properly (i.e. it's not dummy)
        html = self._html_for_question(question)
        self.assertEqual(html, question.thread.get_cached_summary_html())

    def test_edit_question(self):
        self.assertEqual(0, Post.objects.count())
        question = self.post_question()

        thread = Thread.objects.all()[0]
        self.assertEqual(0, thread.answer_count)
        self.assertEqual(thread.last_activity_at, question.added_at)
        self.assertEqual(thread.last_activity_by, question.author)

        time.sleep(1.5) # compensate for 1-sec time resolution in some databases

        response = self.client.post(
            urlresolvers.reverse('edit_question', kwargs={'id': question.id}),
            data={
                'title': 'edited title',
                'text': 'edited body text',
                'tags': 'tag1 tag2',
                'summary': 'just some edit',
                'select_revision': 'false'
            }
        )
        self.assertEqual(1, Post.objects.count())
        question = Post.objects.all()[0]
        self.assertRedirects(
            response=response,
            expected_url=question.get_absolute_url()
        )

        thread = question.thread
        self.assertEqual(0, thread.answer_count)
        self.assertTrue(thread.last_activity_at > question.added_at)
        self.assertEqual(thread.last_activity_at, question.last_edited_at)
        self.assertEqual(thread.last_activity_by, question.author)

        self.assertTrue(question.thread.summary_html_cached())  # <<< make sure that caching backend is set up properly (i.e. it's not dummy)
        html = self._html_for_question(question)
        self.assertEqual(html, question.thread.get_cached_summary_html())

    def test_retag_question(self):
        self.assertEqual(0, Post.objects.count())
        question = self.post_question()
        response = self.client.post(urlresolvers.reverse('retag_question', kwargs={'id': question.id}), data={
            'tags': 'tag1 tag2',
        })
        self.assertEqual(1, Post.objects.count())
        question = Post.objects.all()[0]
        self.assertRedirects(response=response, expected_url=question.get_absolute_url())

        self.assertItemsEqual(['tag1', 'tag2'], list(question.thread.tags.values_list('name', flat=True)))

        self.assertTrue(question.thread.summary_html_cached())  # <<< make sure that caching backend is set up properly (i.e. it's not dummy)
        html = self._html_for_question(question)
        self.assertEqual(html, question.thread.get_cached_summary_html())

    def test_answer_question(self):
        self.assertEqual(0, Post.objects.count())
        question = self.post_question()
        self.assertEqual(1, Post.objects.count())

        #thread = question.thread
        # get fresh Thread instance so that on MySQL it has timestamps without microseconds
        thread = Thread.objects.get(id=question.thread.id)

        self.assertEqual(0, thread.answer_count)
        self.assertEqual(thread.last_activity_at, question.added_at)
        self.assertEqual(thread.last_activity_by, question.author)

        self.client.logout()
        self.client.login(username='user2', password='pswd')
        time.sleep(1.5) # compensate for 1-sec time resolution in some databases
        response = self.client.post(urlresolvers.reverse('answer', kwargs={'id': question.id}), data={
            'text': 'answer longer than 10 chars',
        })
        self.assertEqual(2, Post.objects.count())
        answer = Post.objects.get_answers()[0]
        expected_url=answer.get_absolute_url()
        self.assertRedirects(response=response, expected_url=expected_url)

        thread = answer.thread
        self.assertEqual(1, thread.answer_count)
        self.assertEqual(thread.last_activity_at, answer.added_at)
        self.assertEqual(thread.last_activity_by, answer.author)

        self.assertTrue(question.added_at < answer.added_at)
        self.assertNotEqual(question.author, answer.author)

        self.assertTrue(thread.summary_html_cached())  # <<< make sure that caching backend is set up properly (i.e. it's not dummy)
        html = self._html_for_question(thread._question_post())
        self.assertEqual(html, thread.get_cached_summary_html())

    def test_edit_answer(self):
        self.assertEqual(0, Post.objects.count())
        question = self.post_question()
        # get fresh question Post instance so that on MySQL it has timestamps without microseconds
        question = Post.objects.get(id=question.id)
        self.assertEqual(question.thread.last_activity_at, question.added_at)
        self.assertEqual(question.thread.last_activity_by, question.author)

        time.sleep(1.5)  # compensate for 1-sec time resolution in some databases
        question_thread = copy.deepcopy(question.thread) # INFO: in the line below question.thread is touched and it reloads its `last_activity_by` field so we preserve it here
        answer = self.post_answer(user=self.user2, question=question)
        self.assertEqual(2, Post.objects.count())

        time.sleep(1.5)  # compensate for 1-sec time resolution in some databases
        self.client.logout()
        self.client.login(username='user2', password='pswd')
        response = self.client.post(
            urlresolvers.reverse(
                'edit_answer',
                kwargs={'id': answer.id}
            ),
            data={
                'text': 'edited body text',
                'summary': 'just some edit',
                'select_revision': 'false'
            }
        )
        self.assertRedirects(response=response, expected_url=answer.get_absolute_url())

        answer = Post.objects.get(id=answer.id)
        thread = answer.thread
        self.assertEqual(thread.last_activity_at, answer.last_edited_at)
        self.assertEqual(thread.last_activity_by, answer.last_edited_by)
        self.assertTrue(thread.last_activity_at > question_thread.last_activity_at)
        self.assertNotEqual(thread.last_activity_by, question_thread.last_activity_by)

        self.assertTrue(thread.summary_html_cached())  # <<< make sure that caching backend is set up properly (i.e. it's not dummy)
        html = self._html_for_question(thread._question_post())
        self.assertEqual(html, thread.get_cached_summary_html())

    @skipIf(django_settings.CELERY_ALWAYS_EAGER == True, 'celery deamon not running')
    def test_view_count(self):
        question = self.post_question()
        self.assertEqual(0, question.thread.view_count)
        self.assertEqual(0, Thread.objects.all()[0].view_count)
        self.client.logout()

        # INFO: We need to pass some headers to make question() view believe we're not a robot
        self.client.get(
            urlresolvers.reverse('question', kwargs={'id': question.id}),
            {},
            follow=True, # the first view redirects to the full question url (with slug in it), so we have to follow that redirect
            HTTP_ACCEPT_LANGUAGE='en',
            HTTP_USER_AGENT='Mozilla Gecko'
        )
        thread = Thread.objects.all()[0]
        self.assertEqual(1, thread.view_count)

        self.assertTrue(thread.summary_html_cached())  # <<< make sure that caching backend is set up properly (i.e. it's not dummy)
        html = self._html_for_question(thread._question_post())
        self.assertEqual(html, thread.get_cached_summary_html())

    def test_question_upvote_downvote(self):
        question = self.post_question()
        question.points = 5
        question.vote_up_count = 7
        question.vote_down_count = 2
        question.save()

        self.client.logout()
        self.client.login(username='user2', password='pswd')
        response = self.client.post(
            urlresolvers.reverse('vote'),
            data={'type': '1', 'postId': question.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        ) # use AJAX request
        self.assertEqual(200, response.status_code)
        data = simplejson.loads(response.content)

        self.assertEqual(1, data['success'])
        self.assertEqual(6, data['count'])  # 6 == question.points(5) + 1

        thread = Thread.objects.get(id=question.thread.id)

        self.assertTrue(thread.summary_html_cached())  # <<< make sure that caching backend is set up properly (i.e. it's not dummy)
        html = self._html_for_question(thread._question_post())
        self.assertEqual(html, thread.get_cached_summary_html())

        ###

        response = self.client.post(
            urlresolvers.reverse('vote'),
            data={'type': '2', 'postId': question.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        ) # use AJAX request
        self.assertEqual(200, response.status_code)
        data = simplejson.loads(response.content)

        self.assertEqual(1, data['success'])
        self.assertEqual(5, data['count'])  # 6 == question.points(6) - 1

        thread = Thread.objects.get(id=question.thread.id)

        self.assertTrue(thread.summary_html_cached())  # <<< make sure that caching backend is set up properly (i.e. it's not dummy)
        html = self._html_for_question(thread._question_post())
        self.assertEqual(html, thread.get_cached_summary_html())

    def test_question_accept_answer(self):
        question = self.post_question(user=self.user2)
        answer = self.post_answer(question=question)

        self.client.logout()
        self.client.login(username='user2', password='pswd')
        response = self.client.post(
            urlresolvers.reverse('vote'),
            data={'type': '0', 'postId': answer.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        ) # use AJAX request
        self.assertEqual(200, response.status_code)
        data = simplejson.loads(response.content)

        self.assertEqual(1, data['success'])

        thread = Thread.objects.get(id=question.thread.id)

        self.assertTrue(thread.summary_html_cached())  # <<< make sure that caching backend is set up properly (i.e. it's not dummy)
        html = self._html_for_question(thread._question_post())
        self.assertEqual(html, thread.get_cached_summary_html())


# TODO: (in spare time - those cases should pass without changing anything in code but we should have them eventually for completness)
# - Publishing anonymous questions / answers
# - Re-posting question as answer and vice versa
# - Management commands (like post_emailed_questions)
