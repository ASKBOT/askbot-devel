import datetime
from django.contrib.contenttypes.models import ContentType
from django.test.client import Client
from askbot.tests.utils import AskbotTestCase
from askbot.conf import settings
from askbot import models
from askbot.models.badges import award_badges_signal

from askbot.views.users import get_related_object_type_name
from askbot.models.post import PostRevision

class MiscTests(AskbotTestCase):

    def setUp(self):
        self.u1 = self.create_user(username='user1')
        self.u2 = self.create_user(username='user2')
        self.u3 = self.create_user(username='user3')

    def test_get_related_object_type_name_for_question(self):
        question = self.post_question(user=self.u1)
        #import ipdb; ipdb.set_trace()
        ct = ContentType.objects.get_for_model(question)
        self.assertEqual('question', get_related_object_type_name(ct.id, question.id))

    def test_get_related_object_type_name_for_question_revision(self):
        question = self.post_question(user=self.u1)
        revision = question.revisions.all()[0]
        ct = ContentType.objects.get_for_model(revision)
        self.assertEqual('question', get_related_object_type_name(ct.id, revision.id))

    def test_get_related_object_type_name_for_answer(self):
        question = self.post_question(user=self.u1)
        answer = self.post_answer(user=self.u1, question=question)
        ct = ContentType.objects.get_for_model(answer)
        self.assertEqual('answer', get_related_object_type_name(ct.id, answer.id))

    def test_get_related_object_type_name_for_answer_revision(self):
        question = self.post_question(user=self.u1)
        answer = self.post_answer(user=self.u1, question=question)
        revision = answer.revisions.all()[0]
        ct = ContentType.objects.get_for_model(revision)
        self.assertEqual('answer', get_related_object_type_name(ct.id, revision.id))

    def test_get_related_object_type_name_for_anything_else_1(self):
        ct = ContentType.objects.get_for_model(self.u2)
        self.assertTrue(
            get_related_object_type_name(ct.id, self.u2.id) is None
        )

    def test_get_related_object_type_name_for_anything_else_2(self):
        question = self.post_question(user=self.u1)
        comment = self.post_comment(user=self.u1, parent_post=question)
        ct = ContentType.objects.get_for_model(comment)
        self.assertTrue(
            get_related_object_type_name(ct.id, comment.id) is None
        )

    def test_proper_PostRevision_manager_is_used(self):
        "Makes sure that both normal and related managers for PostRevision don't implement .create() method"
        question = self.post_question(user=self.u1)
        self.assertRaises(NotImplementedError, question.revisions.create)
        self.assertRaises(NotImplementedError, PostRevision.objects.create)
