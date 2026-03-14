from unittest import skip
from askbot.tests.utils import AskbotTestCase
from askbot.conf import settings as askbot_settings
from askbot import models
import django.core.mail
from django.urls import reverse

class ThreadModelTestsWithGroupsEnabled(AskbotTestCase):

    def setUp(self):
        self.groups_enabled_backup = askbot_settings.GROUPS_ENABLED
        askbot_settings.update('GROUPS_ENABLED', True)
        global_group = models.Group.objects.get_global_group()
        global_group.can_post_questions = True
        global_group.can_post_answers = True
        global_group.can_post_comments = True
        global_group.save()
        self.admin = self.create_user('admin', status = 'd')
        self.user = self.create_user(
            'user',
            notification_schedule = {
                'q_ask': 'i',
                'q_all': 'i',
                'q_ans': 'i',
                'q_sel': 'i',
                'm_and_c': 'i'
            }
        )
        self.user.new_response_count = 0
        self.user.seen_response_count = 0
        self.user.save()
        self.group = models.Group.objects.get_or_create(name='jockeys')[0]
        self.group.can_post_questions = True
        self.group.can_post_answers = True
        self.group.can_post_comments = True
        self.group.save()
        self.admin.join_group(self.group)

    def tearDown(self):
        askbot_settings.update('GROUPS_ENABLED', self.groups_enabled_backup)

    def test_private_answer(self):
        # post question, answer, add answer to the group
        self.question = self.post_question(self.user)

        self.answer = self.post_answer(user=self.admin,
                                       question=self.question,
                                       is_private=True)

        thread = self.question.thread

        #test answer counts
        self.assertEqual(thread.get_answer_count(self.user), 0)
        self.assertEqual(thread.get_answer_count(self.admin), 1)

        #test mail outbox
        self.assertEqual(len(django.core.mail.outbox), 0)
        user = self.reload_object(self.user)
        # error below
        self.assertEqual(user.new_response_count, 0)

        self.admin.edit_answer(self.answer, is_private=False)
        self.assertEqual(len(django.core.mail.outbox), 1)
        user = self.reload_object(self.user)
        self.assertEqual(user.new_response_count, 1)

    def test_answer_to_private_question_is_not_globally_visible(self):
        question = self.post_question(user=self.admin, is_private=True)
        answer = self.post_answer(question=question, user=self.admin, is_private=False)
        global_group = models.Group.objects.get_global_group()
        self.assertEqual(
            global_group in set(answer.groups.all()),
            False
        )

    def test_answer_to_group_question_is_not_globally_visible(self):
        #ask into group where user is not a member
        question = self.post_question(user=self.user, group_id=self.group.id)
        #answer posted by a group member
        answer = self.post_answer(question=question, user=self.admin, is_private=False)
        global_group = models.Group.objects.get_global_group()
        self.assertEqual(
            global_group in set(answer.groups.all()),
            False
        )


    def test_permissive_response_publishing(self):
        question = self.post_question(user=self.user, group_id=self.group.id)
        answer = self.post_answer(question=question, user=self.admin)

        #answer and user have one group in common
        answer_groups = set(answer.groups.all())
        user_groups = set(self.user.get_groups())
        self.assertEqual(len(answer_groups & user_groups), 1)
