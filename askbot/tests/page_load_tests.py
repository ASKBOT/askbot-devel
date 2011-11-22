from django.test import TestCase
from django.test import signals
from django.template import defaultfilters
from django.conf import settings
from django.core.urlresolvers import reverse
import coffin
import coffin.template
from askbot import models
from askbot.utils.slug import slugify
from askbot.deployment import package_utils
from askbot.tests.utils import AskbotTestCase
from askbot.conf import settings as askbot_settings
from askbot.tests.utils import skipIf
import sys


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
    import ipdb; ipdb.set_trace()
    patch_jinja2()


class PageLoadTestCase(AskbotTestCase):
    def try_url(
            self,
            url_name, status_code=200, template=None,
            kwargs={}, redirect_url=None, follow=False,
            data={}):
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
                if follow == False:
                    self.fail(
                        ('Have issue accessing %s. '
                        'This should not have happened, '
                        'since you are not expecting a redirect '
                        'i.e. follow == False, there should be only '
                        'one template') % url
                    )

                self.assertEqual(r.template[0].name, template)
            else:
                raise Exception('unexpected error while runnig test')

    def setUp(self):
        self.u1 = self.create_user(username='user1')
        self.u2 = self.create_user(username='user2')
        self.u3 = self.create_user(username='user3')

        self.question = self.post_question(user=self.u1)

        self.answer = self.post_answer(user=self.u1, question=self.question)
        self.answer.id = 38 # one of the tests tries this id
        self.answer.save()

        self.question2 = self.post_question(user=self.u2)
        self.question2.id = 2
        self.question2.save()

        self.question3 = self.post_question(user=self.u3)
        self.question3.id = 3
        self.question3.save()

        self.question17 = self.post_question(user=self.u1)
        self.question17.id = 17
        self.question17.save()


    def test_index(self):
        #todo: merge this with all reader url tests
        response = self.client.get(reverse('index'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.failUnless(len(response.redirect_chain) == 1)
        self.failUnless(response.redirect_chain[0][0].endswith('/questions/'))
        self.assertEquals(response.template.name, 'main_page.html')

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
                'about',
                status_code=status_code,
                template='about.html')
        self.try_url(
                'privacy',
                status_code=status_code,
                template='privacy.html')
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
                kwargs={'id':38}
            )
        #todo: test different sort methods and scopes
        self.try_url(
                'questions',
                status_code=status_code,
                template='main_page.html'
            )
        self.try_url(
                'questions',
                status_code=status_code,
                data={'start_over':'true'},
                template='main_page.html'
            )
        self.try_url(
                'questions',
                status_code=status_code,
                data={'scope':'unanswered'},
                template='main_page.html'
            )
        self.try_url(
                'questions',
                status_code=status_code,
                data={'scope':'favorite'},
                template='main_page.html'
            )
        self.try_url(
                'questions',
                status_code=status_code,
                data={'scope':'unanswered', 'sort':'age-desc'},
                template='main_page.html'
            )
        self.try_url(
                'questions',
                status_code=status_code,
                data={'scope':'unanswered', 'sort':'age-asc'},
                template='main_page.html'
            )
        self.try_url(
                'questions',
                status_code=status_code,
                data={'scope':'unanswered', 'sort':'activity-desc'},
                template='main_page.html'
            )
        self.try_url(
                'questions',
                status_code=status_code,
                data={'scope':'unanswered', 'sort':'activity-asc'},
                template='main_page.html'
            )
        self.try_url(
                'questions',
                status_code=status_code,
                data={'sort':'answers-desc'},
                template='main_page.html'
            )
        self.try_url(
                'questions',
                status_code=status_code,
                data={'sort':'answers-asc'},
                template='main_page.html'
            )
        self.try_url(
                'questions',
                status_code=status_code,
                data={'sort':'votes-desc'},
                template='main_page.html'
            )
        self.try_url(
                'questions',
                status_code=status_code,
                data={'sort':'votes-asc'},
                template='main_page.html'
            )
        self.try_url(
                'question',
                status_code=status_code,
                kwargs={'id':1},
                follow=True,
                template='question.html'
            )
        self.try_url(
                'question',
                status_code=status_code,
                kwargs={'id':2},
                follow=True,
                template='question.html'
            )
        self.try_url(
                'question',
                status_code=status_code,
                kwargs={'id':3},
                follow=True,
                template='question.html'
            )
        self.try_url(
                'question_revisions',
                status_code=status_code,
                kwargs={'id':17},
                template='revisions.html'
            )
        self.try_url('users',
                status_code=status_code,
                template='users.html')
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
                kwargs={'id':4},
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
        user = models.User.objects.get(id=2)
        name_slug = slugify(user.username)
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},
            status_code=status_code,
            data={'sort':'stats'},
            template='user_profile/user_stats.html'
        )
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},
            status_code=status_code,
            data={'sort':'recent'},
            template='user_profile/user_recent.html'
        )
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},
            status_code=status_code,
            data={'sort':'inbox'},
            template='authopenid/signin.html',
            follow=True
        )
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},
            status_code=status_code,
            data={'sort':'reputation'},
            template='user_profile/user_reputation.html'
        )
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},
            status_code=status_code,
            data={'sort':'votes'},
            template='authopenid/signin.html',
            follow = True
        )
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},
            status_code=status_code,
            data={'sort':'favorites'},
            template='user_profile/user_favorites.html'
        )
        self.try_url(
            'user_profile',
            kwargs={'id': 2, 'slug': name_slug},
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
        user = models.User.objects.get(id=2)
        name_slug = slugify(user.username)
        #works only with builtin django_authopenid
        self.client.login(method = 'force', user_id = 2)
        self.try_url(
            'user_subscriptions',
            kwargs = {'id': 2, 'slug': name_slug},
            template = 'user_profile/user_email_subscriptions.html'
        )
        self.client.logout()

    def test_inbox_page(self):
        asker = models.User.objects.get(id = 2)
        question = asker.post_question(
            title = 'How can this happen?',
            body_text = 'This is the body of my question',
            tags = 'question answer test',
        )
        responder = models.User.objects.get(id = 3)
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
        self.user = self.create_user('john doe')
        response = self.client.get(
                            'avatar_render_primary',
                            kwargs = {'user': 'john doe', 'size': 48}
                        )
