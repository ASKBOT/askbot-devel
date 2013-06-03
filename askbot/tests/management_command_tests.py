from django.core import management
from django.contrib import auth
from askbot.tests.utils import AskbotTestCase
from askbot import models
from django.contrib.auth.models import User

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
        user_two_pk = user_two.pk
        management.call_command('merge_users', user_one.id, user_two.id)
        # Check that the first user was deleted
        self.assertEqual(models.User.objects.filter(pk=user_one.id).count(), 0)
        # Explicitly check that the values assigned to user_one are now user_two's
        self.assertEqual(user_two.posts.get_questions().filter(pk=question.id).count(), 1)
        self.assertEqual(user_two.posts.get_comments().filter(pk=comment.id).count(), 1)
        user_two = models.User.objects.get(pk=user_two_pk)
        self.assertEqual(user_two.gold, number_of_gold)
        self.assertEqual(user_two.reputation, reputation)

    def test_create_tag_synonym(self):

        admin = User.objects.create_superuser('test_admin', 'admin@admin.com', 'admin_pass')

        options = {
            'from': 'tag1',     # ok.. 'from' is a bad keyword argument name..
            'to': 'tag2',
            'user_id': admin.id,
            'is_force': True
            }
        management.call_command(
            'create_tag_synonyms',
            **options
            )

        options['from'] = 'tag3'
        options['to'] = 'tag4'
        management.call_command(
            'create_tag_synonyms',
            **options
            )

        options['from']='tag5'
        options['to']='tag4'
        management.call_command(
            'create_tag_synonyms',
            **options
            )

        options['from']='tag2'
        options['to']='tag3'
        management.call_command(
            'create_tag_synonyms',
            **options
            )

        self.assertEqual(models.TagSynonym.objects.filter(source_tag_name = 'tag1',
                                                          target_tag_name = 'tag4'
                                                          ).count(), 1)
        self.assertEqual(models.TagSynonym.objects.filter(source_tag_name = 'tag2',
                                                          target_tag_name = 'tag4'
                                                          ).count(), 1)
        self.assertEqual(models.TagSynonym.objects.filter(source_tag_name = 'tag3',
                                                          target_tag_name = 'tag4'
                                                          ).count(), 1)
        self.assertEqual(models.TagSynonym.objects.filter(source_tag_name = 'tag5',
                                                          target_tag_name = 'tag4'
                                                          ).count(), 1)
        self.assertEqual(models.TagSynonym.objects.count(), 4)

        options['from']='tag4'
        options['to']='tag6'
        management.call_command(
            'create_tag_synonyms',
            **options
            )

        self.assertEqual(models.TagSynonym.objects.filter(source_tag_name = 'tag1',
                                                          target_tag_name = 'tag6'
                                                          ).count(), 1)
        self.assertEqual(models.TagSynonym.objects.filter(source_tag_name = 'tag2',
                                                          target_tag_name = 'tag6'
                                                          ).count(), 1)
        self.assertEqual(models.TagSynonym.objects.filter(source_tag_name = 'tag3',
                                                          target_tag_name = 'tag6'
                                                          ).count(), 1)
        self.assertEqual(models.TagSynonym.objects.filter(source_tag_name = 'tag4',
                                                          target_tag_name = 'tag6'
                                                          ).count(), 1)
        self.assertEqual(models.TagSynonym.objects.filter(source_tag_name = 'tag5',
                                                          target_tag_name = 'tag6'
                                                          ).count(), 1)
        self.assertEqual(models.TagSynonym.objects.count(), 5)

        print 'done create_tag_synonym_test'
        
