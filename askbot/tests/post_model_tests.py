import datetime

from django.core.exceptions import ValidationError
from askbot.tests.utils import AskbotTestCase
from askbot.models import PostRevision


class PostModelTests(AskbotTestCase):

    def setUp(self):
        self.u1 = self.create_user(username='user1')
        self.u2 = self.create_user(username='user2')
        self.u3 = self.create_user(username='user3')

    def test_model_validation(self):
        with self.assertRaises(NotImplementedError):
            PostRevision.objects.create(text='blah', author=self.u1, revised_at=datetime.datetime.now(), revision_type=PostRevision.QUESTION_REVISION)

        with self.assertRaisesRegexp(AttributeError, r"'NoneType' object has no attribute 'revisions'"):
            # cannot set `revision` without a parent
            PostRevision.objects.create_answer_revision(text='blah', author=self.u1, revised_at=datetime.datetime.now())

        with self.assertRaisesRegexp(ValidationError, r"{'__all__': \[u'One \(and only one\) of question/answer fields has to be set.'\], 'revision_type': \[u'Value 4 is not a valid choice.'\]}"):
            # revision_type not in (1,2)
            PostRevision(text='blah', author=self.u1, revised_at=datetime.datetime.now(), revision=1, revision_type=4).save()

        question = self.post_question(user=self.u1)

        rev2 = PostRevision(question=question, text='blah', author=self.u1, revised_at=datetime.datetime.now(), revision=2, revision_type=PostRevision.QUESTION_REVISION)
        rev2.save()
        self.assertIsNotNone(rev2.id)

        with self.assertRaisesRegexp(ValidationError, r"{'__all__': \[u'Revision_type doesn`t match values in question/answer fields.', u'Post revision with this Question and Revision already exists.'\]}"):
            PostRevision(question=question, text='blah', author=self.u1, revised_at=datetime.datetime.now(), revision=2, revision_type=PostRevision.ANSWER_REVISION).save()

        with self.assertRaisesRegexp(ValidationError, r"{'__all__': \[u'Revision_type doesn`t match values in question/answer fields.'\]}"):
            PostRevision(question=question, text='blah', author=self.u1, revised_at=datetime.datetime.now(), revision=3, revision_type=PostRevision.ANSWER_REVISION).save()

        rev3 = PostRevision.objects.create_question_revision(question=question, text='blah', author=self.u1, revised_at=datetime.datetime.now(), revision_type=123) # revision_type
        self.assertIsNotNone(rev3.id)
        self.assertEqual(3, rev3.revision) # By the way: let's test the auto-increase of revision number
        self.assertEqual(PostRevision.QUESTION_REVISION, rev3.revision_type)

    def test_post_revision_autoincrease(self):
        question = self.post_question(user=self.u1)
        self.assertEqual(1, question.revisions.all()[0].revision)
        self.assertEqual(1, question.revisions.count())

        question.apply_edit(edited_by=self.u1, text="blah2", comment="blahc2")
        self.assertEqual(2, question.revisions.all()[0].revision)
        self.assertEqual(2, question.revisions.count())

        question.apply_edit(edited_by=self.u1, text="blah3", comment="blahc3")
        self.assertEqual(3, question.revisions.all()[0].revision)
        self.assertEqual(3, question.revisions.count())
