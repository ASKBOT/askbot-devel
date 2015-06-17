import bs4
import copy
import datetime
import functools
import time
from django.conf import settings as django_settings
from django.core import management
from django.core import serializers
import django.core.mail
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client
from django.utils import translation
from askbot.tests import utils
from askbot.tests.utils import with_settings
from askbot import models
from askbot import mail
from askbot.conf import settings as askbot_settings
from askbot import const
from askbot.models.question import Thread

TO_JSON = functools.partial(serializers.serialize, 'json')

def email_alert_test(test_func):
    """decorator for test methods in
    :class:`~askbot.tests.email_alert_tests.EmailAlertTests`
    wraps tests with a generic sequence of testing
    email alerts on updates to anything relating to
    given question
    """
    @functools.wraps(test_func)
    def wrapped_test(test_object, *args, **kwargs):
        func_name = test_func.__name__
        if func_name.startswith('test_'):
            test_name = func_name.replace('test_', '', 1)
            #run the main codo of the test function
            test_func(test_object)
            #if visit_timestamp is set,
            #target user will visit the question at that time
            test_object.maybe_visit_question()
            test_object.send_alerts()
            test_object.check_results(test_name)
        else:
            raise ValueError('test method names must have prefix "test_"')
    return wrapped_test

def setup_email_alert_tests(setup_func):
    @functools.wraps(setup_func)
    def wrapped_setup(test_object, *args, **kwargs):
        #empty email subscription schedule
        #no email is sent
        test_object.notification_schedule = \
                    copy.deepcopy(models.EmailFeedSetting.NO_EMAIL_SCHEDULE)
        #timestamp to use for the setup
        #functions
        test_object.setup_timestamp = datetime.datetime.now()

        #timestamp to use for the question visit
        #by the target user
        #if this timestamp is None then there will be no visit
        #otherwise question will be visited by the target user
        #at that time
        test_object.visit_timestamp = None

        #dictionary to hols expected results for each test
        #actual data@is initialized in the code just before the function
        #or in the body of the subclass
        test_object.expected_results = dict()

        #do not follow by default (do not use q_sel type subscription)
        test_object.follow_question = False

        #fill out expected result for each test
        test_object.expected_results['q_ask'] = {'message_count': 0, }
        test_object.expected_results['q_ask_delete_answer'] = {'message_count': 0, }
        test_object.expected_results['question_comment'] = {'message_count': 0, }
        test_object.expected_results['question_comment_delete'] = {'message_count': 0, }
        test_object.expected_results['answer_comment'] = {'message_count': 0, }
        test_object.expected_results['answer_delete_comment'] = {'message_count': 0, }
        test_object.expected_results['mention_in_question'] = {'message_count': 0, }
        test_object.expected_results['mention_in_answer'] = {'message_count': 0, }
        test_object.expected_results['question_edit'] = {'message_count': 0, }
        test_object.expected_results['answer_edit'] = {'message_count': 0, }
        test_object.expected_results['question_and_answer_by_target'] = {'message_count': 0, }
        test_object.expected_results['q_ans'] = {'message_count': 0, }
        test_object.expected_results['q_ans_new_answer'] = {'message_count': 0, }

        #this function is expected to contain a difference between this
        #one and the desired setup within the concrete test
        setup_func(test_object)
        #must call this after setting up the notification schedule
        #because it is needed in setUpUsers() function
        test_object.setUpUsers()
    return wrapped_setup

class SubjectLineTests(TestCase):
    """Tests for the email subject line"""
    def test_set_prefix(self):
        """set prefix and see if it is there
        """
        askbot_settings.update('EMAIL_SUBJECT_PREFIX', 'test prefix')
        subj = mail.prefix_the_subject_line('hahah')
        self.assertEquals(subj, 'test prefix hahah')

    def test_can_disable_prefix(self):
        """set prefix to empty string and make sure
        that the subject line is not altered"""
        askbot_settings.update('EMAIL_SUBJECT_PREFIX', '')
        subj = mail.prefix_the_subject_line('hahah')
        self.assertEquals(subj, 'hahah')

class EmailAlertTests(TestCase):
    """Base class for testing delayed Email notifications
    that are triggered by the send_email_alerts
    command

    this class tests cases where target user has no subscriptions
    that is all subscriptions off

    subclasses should redefine initial data via the static
    class member    this class tests cases where target user has no subscriptions
    that is all subscriptions off

    this class also defines a few utility methods that do
    not run any tests themselves

    class variables:

    * notification_schedule
    * setup_timestamp
    * visit_timestamp
    * expected_results

    should be set in subclasses to reuse testing code
    """

    def send_alerts(self):
        """runs the send_email_alerts management command
        and makes a shortcut access to the outbox
        """
        #make sure tha we are not sending email for real
        #this setting must be present in settings.py
        assert(
            django_settings.EMAIL_BACKEND == 'django.core.mail.backends.locmem.EmailBackend'
        )
        management.call_command('send_email_alerts')

    @setup_email_alert_tests
    def setUp(self):
        """generic pre-test setup method:

        this function is empty - because it's intendend content is
        entirely defined by the decorator

        the ``setUp()`` function in any subclass must only enter differences
        between the default version (defined in the decorator) and the
        desired version in the "real" test
        """
        translation.activate('en')
        pass

    def setUpUsers(self):
        self.other_user = utils.create_user(
            username = 'other',
            email = 'other@domain.com',
            date_joined = self.setup_timestamp,
            status = 'm'
        )
        self.target_user = utils.create_user(
            username = 'target',
            email = 'target@domain.com',
            notification_schedule = self.notification_schedule,
            date_joined = self.setup_timestamp,
            status = 'm'
        )

    def post_comment(
                self,
                author = None,
                parent_post = None,
                body_text = 'dummy test comment',
                timestamp = None
            ):
        """posts and returns a comment to parent post, uses
        now timestamp if not given, dummy body_text
        author is required
        """
        if timestamp is None:
            timestamp = self.setup_timestamp
        comment = author.post_comment(
                        parent_post = parent_post,
                        body_text = body_text,
                        timestamp = timestamp,
                    )
        return comment

    def edit_post(
                self,
                author = None,
                post = None,
                timestamp = None,
                body_text = 'edited body text',
            ):
        """todo: this method may also edit other stuff
        like post title and tags - in the case when post is
        of type question
        """
        if timestamp is None:
            timestamp = self.setup_timestamp
        author.edit_post(
                    post=post,
                    timestamp=timestamp,
                    body_text=body_text,
                    revision_comment='nothing serious'
                )

    def post_question(
                self,
                author = None,
                timestamp = None,
                title = 'test question title',
                body_text = 'test question body',
                tags = 'test',
            ):
        """post a question with dummy content
        and return it
        """
        if timestamp is None:
            timestamp = self.setup_timestamp
        self.question = author.post_question(
                            title = title,
                            body_text = body_text,
                            tags = tags,
                            timestamp = timestamp
                        )
        if self.follow_question:
            self.target_user.follow_question(self.question)
        return self.question

    def maybe_visit_question(self, user = None):
        """visits question on behalf of a given user and applies
        a timestamp set in the class attribute ``visit_timestamp``

        if ``visit_timestamp`` is None, then visit is skipped

        parameter ``user`` is optional if not given, the visit will occur
        on behalf of the user stored in the class attribute ``target_user``
        """
        if self.visit_timestamp:
            if user is None:
                user = self.target_user
            user.visit_post(
                        question = self.question,
                        timestamp = self.visit_timestamp
                    )

    def post_answer(
                self,
                question = None,
                author = None,
                body_text = 'test answer body',
                timestamp = None,
                follow = None,#None - do nothing, True/False - follow/unfollow
            ):
        """post answer with dummy content and return it
        """
        if timestamp is None:
            timestamp = self.setup_timestamp

        if follow is None:
            if author.is_following_question(question):
                follow = True
            else:
                follow = False
        elif follow not in (True, False):
            raise ValueError('"follow" may be only None, True or False')

        return author.post_answer(
                    question = question,
                    body_text = body_text,
                    timestamp = timestamp,
                    follow = follow,
                )

    def check_results(self, test_key = None):
        if test_key is None:
            raise ValueError('test_key parameter is required')
        expected = self.expected_results[test_key]
        outbox = django.core.mail.outbox
        error_message =  'emails_sent=%d, expected=%d, function=%s.test_%s' % (
                                                    len(outbox),
                                                    expected['message_count'],
                                                    self.__class__.__name__,
                                                    test_key,
                                                )
        #compares number of emails in the outbox and
        #the expected message count for the current test
        self.assertEqual(len(outbox), expected['message_count'], error_message)
        if expected['message_count'] > 0:
            if len(outbox) > 0:
                error_message = 'expected recipient %s found %s' % \
                    (self.target_user.email, outbox[0].recipients()[0])
                #verify that target user receives the email
                self.assertEqual(
                            outbox[0].recipients()[0],
                            self.target_user.email,
                            error_message
                        )

    def proto_post_answer_comment(self):
        """base method for use in some tests
        """
        question = self.post_question(
                            author = self.other_user
                        )
        answer = self.post_answer(
                            question = question,
                            author = self.target_user
                        )
        comment = self.post_comment(
                    parent_post = answer,
                    author = self.other_user,
                )
        return comment

    @email_alert_test
    def test_answer_comment(self):
        """target user posts answer and other user posts a comment
        to the answer
        """
        self.proto_post_answer_comment()

    @email_alert_test
    def test_answer_delete_comment(self):
        comment = self.proto_post_answer_comment()
        comment.author.delete_comment(comment = comment)

    @email_alert_test
    def test_question_edit(self):
        question = self.post_question(author=self.target_user)
        self.edit_post(post=question, author=self.other_user)
        self.question = question

    @email_alert_test
    def test_answer_edit(self):
        question = self.post_question(
                                author = self.target_user
                            )
        answer = self.post_answer(
                                question = question,
                                author = self.target_user
                            )
        self.edit_post(
                    post = answer,
                    author = self.other_user
                )
        self.question = question

    @email_alert_test
    def test_question_and_answer_by_target(self):
        question = self.post_question(
                                author = self.target_user
                            )
        answer = self.post_answer(
                                question = question,
                                author = self.target_user
                            )
        self.question = question

    def proto_question_comment(self):
        question = self.post_question(
                    author = self.target_user,
                )
        comment = self.post_comment(
                    author = self.other_user,
                    parent_post = question,
                )
        return comment

    @email_alert_test
    def test_question_comment(self):
        """target user posts question other user posts a comment
        target user does or does not receive email notification
        depending on the setup parameters

        in the base class user does not receive a notification
        """
        self.proto_question_comment()

    @email_alert_test
    def test_question_comment_delete(self):
        """target user posts question other user posts a comment
        target user does or does not receive email notification
        depending on the setup parameters

        in the base class user does not receive a notification
        """
        comment = self.proto_question_comment()
        comment.author.delete_comment(comment)

    def proto_test_q_ask(self):
        """base method for tests that
        have name containing q_ask - i.e. target asks other answers
        answer is returned
        """
        question = self.post_question(
                    author = self.target_user,
                )
        answer = self.post_answer(
                    question = question,
                    author = self.other_user,
                )
        return answer

    @email_alert_test
    def test_q_ask(self):
        """target user posts question
        other user answer the question
        """
        self.proto_test_q_ask()

    @email_alert_test
    def test_q_ask_delete_answer(self):
        answer = self.proto_test_q_ask()
        self.other_user.delete_post(answer)

    @email_alert_test
    def test_q_ans(self):
        """other user posts question
        target user post answer
        """
        question = self.post_question(
                                author = self.other_user,
                            )
        self.post_answer(
                    question = question,
                    author = self.target_user
                )
        self.question = question

    @email_alert_test
    def test_q_ans_new_answer(self):
        """other user posts question
        target user post answer and other user
        posts another answer
        """
        question = self.post_question(
                                author = self.other_user,
                            )
        self.post_answer(
                    question = question,
                    author = self.target_user
                )
        self.post_answer(
                    question = question,
                    author = self.other_user
                )
        self.question = question

    @email_alert_test
    def test_mention_in_question(self):
        question = self.post_question(
                                author = self.other_user,
                                body_text = 'hey @target get this'
                            )
        self.question = question

    @email_alert_test
    def test_mention_in_answer(self):
        question = self.post_question(
                                author = self.other_user,
                            )
        self.post_answer(
                    question = question,
                    author = self.other_user,
                    body_text = 'hey @target check this out'
                )
        self.question = question

class WeeklyQAskEmailAlertTests(EmailAlertTests):
    @setup_email_alert_tests
    def setUp(self):
        self.notification_schedule['q_ask'] = 'w'
        self.setup_timestamp = datetime.datetime.now() - datetime.timedelta(14)
        self.expected_results['q_ask'] = {'message_count': 1}
        self.expected_results['q_ask_delete_answer'] = {'message_count': 0}
        self.expected_results['question_edit'] = {'message_count': 1, }
        self.expected_results['answer_edit'] = {'message_count': 1, }

        #local tests
        self.expected_results['question_edit_reedited_recently'] = \
                                                    {'message_count': 1}
        self.expected_results['answer_edit_reedited_recently'] = \
                                                    {'message_count': 1}

    @email_alert_test
    def test_question_edit_reedited_recently(self):
        question = self.post_question(
                        author = self.target_user
                    )
        self.edit_post(
                    post = question,
                    author = self.other_user,
                )
        self.edit_post(
                    post = question,
                    author = self.other_user,
                    timestamp = datetime.datetime.now() - datetime.timedelta(1)
                )

    @email_alert_test
    def test_answer_edit_reedited_recently(self):
        question = self.post_question(
                        author = self.target_user
                    )
        answer = self.post_answer(
                    question = question,
                    author = self.other_user,
                )
        self.edit_post(
                    post = answer,
                    author = self.other_user,
                    timestamp = datetime.datetime.now() - datetime.timedelta(1)
                )

class WeeklyMentionsAndCommentsEmailAlertTests(EmailAlertTests):
    @setup_email_alert_tests
    def setUp(self):
        self.notification_schedule['m_and_c'] = 'w'
        self.setup_timestamp = datetime.datetime.now() - datetime.timedelta(14)
        self.expected_results['question_comment'] = {'message_count': 1, }
        self.expected_results['question_comment_delete'] = {'message_count': 0, }
        self.expected_results['answer_comment'] = {'message_count': 1, }
        self.expected_results['answer_delete_comment'] = {'message_count': 0, }
        self.expected_results['mention_in_question'] = {'message_count': 1, }
        self.expected_results['mention_in_answer'] = {'message_count': 1, }

class WeeklyQAnsEmailAlertTests(EmailAlertTests):
    @setup_email_alert_tests
    def setUp(self):
        self.notification_schedule['q_ans'] = 'w'
        self.setup_timestamp = datetime.datetime.now() - datetime.timedelta(14)
        self.expected_results['answer_edit'] = {'message_count': 1, }
        self.expected_results['q_ans_new_answer'] = {'message_count': 1, }

class InstantQAskEmailAlertTests(EmailAlertTests):
    @setup_email_alert_tests
    def setUp(self):
        self.notification_schedule['q_ask'] = 'i'
        self.setup_timestamp = datetime.datetime.now() - datetime.timedelta(1)
        self.expected_results['q_ask'] = {'message_count': 1}
        self.expected_results['q_ask_delete_answer'] = {'message_count': 1}
        self.expected_results['question_edit'] = {'message_count': 1, }
        self.expected_results['answer_edit'] = {'message_count': 1, }

class InstantWholeForumEmailAlertTests(EmailAlertTests):
    @setup_email_alert_tests
    def setUp(self):
        self.notification_schedule['q_all'] = 'i'
        self.setup_timestamp = datetime.datetime.now() - datetime.timedelta(1)

        self.expected_results['q_ask'] = {'message_count': 1, }
        self.expected_results['q_ask_delete_answer'] = {'message_count': 1}
        self.expected_results['question_comment'] = {'message_count': 1, }
        self.expected_results['question_comment_delete'] = {'message_count': 1, }
        self.expected_results['answer_comment'] = {'message_count': 2, }
        self.expected_results['answer_delete_comment'] = {'message_count': 2, }
        self.expected_results['mention_in_question'] = {'message_count': 1, }
        self.expected_results['mention_in_answer'] = {'message_count': 2, }
        self.expected_results['question_edit'] = {'message_count': 1, }
        self.expected_results['answer_edit'] = {'message_count': 1, }
        self.expected_results['question_and_answer_by_target'] = {'message_count': 0, }
        self.expected_results['q_ans'] = {'message_count': 1, }
        self.expected_results['q_ans_new_answer'] = {'message_count': 2, }

    def test_global_subscriber_with_zero_frequency_gets_no_email(self):
        user = self.target_user
        user.notification_subscriptions.update(frequency='n')
        user.email_tag_filter_strategy = const.INCLUDE_ALL
        user.save()
        self.post_question(author=self.other_user)
        outbox = django.core.mail.outbox
        self.assertEqual(len(outbox), 0)


class BlankWeeklySelectedQuestionsEmailAlertTests(EmailAlertTests):
    """blank means that this is testing for the absence of email
    because questions are not followed as set by default in the
    parent class
    """
    @setup_email_alert_tests
    def setUp(self):
        self.notification_schedule['q_sel'] = 'w'
        self.setup_timestamp = datetime.datetime.now() - datetime.timedelta(14)
        self.expected_results['q_ask'] = {'message_count': 1, }
        self.expected_results['q_ask_delete_answer'] = {'message_count': 0, }
        self.expected_results['question_comment'] = {'message_count': 0, }
        self.expected_results['question_comment_delete'] = {'message_count': 0, }
        self.expected_results['answer_comment'] = {'message_count': 0, }
        self.expected_results['answer_delete_comment'] = {'message_count': 0, }
        self.expected_results['mention_in_question'] = {'message_count': 0, }
        self.expected_results['mention_in_answer'] = {'message_count': 0, }
        self.expected_results['question_edit'] = {'message_count': 1, }
        self.expected_results['answer_edit'] = {'message_count': 1, }
        self.expected_results['question_and_answer_by_target'] = {'message_count': 0, }
        self.expected_results['q_ans'] = {'message_count': 0, }
        self.expected_results['q_ans_new_answer'] = {'message_count': 0, }

class BlankInstantSelectedQuestionsEmailAlertTests(EmailAlertTests):
    """blank means that this is testing for the absence of email
    because questions are not followed as set by default in the
    parent class
    """
    @setup_email_alert_tests
    def setUp(self):
        self.notification_schedule['q_sel'] = 'i'
        self.setup_timestamp = datetime.datetime.now() - datetime.timedelta(1)
        self.expected_results['q_ask'] = {'message_count': 1, }
        self.expected_results['q_ask_delete_answer'] = {'message_count': 1, }
        self.expected_results['question_comment'] = {'message_count': 1, }
        self.expected_results['question_comment_delete'] = {'message_count': 1, }
        self.expected_results['answer_comment'] = {'message_count': 0, }
        self.expected_results['answer_delete_comment'] = {'message_count': 0, }
        self.expected_results['mention_in_question'] = {'message_count': 0, }
        self.expected_results['mention_in_answer'] = {'message_count': 0, }
        self.expected_results['question_edit'] = {'message_count': 1, }
        self.expected_results['answer_edit'] = {'message_count': 1, }
        self.expected_results['question_and_answer_by_target'] = {'message_count': 0, }
        self.expected_results['q_ans'] = {'message_count': 0, }
        self.expected_results['q_ans_new_answer'] = {'message_count': 0, }

class LiveWeeklySelectedQuestionsEmailAlertTests(EmailAlertTests):
    """live means that this is testing for the presence of email
    as all questions are automatically followed by user here
    """
    @setup_email_alert_tests
    def setUp(self):
        self.notification_schedule['q_sel'] = 'w'
        self.setup_timestamp = datetime.datetime.now() - datetime.timedelta(14)
        self.follow_question = True

        self.expected_results['q_ask'] = {'message_count': 1, }
        self.expected_results['q_ask_delete_answer'] = {'message_count': 0}
        self.expected_results['question_comment'] = {'message_count': 0, }
        self.expected_results['question_comment_delete'] = {'message_count': 0, }
        self.expected_results['answer_comment'] = {'message_count': 0, }
        self.expected_results['answer_delete_comment'] = {'message_count': 0, }
        self.expected_results['mention_in_question'] = {'message_count': 1, }
        self.expected_results['mention_in_answer'] = {'message_count': 1, }
        self.expected_results['question_edit'] = {'message_count': 1, }
        self.expected_results['answer_edit'] = {'message_count': 1, }
        self.expected_results['question_and_answer_by_target'] = {'message_count': 0, }
        self.expected_results['q_ans'] = {'message_count': 0, }
        self.expected_results['q_ans_new_answer'] = {'message_count': 1, }

class LiveInstantSelectedQuestionsEmailAlertTests(EmailAlertTests):
    """live means that this is testing for the presence of email
    as all questions are automatically followed by user here
    """
    @setup_email_alert_tests
    def setUp(self):
        self.notification_schedule['q_sel'] = 'i'
        #first posts yesterday
        self.setup_timestamp = datetime.datetime.now() - datetime.timedelta(1)
        self.follow_question = True

        self.expected_results['q_ask'] = {'message_count': 1, }
        self.expected_results['q_ask_delete_answer'] = {'message_count': 1}
        self.expected_results['question_comment'] = {'message_count': 1, }
        self.expected_results['question_comment_delete'] = {'message_count': 1, }
        self.expected_results['answer_comment'] = {'message_count': 1, }
        self.expected_results['answer_delete_comment'] = {'message_count': 1, }
        self.expected_results['mention_in_question'] = {'message_count': 0, }
        self.expected_results['mention_in_answer'] = {'message_count': 1, }
        self.expected_results['question_edit'] = {'message_count': 1, }
        self.expected_results['answer_edit'] = {'message_count': 1, }
        self.expected_results['question_and_answer_by_target'] = {'message_count': 0, }
        self.expected_results['q_ans'] = {'message_count': 0, }
        self.expected_results['q_ans_new_answer'] = {'message_count': 1, }

class InstantMentionsAndCommentsEmailAlertTests(EmailAlertTests):
    @setup_email_alert_tests
    def setUp(self):
        self.notification_schedule['m_and_c'] = 'i'
        self.setup_timestamp = datetime.datetime.now() - datetime.timedelta(1)
        self.expected_results['question_comment'] = {'message_count': 1, }
        self.expected_results['question_comment_delete'] = {'message_count': 1, }
        self.expected_results['answer_comment'] = {'message_count': 1, }
        self.expected_results['answer_delete_comment'] = {'message_count': 1, }
        self.expected_results['mention_in_question'] = {'message_count': 1, }
        self.expected_results['mention_in_answer'] = {'message_count': 1, }

        #specialized local test case
        self.expected_results['question_edited_mention_stays'] = {'message_count': 1}

    @email_alert_test
    def test_question_edited_mention_stays(self):
        question = self.post_question(
                        author = self.other_user,
                        body_text = 'hey @target check this one',
                    )
        self.edit_post(
                    post = question,
                    author = self.other_user,
                    body_text = 'yoyo @target do look here'
                )


class InstantQAnsEmailAlertTests(EmailAlertTests):
    @setup_email_alert_tests
    def setUp(self):
        self.notification_schedule['q_ans'] = 'i'
        self.setup_timestamp = datetime.datetime.now() - datetime.timedelta(1)
        self.expected_results['answer_edit'] = {'message_count': 1, }
        self.expected_results['q_ans_new_answer'] = {'message_count': 1, }

class DelayedAlertSubjectLineTests(TestCase):
    def test_topics_in_subject_line(self):
        threads = [
            models.Thread(tagnames='one two three four five'),
            models.Thread(tagnames='two three four five'),
            models.Thread(tagnames='three four five'),
            models.Thread(tagnames='four five'),
            models.Thread(tagnames='five'),
        ]
        subject = Thread.objects.get_tag_summary_from_threads(threads)
        self.assertEqual('"five", "four", "three", "two" and "one"', subject)

        threads += [
            models.Thread(tagnames='six'),
            models.Thread(tagnames='six'),
            models.Thread(tagnames='six'),
            models.Thread(tagnames='six'),
            models.Thread(tagnames='six'),
            models.Thread(tagnames='six'),
        ]
        subject = Thread.objects.get_tag_summary_from_threads(threads)
        self.assertEqual('"six", "five", "four", "three", "two" and more', subject)

class FeedbackTests(utils.AskbotTestCase):
    def setUp(self):
        self.create_user(username = 'user1', status='m')
        self.create_user(username = 'user2', status='m')
        u3 = self.create_user(username = 'user3')
        u3.is_superuser = True
        u3.save()

    def assert_feedback_works(self):
        outbox = django.core.mail.outbox
        self.assertEqual(len(outbox), 1)
        #todo: change groups to django groups
        #then replace to 4 back to 3 in the line below
        self.assertEqual(len(outbox[0].recipients()), 3)

    def test_feedback_post_form(self):
        client = Client()
        data = {
            'email': 'evgeny.fadeev@gmail.com',
            'text': 'hi this is a test case',
            'subject': 'subject line'
        }
        response = client.post(reverse('feedback'), data)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.templates[0].name, 'feedback.html')

    def test_mail_moderators(self):
        """tests askbot.mail_moderators()
        """
        mail.mail_moderators('subject', 'text')
        self.assert_feedback_works()


class TagFollowedInstantWholeForumEmailAlertTests(utils.AskbotTestCase):
    def setUp(self):
        self.user1 = self.create_user(
            username = 'user1',
            notification_schedule = {'q_all': 'i'},
            status = 'm'
        )
        self.user2 = self.create_user(
            username = 'user2',
            status = 'm'
        )

    def test_wildcard_catches_new_tag(self):
        """users asks a question with a brand new tag
        and other user subscribes to it by wildcard
        """
        askbot_settings.update('USE_WILDCARD_TAGS', True)
        self.user1.email_tag_filter_strategy = const.INCLUDE_INTERESTING
        self.user1.save()
        self.user1.mark_tags(
            wildcards = ('some*',),
            reason = 'good',
            action = 'add'
        )
        self.user2.post_question(
            title = 'some title',
            body_text = 'some text for the question',
            tags = 'something'
        )
        outbox = django.core.mail.outbox
        self.assertEqual(len(outbox), 1)
        self.assertEqual(len(outbox[0].recipients()), 1)
        self.assertTrue(
            self.user1.email in outbox[0].recipients()
        )

    @with_settings(SUBSCRIBED_TAG_SELECTOR_ENABLED=False)
    def test_tag_based_subscription_on_new_question_works1(self):
        """someone subscribes for an pre-existing tag
        then another user asks a question with that tag
        and the subcriber receives an alert
        """
        models.Tag(
            name = 'something',
            created_by = self.user1
        ).save()

        self.user1.email_tag_filter_strategy = const.INCLUDE_INTERESTING
        self.user1.save()
        self.user1.mark_tags(
            tagnames = ('something',),
            reason = 'good',
            action = 'add'
        )
        self.user2.post_question(
            title = 'some title',
            body_text = 'some text for the question',
            tags = 'something'
        )
        outbox = django.core.mail.outbox
        self.assertEqual(len(outbox), 1)
        self.assertEqual(len(outbox[0].recipients()), 1)
        self.assertTrue(
            self.user1.email in outbox[0].recipients()
        )

    @with_settings(SUBSCRIBED_TAG_SELECTOR_ENABLED=True)
    def test_tag_based_subscription_on_new_question_works2(self):
        """someone subscribes for an pre-existing tag
        then another user asks a question with that tag
        and the subcriber receives an alert
        """
        models.Tag(
            name = 'something',
            created_by = self.user1
        ).save()

        self.user1.email_tag_filter_strategy = const.INCLUDE_SUBSCRIBED
        self.user1.save()
        self.user1.mark_tags(
            tagnames = ('something',),
            reason = 'subscribed',
            action = 'add'
        )
        self.user2.post_question(
            title = 'some title',
            body_text = 'some text for the question',
            tags = 'something'
        )
        outbox = django.core.mail.outbox
        self.assertEqual(len(outbox), 1)
        self.assertEqual(len(outbox[0].recipients()), 1)
        self.assertTrue(
            self.user1.email in outbox[0].recipients()
        )

class EmailReminderTestCase(utils.AskbotTestCase):
    #subclass must define these (example below)
    #enable_setting_name = 'ENABLE_UNANSWERED_REMINDERS'
    #frequency_setting_name = 'UNANSWERED_REMINDER_FREQUENCY'
    #days_before_setting_name = 'DAYS_BEFORE_SENDING_UNANSWERED_REMINDER'
    #max_reminder_setting_name = 'MAX_UNANSWERED_REMINDERS'

    def setUp(self):
        self.u1 = self.create_user(username = 'user1')
        self.u2 = self.create_user(username = 'user2')
        askbot_settings.update(self.enable_setting_name, True)
        askbot_settings.update(self.max_reminder_setting_name, 5)
        askbot_settings.update(self.frequency_setting_name, 1)
        askbot_settings.update(self.days_before_setting_name, 2)

        self.wait_days = getattr(askbot_settings, self.days_before_setting_name)
        self.recurrence_days = getattr(askbot_settings, self.frequency_setting_name)
        self.max_emails = getattr(askbot_settings, self.max_reminder_setting_name)

    def assert_have_emails(self, email_count = None):
        management.call_command(self.command_name)
        outbox = django.core.mail.outbox
        self.assertEqual(len(outbox), email_count)

    def do_post(self, timestamp):
        self.question = self.post_question(
            user = self.u1,
            timestamp = timestamp
        )


class AcceptAnswerReminderTests(EmailReminderTestCase):
    """only two test cases here, because the algorithm here
    is the same as for unanswered questons,
    except here we are dealing with the questions that have
    or do not have an accepted answer
    """
    enable_setting_name = 'ENABLE_ACCEPT_ANSWER_REMINDERS'
    frequency_setting_name = 'ACCEPT_ANSWER_REMINDER_FREQUENCY'
    days_before_setting_name = 'DAYS_BEFORE_SENDING_ACCEPT_ANSWER_REMINDER'
    max_reminder_setting_name = 'MAX_ACCEPT_ANSWER_REMINDERS'
    command_name = 'send_accept_answer_reminders'

    def do_post(self, timestamp):
        super(AcceptAnswerReminderTests, self).do_post(timestamp)
        self.answer = self.post_answer(
            question = self.question,
            user = self.u2,
            timestamp = timestamp
        )

    def test_reminder_positive_wait(self):
        """a positive test - user must receive a reminder
        """
        days_ago = self.wait_days
        timestamp = datetime.datetime.now() - datetime.timedelta(days_ago, 3600)
        self.do_post(timestamp)
        self.assert_have_emails(1)

    def test_reminder_negative_wait(self):
        """negative test - the answer is accepted already"""
        days_ago = self.wait_days
        timestamp = datetime.datetime.now() - datetime.timedelta(days_ago, 3600)
        self.do_post(timestamp)
        self.u1.accept_best_answer(
            answer = self.answer,
        )
        self.assert_have_emails(0)


class UnansweredReminderTests(EmailReminderTestCase):

    enable_setting_name = 'ENABLE_UNANSWERED_REMINDERS'
    frequency_setting_name = 'UNANSWERED_REMINDER_FREQUENCY'
    days_before_setting_name = 'DAYS_BEFORE_SENDING_UNANSWERED_REMINDER'
    max_reminder_setting_name = 'MAX_UNANSWERED_REMINDERS'
    command_name = 'send_unanswered_question_reminders'

    def test_reminder_positive_wait(self):
        """a positive test - user must receive a reminder
        """
        days_ago = self.wait_days
        timestamp = datetime.datetime.now() - datetime.timedelta(days_ago, 3600)
        self.do_post(timestamp)
        self.assert_have_emails(1)

    def test_reminder_negative_wait(self):
        """a positive test - user must receive a reminder
        """
        days_ago = self.wait_days - 1
        timestamp = datetime.datetime.now() - datetime.timedelta(days_ago, 3600)
        self.do_post(timestamp)
        self.assert_have_emails(0)

    def test_reminder_cutoff_positive(self):
        """send a reminder a slightly before the last reminder
        date passes"""
        days_ago = self.wait_days + (self.max_emails - 1)*self.recurrence_days - 1
        timestamp = datetime.datetime.now() - datetime.timedelta(days_ago, 3600)
        self.do_post(timestamp)
        #todo: change groups to django groups
        #then replace to 2 back to 1 in the line below
        self.assert_have_emails(1)


    def test_reminder_cutoff_negative(self):
        """no reminder after the time for the last reminder passes
        """
        days_ago = self.wait_days + (self.max_emails - 1)*self.recurrence_days
        timestamp = datetime.datetime.now() - datetime.timedelta(days_ago, 3600)
        self.do_post(timestamp)
        self.assert_have_emails(0)

class EmailFeedSettingTests(utils.AskbotTestCase):
    def setUp(self):
        self.user = self.create_user('user')

    def get_user_feeds(self):
        return models.EmailFeedSetting.objects.filter(subscriber = self.user)

    def test_add_missings_subscriptions_noop(self):
        data_before = TO_JSON(self.get_user_feeds())
        self.user.add_missing_askbot_subscriptions()
        data_after = TO_JSON(self.get_user_feeds())
        self.assertEquals(data_before, data_after)

    def test_add_missing_q_all_subscription(self):
        feed = self.get_user_feeds().filter(feed_type = 'q_all')
        feed.delete()
        count_before = self.get_user_feeds().count()
        self.user.add_missing_askbot_subscriptions()
        count_after = self.get_user_feeds().count()
        self.assertEquals(count_after - count_before, 1)

        feed = self.get_user_feeds().filter(feed_type = 'q_all')[0]

        self.assertEquals(
            feed.frequency,
            askbot_settings.DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_Q_ALL
        )

    def test_missing_subscriptions_added_automatically(self):
        new_user = models.User.objects.create_user('new', 'new@example.com')
        feeds_before = self.get_user_feeds()

        #verify that feed settigs are created automatically
        #when user is just created
        self.assertTrue(feeds_before.count() != 0)

        data_before = TO_JSON(feeds_before)
        new_user.add_missing_askbot_subscriptions()
        data_after = TO_JSON(self.get_user_feeds())
        self.assertEquals(data_before, data_after)


class EmailAlertTestsWithGroupsEnabled(utils.AskbotTestCase):

    def setUp(self):
        self.backup = askbot_settings.GROUPS_ENABLED
        askbot_settings.update('GROUPS_ENABLED', True)

    def tearDown(self):
        askbot_settings.update('GROUPS_ENABLED', self.backup)

    @with_settings(MIN_REP_TO_TRIGGER_EMAIL=1)
    def test_notification_for_global_group_works(self):
        sender = self.create_user('sender')
        recipient = self.create_user(
            'recipient',
            notification_schedule=models.EmailFeedSetting.MAX_EMAIL_SCHEDULE
        )
        self.post_question(user=sender)
        outbox = django.core.mail.outbox
        self.assertEqual(len(outbox), 1)
        self.assertEqual(outbox[0].recipients(), [recipient.email])


class PostApprovalTests(utils.AskbotTestCase):
    """test notifications sent to authors when their posts
    are approved or published"""
    def setUp(self):
        self.reply_by_email = askbot_settings.REPLY_BY_EMAIL
        askbot_settings.update('REPLY_BY_EMAIL', True)
        self.content_moderation_mode = \
            askbot_settings.CONTENT_MODERATION_MODE
        askbot_settings.update('CONTENT_MODERATION_MODE', 'premoderation')
        self.self_notify_when = \
            askbot_settings.SELF_NOTIFY_EMAILED_POST_AUTHOR_WHEN
        when = const.FOR_FIRST_REVISION
        askbot_settings.update('SELF_NOTIFY_EMAILED_POST_AUTHOR_WHEN', when)
        assert(
            django_settings.EMAIL_BACKEND == 'django.core.mail.backends.locmem.EmailBackend'
        )

    def tearDown(self):
        askbot_settings.update(
            'REPLY_BY_EMAIL', self.reply_by_email
        )
        askbot_settings.update(
            'CONTENT_MODERATION_MODE',
            self.content_moderation_mode
        )
        askbot_settings.update(
            'SELF_NOTIFY_EMAILED_POST_AUTHOR_WHEN',
            self.self_notify_when
        )

    def test_emailed_question_answerable_approval_notification(self):
        self.u1 = self.create_user('user1', status='a')#watched user
        question = self.post_question(user=self.u1, by_email=True)
        outbox = django.core.mail.outbox
        #here we should get just the notification of the post
        #being placed on the moderation queue
        self.assertEquals(len(outbox), 1)
        self.assertEquals(outbox[0].recipients(), [self.u1.email])

    def test_moderated_question_answerable_approval_notification(self):
        u1 = self.create_user('user1', status = 'w')
        question = self.post_question(user = u1, by_email = True)

        self.assertEquals(question.approved, False)

        u2 = self.create_user('admin', status = 'd')

        self.assertEquals(question.revisions.count(), 1)
        u2.approve_post_revision(question.get_latest_revision())

        outbox = django.core.mail.outbox
        self.assertEquals(len(outbox), 2)
        #moderation notification
        self.assertEquals(outbox[0].recipients(), [u1.email,])
        #self.assertEquals(outbox[1].recipients(), [u1.email,])#approval


class AbsolutizeUrlsInEmailsTests(utils.AskbotTestCase):
    @with_settings(
        MIN_REP_TO_TRIGGER_EMAIL=1,
        APP_URL='http://example.com/',
        MIN_REP_TO_INSERT_LINK=1
    )
    def test_urls_are_absolute(self):
        u1 = self.create_user('u1')
        max_email = models.EmailFeedSetting.MAX_EMAIL_SCHEDULE
        u2 = self.create_user('u2', notification_schedule=max_email)
        text = '<a href="/index.html">home</a>' + \
        '<img alt="an image" src=\'/img.png\'><a href="https://example.com"><img src="/img.png"/></a>'
        question = self.post_question(user=u1, body_text=text)
        outbox = django.core.mail.outbox
        html_message = outbox[0].alternatives[0][0]
        content_type = outbox[0].alternatives[0][1]
        self.assertEqual(content_type, 'text/html')

        soup = bs4.BeautifulSoup(html_message)
        links = soup.find_all('a')
        url_bits = {}
        for link in links:
            if link.attrs['href'].startswith('mailto:'):
                continue
            url_bits[link.attrs['href'][:4]] = 1

        self.assertEqual(len(url_bits.keys()), 1)
        self.assertEqual(url_bits.keys()[0], 'http')

        images = soup.find_all('img')
        url_bits = {}
        for img in images:
            url_bits[img.attrs['src'][:4]] = 1

        self.assertEqual(len(url_bits.keys()), 1)
        self.assertEqual(url_bits.keys()[0], 'http')


class MailMessagesTests(utils.AskbotTestCase):
    def test_ask_for_signature(self):
        from askbot.mail.messages import AskForSignature
        user = self.create_user('user')
        message = AskForSignature({
                            'user': user,
                            'footer_code': 'nothing'
                        }).render_body()
        self.assertTrue(user.username in message)
