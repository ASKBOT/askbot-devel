from askbot.tests.utils import AskbotTestCase
from askbot.models.post import PostRevision

class MiscTests(AskbotTestCase):

    def setUp(self):
        self.u1 = self.create_user(username='user1')
        self.u2 = self.create_user(username='user2')
        self.u3 = self.create_user(username='user3')

    def test_proper_PostRevision_manager_is_used(self):
        "Makes sure that both normal and related managers for PostRevision don't implement .create() method"
        question = self.post_question(user=self.u1)
        self.assertRaises(NotImplementedError, question.revisions.create)
        self.assertRaises(NotImplementedError, PostRevision.objects.create)
