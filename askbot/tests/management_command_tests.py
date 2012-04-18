from django.core import management
from django.contrib import auth
from askbot.tests.utils import AskbotTestCase
from askbot import models

class ManagementCommandTests(AskbotTestCase):
    def test_add_askbot_user(self):
        username = 'test user'
        password = 'secretno1'
        management.call_command(
                        'add_askbot_user',
                        email = 'test@askbot.org',
                        username = username,
                        frequency = 'd',
                        password = password
                     )
        #check that we have the user
        users = models.User.objects.filter(username = username)
        self.assertEquals(users.count(), 1)
        user = users[0]
        #check thath subscrptions are correct
        subs = models.EmailFeedSetting.objects.filter(
                                                subscriber = user,
                                            )
        self.assertEquals(subs.count(), 5)
        #try to log in
        user = auth.authenticate(username = username, password = password)
        self.assertTrue(user is not None)

    def test_merge_users(self):
        """Verify a users account can be transfered to another user"""
        # Create a new user and add some random related objects
        user_one = self.create_user()
        question = self.post_question(user=user_one)
        comment = self.post_comment(user=user_one, parent_post=question)
        number_of_gold = 50
        user_one.gold = number_of_gold 
        reputation = 20
        user_one.reputation = reputation 
        user_one.save()
        # Create a second user and transfer all objects from 'user_one' to 'user_two'
        user_two = self.create_user(username='unique')
        management.call_command('merge_users', user_one.id, user_two.id)
        # Check that the first user was deleted
        self.assertEqual(models.User.objects.filter(pk=user_one.id).count(), 0)
        # Explicitly check that the values assigned to user_one are now user_two's
        self.assertEqual(user_two.questions.filter(pk=question.id).count(), 1)  
        self.assertEqual(user_two.comments.filter(pk=comment.id).count(), 1)  
        user_two = models.User.objects.get(pk=2)
        self.assertEqual(user_two.gold, number_of_gold) 
        self.assertEqual(user_two.reputation, reputation)
