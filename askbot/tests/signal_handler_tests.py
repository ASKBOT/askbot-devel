from askbot.tests.utils import AskbotTestCase
from askbot import models
from datetime import datetime
from datetime import timedelta

class SignalHandlerTests(AskbotTestCase):

    def setUp(self):
        self.user = self.create_user('user1')

    def test_record_user_visit(self):
        today = datetime.now()
        self.user.last_seen = today
        self.user.save()
        self.assertEqual(self.user.consecutive_days_visit_count, 0)
        tomorrow = today + timedelta(1)
        models.record_user_visit(self.user, tomorrow)
        user = self.reload_object(self.user)
        self.assertEqual(user.consecutive_days_visit_count, 1)
