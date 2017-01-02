from django.core import management, mail
from django.contrib import auth
from askbot.tests.utils import AskbotTestCase
from askbot.tests.utils import with_settings
from askbot import (const, models)
from django.contrib.auth.models import User

class ManagementCommandTests(AskbotTestCase):
    def test_askbot_add_user(self):
        username = 'test user'
        password = 'secretno1'
        management.call_command(
                        'askbot_add_user',
                        email = 'test@askbot.org',
                        username = username,
                        frequency = 'd',
                        password = password
                     )
        #check that we have the user
        users = models.User.objects.filter(username=username)
        self.assertEquals(users.count(), 1)
        user = users[0]
        #check thath subscrptions are correct
        subs = models.EmailFeedSetting.objects.filter(
                                                subscriber = user,
                                            )
        self.assertEquals(subs.count(), 5)
        #try to log in
        user = auth.authenticate(username=username, password=password)
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
        user_one.receive_reputation(reputation)
        user_one.askbot_profile.save()
        user_one.save()
        # Create a second user and transfer all objects from 'user_one' to 'user_two'
        user_two = self.create_user(username='unique')
        user_two_pk = user_two.pk
        management.call_command('merge_users', str(user_one.id), str(user_two.id))
        # Check that the first user was deleted
        self.assertEqual(models.User.objects.filter(pk=user_one.id).count(), 0)
        # Explicitly check that the values assigned to user_one are now user_two's
        self.assertEqual(user_two.posts.get_questions().filter(pk=question.id).count(), 1)
        self.assertEqual(user_two.posts.get_comments().filter(pk=comment.id).count(), 1)
        user_two = models.User.objects.get(pk=user_two_pk)
        self.assertEqual(user_two.gold, number_of_gold)
        self.assertEqual(user_two.reputation, reputation + const.MIN_REPUTATION)

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

    def test_delete_unused_tags(self):

        user = self.create_user()
        question = self.post_question(user=user)

        tag_count = models.Tag.objects.count()

        #create some unused tags
        self.create_tag("picasso", user)
        self.create_tag("renoir", user)
        self.create_tag("pissarro", user)

        #check they're in the db
        self.assertEqual(models.Tag.objects.count(), tag_count+3)
        management.call_command('delete_unused_tags')

        #now they should be removed
        self.assertEqual(models.Tag.objects.count(), tag_count)

    @with_settings(CONTENT_MODERATION_MODE='premoderation')
    def test_askbot_send_moderation_alerts(self):
        mod1 = self.create_user('mod1', status='m')
        mod2 = self.create_user('mod2', status='m')
        mod3 = self.create_user('mod3', status='m')
        mod4 = self.create_user('mod4', status='m')
        mod5 = self.create_user('mod5', status='m')
        mod6 = self.create_user('mod6', status='m')
        usr = self.create_user('usr', status='w')
        self.post_question(user=usr)
        mail.outbox = list()
        management.call_command('askbot_send_moderation_alerts')
        #command sends alerts to three moderators at a time
        self.assertEqual(len(mail.outbox), 3)
        self.assertTrue('moderation' in mail.outbox[0].subject)
