from django.db import connection
from django.core.urlresolvers import reverse
from django.conf import settings
from askbot.tests.utils import AskbotTestCase

class CacheTests(AskbotTestCase):
    def setUp(self):
        self.create_user()
        self.create_user('other_user')
        self.question = self.post_question()
        self.post_answer(question = self.question)
        settings.DEBUG = True  # because it's forsed to False

    def visit_question(self):
        self.client.get(self.question.get_absolute_url(), follow=True)
        
    def test_anonymous_question_cache(self):

        self.visit_question()
        counter = len(connection.queries)
        print 'we have %d queries' % counter
        self.visit_question()

        #second hit to the same question should give fewer queries
        self.assertTrue(counter > len(connection.queries))
        settings.DEBUG = False

    def test_authentificated_no_question_cache(self):
        url = reverse('question', kwargs={'id': self.question.id})

        password = '123'
        self.other_user.set_password(password)
        self.client.login(username=self.other_user.username, password=password)

        self.visit_question()
        counter = len(connection.queries)
        self.visit_question()

        #expect the same number of queries both times
        self.assertEqual(counter, len(connection.queries))
        settings.DEBUG = False


