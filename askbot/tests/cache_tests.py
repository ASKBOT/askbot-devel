from django.db import connection
from django.core.urlresolvers import reverse
from django.conf import settings
from askbot.tests.utils import AskbotTestCase


class CacheTests(AskbotTestCase):
    def setUp(self):
        user = self.create_user('other_user')
        self.question = self.post_question(user=user)
        self.post_answer(user=user, question=self.question)
        settings.DEBUG = True  # because it's forsed to False

    def tearDown(self):
        settings.DEBUG = False

    def visit_question(self):
        self.client.get(self.question.get_absolute_url(), follow=True)

    def test_anonymous_question_cache(self):

        self.visit_question()
        before_count = len(connection.queries)
        self.visit_question()
        #second hit to the same question should give fewer queries
        after_count = len(connection.queries)
        self.assertTrue(before_count > after_count,
                ('Expected fewer queries after calling visit_question. ' +
                 'Before visit: %d. After visit: %d.') % (before_count, after_count))
