
from datetime import date
import json
import os
import sys
import io
import shutil
import unittest
from unittest.mock import patch, MagicMock, mock_open
import zipfile
import askbot
from django.core import management, mail
from django.conf import settings as django_settings
from django.contrib import auth
from django.contrib.auth.models import User, Group as AuthGroup
from askbot.utils.html import site_url
from askbot.utils.url_utils import reload_urlconf
from askbot.tests.utils import AskbotTestCase
from askbot.tests.utils import with_settings
from askbot import (const, models)
from askbot import models
from askbot.models import LocalizedUserProfile, UserProfile

class ExportUserDataTests(AskbotTestCase):

    def setUp(self):
        self.prev_lang = django_settings.LANGUAGE_CODE
        self.prev_lang_mode = django_settings.ASKBOT_LANGUAGE_MODE
        self.prev_langs = django_settings.LANGUAGES
        django_settings.LANGUAGE_CODE = 'en'
        django_settings.ASKBOT_LANGUAGE_MODE = 'url-lang'
        django_settings.LANGUAGES = (('en', 'English'), ('es', 'Spanish'))
        media_root = django_settings.MEDIA_ROOT
        if not os.path.isdir(media_root):
            os.makedirs(media_root)
        reload_urlconf()

    def tearDown(self):
        #translation.activate(self.prev_lang)
        django_settings.LANGUAGE_CODE = self.prev_lang
        django_settings.LANGUAGES = self.prev_langs
        django_settings.ASKBOT_LANGUAGE_MODE = self.prev_lang_mode
        media_root = django_settings.MEDIA_ROOT
        # IMPORTANT: commented out below to not break the production files by accident
        # it would be better to create a temp test directory and then
        # delete it entirely
        #if os.path.isdir(media_root):
        #    shutil.rmtree(media_root)
        reload_urlconf()

    @classmethod
    def put_upfile(cls, file_name):
        """Creates a test upfile with contents
        being the file name.
        Returns file path."""
        media_root = django_settings.MEDIA_ROOT
        try:
            os.makedirs(media_root)
        except FileExistsError:
            pass
        path = os.path.join(media_root, file_name)
        with open(path, 'w') as file_obj:
            file_obj.write(file_name)
        return path

    @classmethod
    def get_upfile_url_from_path(cls, path):
        #pylint: disable=missing-docstring
        file_name = os.path.basename(path)
        media_url = django_settings.MEDIA_URL
        return os.path.join(media_url, file_name)

    def test_extract_upfile_paths_from_text(self):
        from askbot.management.commands.askbot_export_user_data import Command
        prefix = django_settings.MEDIA_URL
        path = os.path.join(prefix, 'somefile')
        expected = [path + str(i) + '.jpg' for i in range(1,6)]
        text = f"hello {path}1.jpg) blabla <img src=\"{path}2.jpg\" />\
        <img src='{path}3.jpg' /> :{path}4.jpg {path}5.jpg"

        paths = Command.extract_upfile_paths_from_text(text)
        self.assertEqual(len(paths), 5)
        #expected = ('/upfiles/somefile1.jpg',
        #            '/upfiles/somefile2.jpg',
        #            '/upfiles/somefile3.jpg',
        #            '/upfiles/somefile4.jpg',
        #            '/upfiles/somefile5.jpg')

        self.assertEqual(set(paths), set(expected))

    def test_upfile_is_on_disk(self):
        from askbot.management.commands.askbot_export_user_data import Command
        path = self.put_upfile('somefile.jpg')
        url = self.get_upfile_url_from_path(path)
        is_on_disk = Command.upfile_is_on_disk(url)
        self.assertEqual(is_on_disk, True)
        os.remove(path)

    def test_command(self):
        # create user
        today = date.today()
        # create user & fill out profile
        user = User.objects.create(username='bob',
                                   email='bob@example.com')
        profile = UserProfile(auth_user_ptr=user, date_of_birth=today)
        profile.save()

        lang1 = 'en'
        lang2 = 'es'
        localized_profile1 = LocalizedUserProfile(auth_user=user,
                                                  language_code=lang1,
                                                  about='about me')
        localized_profile1.save()
        localized_profile2 = LocalizedUserProfile(auth_user=user,
                                                  language_code=lang2,
                                                  about='sobre mi')
        localized_profile2.save()

        # put three upfiles in place
        paths = list()
        for idx in range(1, 4):
            path = self.put_upfile('file{}.txt'.format(idx))
            paths.append(path)

        # post question with an image
        text_tpl ='hello there ![image]({} "Image {}")'
        url = self.get_upfile_url_from_path(paths[0])
        question_text = text_tpl.format(url, 1)
        question = user.post_question(title='question',
                                      body_text=question_text,
                                      tags='one two')

        # post answer with an image
        url = self.get_upfile_url_from_path(paths[1])
        answer_text = text_tpl.format(url, 2)
        answer = user.post_answer(question, answer_text)

        # post comment with an image
        url = self.get_upfile_url_from_path(paths[2])
        comment_text = text_tpl.format(url, 3)
        comment = user.post_comment(answer, comment_text)

        # run extract data command into a temp dir
        askbot_dir = askbot.get_install_directory()
        test_dir = os.path.join(askbot_dir, 'tests',
                                'temp_export_user_data')

        if os.path.isdir(test_dir):
            shutil.rmtree(test_dir)
        os.makedirs(test_dir)

        backup_file = os.path.join(test_dir, 'backup.zip')
        management.call_command('askbot_export_user_data',
                     user_id=user.pk, file_name=backup_file)
        # test: unzip the file
        zip_file = zipfile.ZipFile(backup_file, 'r')
        extract_dir = os.path.join(test_dir, 'extracted')
        zip_file.extractall(extract_dir)

        json_file = os.path.join(extract_dir, 'data.json')
        self.assertTrue(os.path.isfile(json_file))

        # test: load json
        with open(json_file) as f:
            json_data = json.loads(f.read())
        # test: validate question
        q_data = json_data['questions'][0]
        thread = question.thread
        self.assertEqual(q_data['title'], thread.title)
        self.assertEqual(q_data['tags'], thread.tagnames)
        self.assertEqual(q_data['text'], question.text)
        self.assertEqual(q_data['added_at'], str(question.added_at))
        self.assertEqual(q_data['last_edited_at'],
                         str(question.last_edited_at))
        question_url = site_url(question.get_absolute_url())
        self.assertEqual(q_data['url'], question_url)

        # test: validate answer, just check it's there
        self.assertEqual(len(json_data['answers']), 1)
        # test: validate comment
        self.assertEqual(len(json_data['comments']), 1)

        # test: validate user profile data
        user_data = json_data['user_profile']
        self.assertEqual(user_data['username'], user.username)
        lang_data = user_data['localized_profiles']

        profile_url_tpl = site_url('/{}/users/{}/bob/')
        self.assertEqual(lang_data[lang1]['about'], 'about me')
        lang1_url = profile_url_tpl.format('en', user.pk)
        self.assertEqual(lang_data[lang1]['profile_url'], lang1_url)
        self.assertEqual(lang_data[lang2]['about'], 'sobre mi')
        lang2_url = profile_url_tpl.format('es', user.pk)
        self.assertEqual(lang_data[lang2]['profile_url'], lang2_url)

        self.assertEqual(user_data['email'], user.email)
        self.assertEqual(user_data['date_of_birth'], str(today))

        # test: verify that uploaded files are there
        upfile_names = [os.path.basename(path) for path in paths]
        for name in upfile_names:
            extracted_path = os.path.join(extract_dir, 'upfiles', name)
            self.assertTrue(os.path.isfile(extracted_path))

        shutil.rmtree(test_dir)

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
        self.assertEqual(users.count(), 1)
        user = users[0]
        #check thath subscrptions are correct
        subs = models.EmailFeedSetting.objects.filter(
                                                subscriber = user,
                                            )
        self.assertEquals(subs.count(), 6)
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

        admin = self.create_user(username='test_admin', email='admin@admin.com', status='d')
        options = {
            'from': 'tag1',     # ok.. 'from' is a bad keyword argument name..
            'to': 'tag2',
            'user_id': admin.id,
            'is_force': True
            }

        with patch('sys.stdout', new_callable=io.StringIO):
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
        with patch('sys.stdout', new_callable=io.StringIO):
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

        # print('done create_tag_synonym_test')

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

        # with patch('builtins.print', new=MagicMock()):
        with patch('sys.stdout', new_callable=io.StringIO):
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

    @with_settings(INVITED_MODERATORS='one@site.com Joe\ntwo@site.com Ben',
                   CONTENT_MODERATION_MODE='premoderation')
    def test_askbot_send_moderation_alerts1(self):
        usr = self.create_user('usr', status='w')
        self.post_question(user=usr)
        mail.outbox = list()
        management.call_command('askbot_send_moderation_alerts')
        #command sends alerts to three moderators at a time
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue('moderation' in mail.outbox[0].subject)


    def test_askbot_create_per_email_domain_groups(self):
        user1 = self.create_user('org1', 'user@org1.com')
        user2 = self.create_user('org2', 'user@org2.com')
        count = models.Group.objects.filter(name__in=('Org1', 'Org2')).count()
        self.assertEqual(count, 0)
        management.call_command('askbot_create_per_email_domain_groups')
        count = models.Group.objects.filter(name__in=('Org1', 'Org2')).count()
        self.assertEqual(count, 2)
        self.assertEqual(AuthGroup.objects.filter(name='Org1').count(), 1)
        self.assertEqual(AuthGroup.objects.filter(name='Org2').count(), 1)


