from askbot.tests.utils import AskbotTestCase
from django.contrib.auth.models import User
from askbot import models
from askbot.conf import settings
from askbot.models.tag import format_personal_group_name

class UserModelTests(AskbotTestCase):
    """test user model"""

    def test_new_user_has_personal_group(self):
        user = User.objects.create_user('somebody', 'somebody@example.com')
        group_name = format_personal_group_name(user)
        group = models.Group.objects.filter(name=group_name)
        self.assertEqual(group.count(), 1)
        memberships = models.GroupMembership.objects.filter(
                                                group=group, user=user
                                            )
        self.assertEqual(memberships.count(), 1)

    def test_new_user_has_subscriptions(self):
        old_value = settings.SUBSCRIBED_TAG_SELECTOR_ENABLED
        old_group_value = settings.GROUPS_ENABLED
        settings.SUBSCRIBED_TAG_SELECTOR_ENABLED = True
        settings.GROUPS_ENABLED = True
        one_tag  = self.create_tag('one-tag')
        another_tag  = self.create_tag('another_tag')

        global_group =  models.Group.objects.get_global_group()

        the_boss = self.create_user('theboss')
        bulk_subscription = models.BulkTagSubscription.objects.create(
                                                tag_names=[one_tag.name, another_tag.name],
                                                group_list=[global_group],
                                                tag_author=the_boss,
                                                language_code='en'
                                            )

        user = self.create_user('someone')
        marked_tags = user.get_marked_tags('subscribed')
        self.assertTrue(one_tag in marked_tags)
        self.assertTrue(another_tag in marked_tags)
        settings.SUBSCRIBED_TAG_SELECTOR_ENABLED = old_value
        settings.GROUPS_ENABLED = old_group_value

    def test_delete_user(self):
        user = self.create_user('user')
        user.delete()
        self.assertRaises(User.DoesNotExist, User.objects.get, username='user')

    def test_rename_user(self):
        user = self.create_user('user')
        user.username = 'user2'
        user.save()
