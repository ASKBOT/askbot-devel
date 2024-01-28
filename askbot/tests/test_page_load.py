from askbot.search.state_manager import SearchState
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.core import management
from django.core.cache.backends.dummy import DummyCache
from django.core import cache
import json
from django.utils.translation import activate as activate_language

from bs4 import BeautifulSoup

import askbot
from askbot import models
from askbot.utils.slug import slugify
from askbot.utils import url_utils
from askbot.tests.utils import AskbotTestCase
from askbot.conf import settings as askbot_settings
from askbot.tests.utils import skipIf
from askbot.tests.utils import skipIf, patch_jinja2, with_settings

from askbot.skins.template_backends import Template as AskbotTemplate

patch_jinja2()


class PageLoadTestCase(AskbotTestCase):

    serialized_rollback = True

    #############################################
    #
    # INFO: We load test data once for all tests in this class (setUpClass + cleanup in tearDownClass)
    #
    #       We also disable (by overriding _fixture_setup/teardown) per-test fixture setup,
    #       which by default flushes the database for non-transactional db engines like MySQL+MyISAM.
    #       For transactional engines it only messes with transactions, but to keep things uniform
    #       for both types of databases we disable it all.
    #
    @classmethod
    def setUpClass(cls):
        management.call_command('flush', verbosity=0, interactive=False)
        everyone = models.Group.objects.get_global_group()
        everyone.can_post_questions = True
        everyone.can_post_answers = True
        everyone.can_post_comments = True
        everyone.save()
        activate_language(settings.LANGUAGE_CODE)
        management.call_command('askbot_add_test_content', verbosity=0, interactive=False)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        management.call_command('flush', verbosity=0, interactive=False)

    def _fixture_setup(self):
        pass

    def _fixture_teardown(self):
        pass

    #############################################

    def setUp(self):
        self.old_cache = cache.cache
        #Disable caching (to not interfere with production cache,
        #not sure if that's possible but let's not risk it)
        cache.cache = DummyCache('', {})
        if 'postgresql' in askbot.get_database_engine_name():
            management.call_command(
                'init_postgresql_full_text_search',
                verbosity=0,
                interactive=False
            )

    def tearDown(self):
        cache.cache = self.old_cache  # Restore caching

    def try_url(
            self,
            url_name, status_code=200, template=None,
            kwargs={}, redirect_url=None, follow=False,
            data={}, plain_url_passed=False):
        if plain_url_passed:
            url = url_name
        else:
            url = reverse(url_name, kwargs=kwargs)
        if status_code == 302:
            url_info = 'redirecting to LOGIN_URL in closed_mode: %s' % url
        else:
            url_info = 'getting url %s' % url
        if data:
            url_info += '?' + '&'.join([f'{k}={v}' for k, v in data.items()])
        # print(url_info)

        # if redirect expected, but we wont' follow
        if status_code == 302 and follow:
            response = self.client.get(url, data=data)
            self.assertTrue(url_utils.get_login_url() in response['Location'])
            return

        r = self.client.get(url, data=data, follow=follow)
        # if hasattr(self.client, 'redirect_chain'):
        #     print('redirect chain: %s' % ','.join(self.client.redirect_chain))

        # if r.status_code != status_code:
        #     print('Error in status code for url: %s' % url)

        self.assertEqual(r.status_code, status_code)

        if template and status_code != 302:
            if hasattr(r, 'template'):
                if isinstance(r.template, AskbotTemplate):
                    self.assertEqual(r.template.name, template)
                    return

            if hasattr(r, 'template'):
                templates = r.template
            elif hasattr(r, 'templates'):
                templates = r.templates
            else:
                raise NotImplementedError()

            if isinstance(templates, list):
                #asuming that there is more than one template
                template_names = [t.name for t in templates]
                # print('templates are %s' % ','.join(template_names))
                self.assertIn(template, template_names)
            else:
                raise Exception('unexpected error while runnig test')


    def test_index(self):
        #todo: merge this with all reader url tests
        response = self.client.get(reverse('index'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.redirect_chain) == 1)
        redirect_url = response.redirect_chain[0][0]
        self.assertTrue(str(redirect_url).endswith('/questions/'))
        if hasattr(response, 'template'):
            templates = response.template
        elif hasattr(response, 'templates'):
            templates = response.templates
        else:
            raise NotImplementedError()
        self.assertTrue(isinstance(templates, list))
        self.assertIn('questions/index.html', [t.name for t in templates])

    def proto_test_ask_page(self, allow_anonymous, status_code):
        prev_setting = askbot_settings.ALLOW_POSTING_BEFORE_LOGGING_IN
        askbot_settings.update('ALLOW_POSTING_BEFORE_LOGGING_IN', allow_anonymous)
        self.try_url(
            'ask',
            status_code = status_code,
            template = 'ask/index.html'
        )
        askbot_settings.update('ALLOW_POSTING_BEFORE_LOGGING_IN', prev_setting)

    def test_ask_page_allowed_anonymous(self):
        self.proto_test_ask_page(True, 200)

    @with_settings(GROUPS_ENABLED=False)
    def test_title_search_groups_disabled(self):
        data = {'query_text': 'Question'}
        response = self.client.get(reverse('api_get_questions'), data)
        data = json.loads(response.content)
        self.assertTrue(len(data) > 1)

    @with_settings(GROUPS_ENABLED=True)
    def test_title_search_groups_enabled(self):

        group = models.Group.objects.create(name='secret group',
                                            openness=models.Group.OPEN,
                                            can_post_questions=True,
                                            can_post_answers=True,
                                            can_post_comments=True)
        user = self.create_user('user')
        user.join_group(group)
        question = self.post_question(user=user, title='alibaba', group_id=group.id)

        #ask for data anonymously - should get nothing
        query_data = {'query_text': 'alibaba'}
        response = self.client.get(reverse('api_get_questions'), query_data)
        response_data = json.loads(response.content)
        self.assertEqual(len(response_data), 0)

        #log in - should get the question
        self.client.login(method='force', user_id=user.id)
        response = self.client.get(reverse('api_get_questions'), query_data)
        response_data = json.loads(response.content)
        self.assertEqual(len(response_data), 1)

    def test_ask_page_disallowed_anonymous(self):
        self.proto_test_ask_page(False, 302)

    def proto_test_non_user_urls(self, status_code):
        """test all reader views thoroughly
        on non-crashiness (no correcteness tests here)
        """
        self.try_url('sitemap')
        self.try_url(
            'get_groups_list',
            status_code=status_code
        )
        #self.try_url(
        #        'individual_question_feed',
        #        kwargs={'pk':'one-tag'},
        #        status_code=status_code)
        self.try_url(
                'latest_questions_feed',
                status_code=status_code)
        self.try_url(
                'latest_questions_feed',
                data={'tags':'one-tag'},
                status_code=status_code)
        self.try_url(
                'about',
                status_code=status_code,
                template='static_page.html')
        self.try_url(
                'privacy',
                status_code=status_code,
                template='static_page.html')
        self.try_url('logout', template='authopenid/logout.html')
        #todo: test different tabs
        self.try_url(
                'tags',
                status_code=status_code,
                template='tags/index.html')
        self.try_url(
                'tags',
                status_code=status_code,
                data={'sort':'name'}, template='tags/index.html')
        self.try_url(
                'tags',
                status_code=status_code,
                data={'sort':'used'}, template='tags/index.html')
        self.try_url(
                'badges',
                status_code=status_code,
                template='badges/index.html')
        self.try_url(
                'answer_revisions',
                status_code=status_code,
                template='revisions.html',
                kwargs={'id': models.Post.objects.get_answers().order_by('id')[0].id}
            )
        #todo: test different sort methods and scopes
        self.try_url(
            'questions',
            status_code=status_code,
            template='questions/index.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_scope('unanswered').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='questions/index.html',
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_scope('followed').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='questions/index.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_scope('unanswered').change_sort('age-desc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='questions/index.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_scope('unanswered').change_sort('age-asc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='questions/index.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_scope('unanswered').change_sort('activity-desc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='questions/index.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_scope('unanswered').change_sort('activity-asc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='questions/index.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_sort('answers-desc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='questions/index.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_sort('answers-asc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='questions/index.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_sort('votes-desc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='questions/index.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_sort('votes-asc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='questions/index.html'
        )

        self.try_url(
                'question',
                status_code=status_code,
                kwargs={'id':1},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
                follow=True,
                template='question/index.html'
            )
        self.try_url(
                'question',
                status_code=status_code,
                kwargs={'id':2},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
                follow=True,
                template='question/index.html'
            )
        self.try_url(
                'question',
                status_code=status_code,
                kwargs={'id':3},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
                follow=True,
                template='question/index.html'
            )
        self.try_url(
                'question_revisions',
                status_code=status_code,
                kwargs={'id':40},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
                template='revisions.html'
            )
        self.try_url('users',
                status_code=status_code,
                template='users/index.html'
            )
        #self.try_url(
        #        'widget_questions',
        #        status_code = status_code,
        #        data={'tags': 'tag-1-0'},
        #        template='question_widget.html',
        #    )
        #todo: really odd naming conventions for sort methods
        self.try_url(
                'users',
                status_code=status_code,
                template='users/index.html',
                data={'sort':'reputation'},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users/index.html',
                data={'sort':'newest'},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users/index.html',
                data={'sort':'last'},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users/index.html',
                data={'sort':'user'},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users/index.html',
                data={'sort':'reputation', 'page':2},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users/index.html',
                data={'sort':'newest', 'page':2},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users/index.html',
                data={'sort':'last', 'page':2},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users/index.html',
                data={'sort':'user', 'page':2},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users/index.html',
                data={'sort':'reputation', 'page':1},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users/index.html',
                data={'sort':'newest', 'page':1},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users/index.html',
                data={'sort':'last', 'page':1},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users/index.html',
                data={'sort':'user', 'page':1},
            )
        self.try_url(
                'faq',
                template='faq_static.html',
                status_code=status_code,
            )

    def test_non_user_urls(self):
        self.proto_test_non_user_urls(status_code=200)

    @skipIf('askbot.middleware.forum_mode.ForumModeMiddleware' \
        not in settings.MIDDLEWARE,
        'no ForumModeMiddleware set')
    @with_settings(ASKBOT_CLOSED_FORUM_MODE=True)
    def test_non_user_urls_in_closed_forum_mode(self):
        self.proto_test_non_user_urls(status_code=302)

    #def test_non_user_urls_logged_in(self):
        #user = User.objects.get(id=1)
        #somehow login this user
        #self.proto_test_non_user_urls()


    def proto_test_user_urls(self, status_code):
        user = models.User.objects.get(id=2)   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
        name_slug = slugify(user.username)
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
            status_code=status_code,
            data={'sort':'stats'},
            template='user_profile/user_stats.html'
        )
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
            status_code=status_code,
            data={'sort':'recent'},
            template='user_profile/user_activity.html'
        )
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
            status_code=status_code,
            data={'sort':'inbox'},
            template='authopenid/signin.html',
            follow=True
        )
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
            status_code=status_code,
            data={'sort':'reputation'},
            template='user_profile/user_reputation.html'
        )
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
            status_code=status_code,
            data={'sort':'votes'},
            template='authopenid/signin.html',
            follow = True
        )
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
            status_code=status_code,
            data={'sort':'favorites'},
            template='user_profile/user_favorites.html'
        )
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
            status_code=status_code,
            data={'sort':'email_subscriptions'},
            template='authopenid/signin.html',
            follow = True
        )

    def test_user_urls(self):
        self.proto_test_user_urls(status_code=200)

    @skipIf('askbot.middleware.forum_mode.ForumModeMiddleware' \
        not in settings.MIDDLEWARE,
        'no ForumModeMiddleware set')
    @with_settings(ASKBOT_CLOSED_FORUM_MODE=True)
    def test_user_urls_in_closed_forum_mode(self):
        self.proto_test_user_urls(status_code=302)

    def test_user_urls_logged_in(self):
        user = models.User.objects.get(id=2)   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
        name_slug = slugify(user.username)
        #works only with builtin django_authopenid
        self.client.login(method = 'force', user_id = 2)   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
        self.try_url(
            'user_subscriptions',
            kwargs = {'id': 2, 'slug': name_slug},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
            template = 'user_profile/user_email_subscriptions.html'
        )
        self.try_url(
            'edit_user',
            kwargs = {'id': 2},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
            template = 'user_profile/user_edit.html'
        )
        self.client.logout()

    def test_inbox_page(self):
        asker = models.User.objects.get(id = 2)   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
        question = asker.post_question(
            title = 'How can this happen?',
            body_text = 'This is the body of my question',
            tags = 'question answer test',
        )
        responder = models.User.objects.get(id = 3)   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
        responder.post_answer(
            question = question,
            body_text = 'this is the answer text'
        )
        self.client.login(method = 'force', user_id = asker.id)
        self.try_url(
            'user_profile',
            kwargs={'id': asker.id, 'slug': slugify(asker.username)},
            data={'sort':'inbox'},
            template='user_inbox/responses.html',
        )

    @with_settings(GROUPS_ENABLED=True)
    def test_user_page_with_groups_enabled(self):
        self.try_url('users', status_code=302)

    @with_settings(GROUPS_ENABLED=False)
    def test_user_page_with_groups_disabled(self):
        self.try_url('users', status_code=200)

class AvatarTests(AskbotTestCase):

    def test_avatar_for_two_word_user_works(self):
        self.user = self.create_user('john doe')
        response = self.client.get(
                            'avatar_render_primary',
                            kwargs = {'user': 'john doe', 'size': 48}
                        )


class QuestionViewTests(AskbotTestCase):
    def test_meta_description_has_question_summary(self):
        user = self.create_user('user')
        text = 'this is a question'
        question = self.post_question(user=user, body_text=text)
        response = self.client.get(question.get_absolute_url())
        soup = BeautifulSoup(response.content, 'html5lib')
        meta_descr = soup.find_all('meta', attrs={'name': 'description'})[0]
        self.assertTrue(text in meta_descr.attrs['content'])


class QuestionPageRedirectTests(AskbotTestCase):

    def setUp(self):
        self.create_user()

        self.q = self.post_question()
        self.q.old_question_id = 101
        self.q.save()

        self.a = self.post_answer(question=self.q)
        self.a.old_answer_id = 201
        self.a.save()

        self.c = self.post_comment(parent_post=self.a)
        self.c.old_comment_id = 301
        self.c.save()

    def test_show_bare_question(self):
        self.q.old_question_id = 101
        self.q.save()

        resp = self.client.get(self.q.get_absolute_url())
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.q, resp.context['question'])

        url = reverse('question', kwargs={'id': self.q.id})
        resp = self.client.get(url)
        self.assertRedirects(
            resp,
            expected_url=self.q.get_absolute_url()
        )

        url = reverse('question', kwargs={'id': 101})
        resp = self.client.get(url)
        url = reverse('question', kwargs={'id': self.q.id}) + self.q.slug + '/'# redirect uses the new question.id !
        self.assertRedirects(resp, expected_url=url)

        url = reverse('question', kwargs={'id': 101}) + self.q.slug + '/'
        resp = self.client.get(url)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.q, resp.context['question'])

    def test_show_answer(self):
        self.q.old_question_id = 101
        self.q.save()

        resp = self.client.get(self.a.get_absolute_url())
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.q, resp.context['question'])
        self.assertEqual(self.a, resp.context['show_post'])

        url = reverse('question', kwargs={'id': self.q.id})
        resp = self.client.get(url, data={'answer': self.a.id})

        url = self.q.get_absolute_url()
        self.assertRedirects(resp, expected_url=url + '?answer=%d' % self.a.id)

        resp = self.client.get(url, data={'answer': self.a.id})
        self.assertEqual(200, resp.status_code)
        #NOTE: below fails because resp.context in None - why it works in
        #some cases and not in others???
        #self.assertEqual(self.q, resp.context['question'])
        #self.assertEqual(self.a, resp.context['show_post'])

        #test redirect from old question
        url = reverse('question', kwargs={'id': 101}) + self.q.slug + '/'
        resp = self.client.get(url, data={'answer': 201})
        self.assertRedirects(resp, expected_url=self.a.get_absolute_url())

    def test_show_comment(self):
        resp = self.client.get(self.c.get_absolute_url())
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.q, resp.context['question'])
        self.assertEqual(self.a, resp.context['show_post'])
        self.assertEqual(self.c, resp.context['show_comment'])

        url = self.q.get_absolute_url()
        resp = self.client.get(url, data={'comment': self.c.id})
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.q, resp.context['question'])
        self.assertEqual(self.a, resp.context['show_post'])
        self.assertEqual(self.c, resp.context['show_comment'])

        url = self.q.get_absolute_url()
        #point to a non-existing comment
        resp = self.client.get(url, data={'comment': 100301})
        self.assertRedirects(resp, expected_url = self.q.get_absolute_url())

class CommandViewTests(AskbotTestCase):
    def test_load_empty_object_description_works(self):
        group = models.Group(name='somegroup')
        group.save()

        response = self.client.get(
            reverse('load_object_description'),
            data = {'object_id': group.id, 'model_name': 'Group'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')

    def test_load_full_object_description_works(self):
        group = models.Group(name='somegroup')
        user = self.create_user('someuser')
        post_params = {'author': user, 'text':'some text'}
        post = models.Post.objects.create_new_tag_wiki(**post_params)
        group.description = post
        group.save()

        response = self.client.get(
            reverse('load_object_description'),
            data = {'object_id': group.id,'model_name': 'Group'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'some text')

    def test_save_object_description_works(self):
        group = models.Group(name='somegroup')
        group.save()
        admin = self.create_user('admin', status='d')
        self.client.login(user_id=admin.id, method='force')
        post_data = {
            'object_id': group.id,
            'model_name': 'Group',
            'text': 'some description'
        }
        self.client.post(#ajax post
            reverse('save_object_description'),
            data=post_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        group = self.reload_object(group)
        self.assertEqual(group.description.text, 'some description')

        #test edit
        post_data['text'] = 'edited description'
        self.client.post(#second post to edit
            reverse('save_object_description'),
            data=post_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        group = self.reload_object(group)
        self.assertEqual(group.description.text, 'edited description')

    def test_load_object_description_fails(self):
        response = self.client.get(reverse('load_object_description'))
        self.assertEqual(response.status_code, 404)

    def test_set_tag_filter_strategy(self):
        user = self.create_user('someuser')

        def run_test_for_setting(self, filter_type, value):
            response = self.client.post(
                                reverse('set_tag_filter_strategy'),
                                data={
                                    'filter_type': filter_type,
                                    'filter_value': value
                                },
                                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
                            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b'{}')

        self.client.login(user_id=user.id, method='force')

        from askbot import conf
        values = list(dict(conf.get_tag_email_filter_strategy_choices()).keys())
        for value in values:
            run_test_for_setting(self, 'email', value)
            user = self.reload_object(user)
            self.assertEqual(user.email_tag_filter_strategy, value)

        values = list(dict(conf.get_tag_display_filter_strategy_choices()).keys())
        for value in values:
            run_test_for_setting(self, 'display', value)
            user = self.reload_object(user)
            self.assertEqual(user.display_tag_filter_strategy, value)


class UserProfilePageTests(AskbotTestCase):
    def setUp(self):
        self.user = self.create_user('user')

    @with_settings(EDITABLE_EMAIL=False, EDITABLE_SCREEN_NAME=True)
    def test_user_cannot_change_email(self):
        #log in
        self.client.login(user_id=self.user.id, method='force')
        email_before = self.user.email
        response = self.client.post(
            reverse('edit_user', kwargs={'id': self.user.id}),
            data={
                'username': 'edited',
                'email': 'fake@example.com',
                'country': 'unknown'
            }
        )
        self.assertEqual(response.status_code, 302)
        user = self.reload_object(self.user)
        self.assertEqual(user.username, 'edited')
        self.assertEqual(user.email, email_before)

    @with_settings(EDITABLE_EMAIL=True, EDITABLE_SCREEN_NAME=True)
    def test_user_can_change_email(self):
        self.client.login(user_id=self.user.id, method='force')
        email_before = self.user.email
        response = self.client.post(
            reverse('edit_user', kwargs={'id': self.user.id}),
            data={
                'username': 'edited',
                'email': 'new@example.com',
                'country': 'unknown'
            }
        )
        self.assertEqual(response.status_code, 302)
        user = self.reload_object(self.user)
        self.assertEqual(user.username, 'edited')
        self.assertEqual(user.email, 'new@example.com')

    def test_user_network(self):
        user2 = self.create_user('user2')
        user2.follow_user(self.user)
        self.user.follow_user(user2)
        name_slug = slugify(self.user.username)
        kwargs={'id': self.user.id, 'slug': name_slug}
        url = reverse('user_profile', kwargs=kwargs)
        response = self.client.get(url, data={'sort':'network'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'user_profile/user_network.html')
