from django.conf import settings as django_settings
from askbot.tests.utils import AskbotTestCase

if 'followit' in django_settings.INSTALLED_APPS:
    TEST_PROTOTYPE = AskbotTestCase
else:
    TEST_PROTOTYPE = object

class FollowUserTests(TEST_PROTOTYPE):

    def setUp(self):
        self.u1 = self.create_user('user1')
        self.u2 = self.create_user('user2')
        self.u3 = self.create_user('user3')

    def test_multiple_follow(self):

        self.u1.follow_user(self.u2)
        self.u1.follow_user(self.u3)
        self.u2.follow_user(self.u1)

        self.assertEquals(
            set(self.u1.get_followers()),
            set([self.u2])
        )

        self.assertEquals(
            set(self.u2.get_followers()),
            set([self.u1])
        )

        self.assertEquals(
            set(self.u1.get_followed_users()),
            set([self.u2, self.u3])
        )

    def test_unfollow(self):
        self.u1.follow_user(self.u2)
        self.u1.unfollow_user(self.u2)
        self.assertEquals(self.u1.get_followed_users().count(), 0)
