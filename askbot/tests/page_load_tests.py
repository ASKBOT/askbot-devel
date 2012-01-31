from askbot.search.state_manager import SearchState
from django.test import signals
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core import management
from django.core.cache.backends.dummy import DummyCache
from django.core import cache

import coffin
import coffin.template

from askbot import models
from askbot.utils.slug import slugify
from askbot.deployment import package_utils
from askbot.tests.utils import AskbotTestCase
from askbot.conf import settings as askbot_settings
from askbot.tests.utils import skipIf



def patch_jinja2():
    from jinja2 import Template
    ORIG_JINJA2_RENDERER = Template.render

    def instrumented_render(template_object, *args, **kwargs):
        context = dict(*args, **kwargs)
        signals.template_rendered.send(
                                sender=template_object,
                                template=template_object,
                                context=context
                            )
        return ORIG_JINJA2_RENDERER(template_object, *args, **kwargs)
    Template.render = instrumented_render

(CMAJOR, CMINOR, CMICRO) = package_utils.get_coffin_version()
if CMAJOR == 0 and CMINOR == 3 and CMICRO < 4:
    patch_jinja2()


class PageLoadTestCase(AskbotTestCase):

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
        management.call_command('askbot_add_test_content', verbosity=0, interactive=False)

    @classmethod
    def tearDownClass(self):
        management.call_command('flush', verbosity=0, interactive=False)

    def _fixture_setup(self):
        pass

    def _fixture_teardown(self):
        pass

    #############################################

    def setUp(self):
        self.old_cache = cache.cache
        cache.cache = DummyCache('', {})  # Disable caching (to not interfere with production cache, not sure if that's possible but let's not risk it)

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
            url_info += '?' + '&'.join(['%s=%s' % (k, v) for k, v in data.iteritems()])
        print url_info

        # if redirect expected, but we wont' follow
        if status_code == 302 and follow:
            response = self.client.get(url, data=data)
            self.assertTrue(settings.LOGIN_URL in response['Location'])
            return

        r = self.client.get(url, data=data, follow=follow)
        if hasattr(self.client, 'redirect_chain'):
            print 'redirect chain: %s' % ','.join(self.client.redirect_chain)

        self.assertEqual(r.status_code, status_code)

        if template and status_code != 302:
            if isinstance(r.template, coffin.template.Template):
                self.assertEqual(r.template.name, template)
            elif isinstance(r.template, list):
                #asuming that there is more than one template
                template_names = ','.join([t.name for t in r.template])
                print 'templates are %s' % template_names
                # The following code is no longer relevant because we're using
                # additional templates for cached fragments [e.g. thread.get_summary_html()]
#                if follow == False:
#                    self.fail(
#                        ('Have issue accessing %s. '
#                        'This should not have happened, '
#                        'since you are not expecting a redirect '
#                        'i.e. follow == False, there should be only '
#                        'one template') % url
#                    )
#
#               self.assertEqual(r.template[0].name, template)
                self.assertIn(template, [t.name for t in r.template])
            else:
                raise Exception('unexpected error while runnig test')


    def test_index(self):
        #todo: merge this with all reader url tests
        response = self.client.get(reverse('index'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.failUnless(len(response.redirect_chain) == 1)
        self.failUnless(response.redirect_chain[0][0].endswith('/questions/'))
        self.assertTrue(isinstance(response.template, list))
        self.assertIn('main_page.html', [t.name for t in response.template])

    def proto_test_ask_page(self, allow_anonymous, status_code):
        prev_setting = askbot_settings.ALLOW_POSTING_BEFORE_LOGGING_IN
        askbot_settings.update('ALLOW_POSTING_BEFORE_LOGGING_IN', allow_anonymous)
        self.try_url(
            'ask',
            status_code = status_code,
            template = 'ask.html'
        )
        askbot_settings.update('ALLOW_POSTING_BEFORE_LOGGING_IN', prev_setting)

    def test_ask_page_allowed_anonymous(self):
        self.proto_test_ask_page(True, 200)

    def test_ask_page_disallowed_anonymous(self):
        self.proto_test_ask_page(False, 302)

    def proto_test_non_user_urls(self, status_code):
        """test all reader views thoroughly
        on non-crashiness (no correcteness tests here)
        """

        self.try_url('sitemap')
        self.try_url(
                'feeds',
                status_code=status_code,
                kwargs={'url':'rss'})
        self.try_url(
                'feeds',
                kwargs={'url':'rss'},
                data={'tags':'one-tag'},
                status_code=status_code)
        #self.try_url(
        #        'feeds',
        #        kwargs={'url':'question'},
        #        status_code=status_code)
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
                template='tags.html')
        self.try_url(
                'tags',
                status_code=status_code,
                data={'sort':'name'}, template='tags.html')
        self.try_url(
                'tags',
                status_code=status_code,
                data={'sort':'used'}, template='tags.html')
        self.try_url(
                'badges',
                status_code=status_code,
                template='badges.html')
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
            template='main_page.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_scope('unanswered').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='main_page.html',
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_scope('favorite').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='main_page.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_scope('unanswered').change_sort('age-desc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='main_page.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_scope('unanswered').change_sort('age-asc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='main_page.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_scope('unanswered').change_sort('activity-desc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='main_page.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_scope('unanswered').change_sort('activity-asc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='main_page.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_sort('answers-desc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='main_page.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_sort('answers-asc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='main_page.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_sort('votes-desc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='main_page.html'
        )
        self.try_url(
            url_name=reverse('questions') + SearchState.get_empty().change_sort('votes-asc').query_string(),
            plain_url_passed=True,

            status_code=status_code,
            template='main_page.html'
        )

        self.try_url(
                'question',
                status_code=status_code,
                kwargs={'id':1},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
                follow=True,
                template='question.html'
            )
        self.try_url(
                'question',
                status_code=status_code,
                kwargs={'id':2},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
                follow=True,
                template='question.html'
            )
        self.try_url(
                'question',
                status_code=status_code,
                kwargs={'id':3},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
                follow=True,
                template='question.html'
            )
        self.try_url(
                'question_revisions',
                status_code=status_code,
                kwargs={'id':40},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
                template='revisions.html'
            )
        self.try_url('users',
                status_code=status_code,
                template='users.html'
            )
        self.try_url(
                'widget_questions',
                status_code = status_code,
                data={'tags': 'tag-1-0'},
                template='question_widget.html',
            )
        #todo: really odd naming conventions for sort methods
        self.try_url(
                'users',
                status_code=status_code,
                template='users.html',
                data={'sort':'reputation'},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users.html',
                data={'sort':'newest'},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users.html',
                data={'sort':'last'},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users.html',
                data={'sort':'user'},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users.html',
                data={'sort':'reputation', 'page':2},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users.html',
                data={'sort':'newest', 'page':2},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users.html',
                data={'sort':'last', 'page':2},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users.html',
                data={'sort':'user', 'page':2},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users.html',
                data={'sort':'reputation', 'page':1},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users.html',
                data={'sort':'newest', 'page':1},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users.html',
                data={'sort':'last', 'page':1},
            )
        self.try_url(
                'users',
                status_code=status_code,
                template='users.html',
                data={'sort':'user', 'page':1},
            )
        self.try_url(
                'edit_user',
                template='authopenid/signin.html',
                kwargs={'id':4},   # INFO: Hardcoded ID, might fail if DB allocates IDs in some non-continuous way
                status_code=status_code,
                follow=True,
            )
        self.try_url(
                'faq',
                template='faq_static.html',
                status_code=status_code,
            )

    def test_non_user_urls(self):
        self.proto_test_non_user_urls(status_code=200)

    @skipIf('askbot.middleware.forum_mode.ForumModeMiddleware' \
        not in settings.MIDDLEWARE_CLASSES,
        'no ForumModeMiddleware set')
    def test_non_user_urls_in_closed_forum_mode(self):
        askbot_settings.ASKBOT_CLOSED_FORUM_MODE = True
        self.proto_test_non_user_urls(status_code=302)
        askbot_settings.ASKBOT_CLOSED_FORUM_MODE = False

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
            template='user_profile/user_recent.html'
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
        not in settings.MIDDLEWARE_CLASSES,
        'no ForumModeMiddleware set')
    def test_user_urls_in_closed_forum_mode(self):
        askbot_settings.ASKBOT_CLOSED_FORUM_MODE = True
        self.proto_test_user_urls(status_code=302)
        askbot_settings.ASKBOT_CLOSED_FORUM_MODE = False


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
            template='user_profile/user_inbox.html',
        )


class AvatarTests(AskbotTestCase):

    def test_avatar_for_two_word_user_works(self):
        if 'avatar' in settings.INSTALLED_APPS:
            self.user = self.create_user('john doe')
            response = self.client.get(
                                'avatar_render_primary',
                                kwargs = {'user': 'john doe', 'size': 48}
                            )


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

    def test_bare_question(self):
        resp = self.client.get(self.q.get_absolute_url())
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.q, resp.context['question'])

        url = reverse('question', kwargs={'id': self.q.id})
        resp = self.client.get(url)
        url = url + self.q.slug
        self.assertRedirects(resp, expected_url=url)

        resp = self.client.get(url)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.q, resp.context['question'])

        url = reverse('question', kwargs={'id': 101})
        resp = self.client.get(url)
        url = reverse('question', kwargs={'id': self.q.id}) + self.q.slug  # redirect uses the new question.id !
        self.assertRedirects(resp, expected_url=url)

        url = reverse('question', kwargs={'id': 101}) + self.q.slug
        resp = self.client.get(url)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.q, resp.context['question'])

    def test_show_answer(self):
        resp = self.client.get(self.a.get_absolute_url())
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.q, resp.context['question'])
        self.assertEqual(self.a, resp.context['show_post'])

        url = reverse('question', kwargs={'id': self.q.id})
        resp = self.client.get(url, data={'answer': self.a.id})
        url = url + self.q.slug
        self.assertRedirects(resp, expected_url=url + '?answer=%d' % self.a.id)

        resp = self.client.get(url, data={'answer': self.a.id})
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.q, resp.context['question'])
        self.assertEqual(self.a, resp.context['show_post'])

        url = reverse('question', kwargs={'id': 101}) + self.q.slug
        resp = self.client.get(url, data={'answer': 201})
        self.assertRedirects(resp, expected_url=self.a.get_absolute_url())

    def test_show_comment(self):
        resp = self.client.get(self.c.get_absolute_url())
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.q, resp.context['question'])
        self.assertEqual(self.a, resp.context['show_post'])
        self.assertEqual(self.c, resp.context['show_comment'])

        url = reverse('question', kwargs={'id': self.q.id})
        resp = self.client.get(url, data={'comment': self.c.id})
        url = url + self.q.slug
        self.assertRedirects(resp, expected_url=url + '?comment=%d' % self.c.id)

        resp = self.client.get(url, data={'comment': self.c.id})
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.q, resp.context['question'])
        self.assertEqual(self.a, resp.context['show_post'])
        self.assertEqual(self.c, resp.context['show_comment'])

        url = reverse('question', kwargs={'id': 101}) + self.q.slug
        resp = self.client.get(url, data={'comment': 301})
        self.assertRedirects(resp, expected_url=self.c.get_absolute_url())
