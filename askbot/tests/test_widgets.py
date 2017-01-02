from askbot import models
from askbot.tests.utils import AskbotTestCase

from django.test.client import Client
from django.conf import settings as django_settings
from django.core.urlresolvers import reverse
from django.utils import translation, timezone


class WidgetViewsTests(AskbotTestCase):

    def setUp(self):
        translation.activate(django_settings.LANGUAGE_CODE)
        self.client = Client()
        self.widget = models.AskWidget.objects.create(title='foo widget')
        self.user = self.create_user('user1')
        self.user.set_password('sample')
        self.user.save()
        self.good_data = {'title': 'This is a title question',
                          'ask_anonymously': False}

    def test_post_with_auth(self):
        self.client.login(username='user1', password='sample')
        response = self.client.post(reverse('ask_by_widget', args=(self.widget.id, )), self.good_data)
        self.assertEquals(response.status_code, 302)
        self.client.logout()

    def test_post_without_auth(self):
        #weird issue
        response = self.client.post(reverse('ask_by_widget', args=(self.widget.id, )), self.good_data)
        self.assertEquals(response.status_code, 302)
        self.assertTrue('widget_question' in self.client.session)
        self.assertEquals(self.client.session['widget_question']['title'],
                          self.good_data['title'])

    def test_post_after_login(self):
        widget_question_data = { 'title': 'testing post after login, does it?',
                                 'author': self.user,
                                 'added_at': timezone.now(),
                                 'wiki': False,
                                 'text': ' ',
                                 'tagnames': '',
                                 'is_anonymous': False
                               }

        self.client.login(username='user1', password='sample')

        session = self.client.session
        session['widget_question'] = widget_question_data
        session.save()
        response = self.client.get(
            reverse('ask_by_widget', args=(self.widget.id, )),
            {'action': 'post-after-login'}
        )
        self.assertFalse('widget_question' in self.client.session)
        self.assertEquals(response.status_code, 302)
        #verify posting question

    def test_render_widget_view(self):
        response = self.client.get(reverse('render_ask_widget', args=(self.widget.id, )))
        self.assertEquals(200, response.status_code)
        content_type = 'text/javascript'
        self.assertTrue(content_type in response['Content-Type'])


class WidgetLoginViewTest(AskbotTestCase):

    def test_correct_template_loading(self):
        client = Client()
        response = client.get(reverse('widget_signin'))
        template_name = 'authopenid/widget_signin.html'
        templates = [template.name for template in response.templates]
        self.assertTrue(template_name in templates)

class WidgetCreatorViewsTests(AskbotTestCase):

    def setUp(self):
        translation.activate(django_settings.LANGUAGE_CODE)
        self.client = Client()
        self.user = self.create_user('user1')
        self.user.set_password('testpass')
        self.user.set_admin_status()
        self.user.save()
        self.widget = models.AskWidget.objects.create(title='foo widget')

    def test_list_ask_widget_view(self):
        self.client.login(username='user1', password='testpass')
        response = self.client.get(reverse('list_widgets', args=('ask',)))
        self.assertEquals(response.status_code, 200)
        self.assertTrue('widgets' in response.context)

    def test_create_ask_widget_get(self):
        self.client.login(username='user1', password='testpass')
        response = self.client.get(reverse('create_widget', args=('ask',)))
        self.assertEquals(response.status_code, 200)
        self.assertTrue('form' in response.context)

    def test_create_ask_widget_post(self):
        self.client.login(username='user1', password='testpass')
        post_data = {'title': 'Test widget'}
        response = self.client.post(reverse('create_widget', args=('ask',)), post_data)
        self.assertEquals(response.status_code, 302)

    def test_edit_ask_widget_get(self):
        self.client.login(username='user1', password='testpass')
        response = self.client.get(reverse('edit_widget',
            args=('ask', self.widget.id, )))
        self.assertEquals(response.status_code, 200)
        self.assertTrue('form' in response.context)

    def test_edit_ask_widget_post(self):
        self.client.login(username='user1', password='testpass')
        post_data = {'title': 'Test lalalla'}
        response = self.client.post(reverse('edit_widget',
            args=('ask', self.widget.id, )), post_data)
        self.assertEquals(response.status_code, 302)

    def test_delete_ask_widget_get(self):
        self.client.login(username='user1', password='testpass')
        response = self.client.get(reverse('delete_widget',
            args=('ask', self.widget.id, )))
        self.assertEquals(response.status_code, 200)
        self.assertTrue('widget' in response.context)

    def test_delete_ask_widget_post(self):
        self.client.login(username='user1', password='testpass')
        response = self.client.post(reverse('delete_widget',
            args=('ask', self.widget.id, )))
        self.assertEquals(response.status_code, 302)

    #this test complains about 404.html template but it's correct
    #def test_bad_url(self):
    #    self.client.login(username='user1', password='testpass')
    #    response = self.client.get('/widgets/foo/create/')
    #    self.assertEquals(404, response.status_code)


class QuestionWidgetViewsTests(AskbotTestCase):

    def setUp(self):
        translation.activate(django_settings.LANGUAGE_CODE)
        self.user = self.create_user('testuser')
        self.client = Client()
        self.widget =  models.QuestionWidget.objects.create(title="foo",
                                   question_number=5, search_query='test',
                                   tagnames='test')

        #we post 6 questions!
        titles = (
            'test question 1', 'this is a test',
            'without the magic word', 'test test test',
            'test just another test', 'no magic word',
            'test another', 'I can no believe is a test'
        )

        tagnames = 'test foo bar'
        for title in titles:
            self.post_question(title=title, tags=tagnames)

    def test_valid_response(self):
        filter_params = {
            'title__icontains': self.widget.search_query,
            'tags__name__in': self.widget.tagnames.split(' ')
        }

        threads = models.Thread.objects.filter(**filter_params)[:5]

        response = self.client.get(reverse('question_widget', args=(self.widget.id, )))
        self.assertEquals(200, response.status_code)

        self.assertQuerysetEqual(threads, response.context['threads'])
        self.assertEquals(self.widget, response.context['widget'])
