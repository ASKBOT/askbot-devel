from datetime import datetime, timedelta
import time_machine
from django.test.utils import override_settings
from django.http import HttpRequest
from django.core.management import call_command
from askbot.tests.utils import AskbotTestCase
from askbot import signals
from askbot.models.analytics import (Session, Event, HourlyUserSummary,
                                     HourlyGroupSummary, DailyUserSummary,
                                     DailyGroupSummary,
                                     EVENT_TYPE_UPVOTED,
                                     EVENT_TYPE_DOWNVOTED)

class TestAnalytics(AskbotTestCase):

    def register_user(self, email, user_status='a'):
        """Registers and logs in the user,
        Creates a session. Sends the registration and login signals.
        Returns the user object and session.
        """
        user = self.create_user(username=email.split('@')[0], email=email, status=user_status)
        self.client.force_login(user)
        # fake django request
        request = HttpRequest()
        request.user = user
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        request.META['HTTP_USER_AGENT'] = 'test'
        request.META['HTTP_ACCEPT_LANGUAGE'] = 'en-US,en;q=0.9'
        request.session = {'session_key': email + '-session'}
        session = Session.objects.create_session(user, '127.0.0.1', 'test')
        signals.user_registered.send(None, user=user, request=request)
        signals.user_logged_in.send(None, user=user, request=request, session_key='test')
        return user, session

    def mock_visit_question(self, user, question):
        request = HttpRequest()
        request.user = user
        signals.question_visited.send(None,
                                      request=request,
                                      question=question,
                                      timestamp=datetime.now())

    def post_question_and_answer(self, session, answer_delay, tags='test'):
        question = self.post_question(user=session.user, tags=tags)
        session.touch()
        signals.new_question_posted.send(None, question=question)

        time3 = datetime.now() + answer_delay
        with time_machine.travel(time3):
            answer = self.post_answer(user=session.user, question=question)
            session.touch()
            signals.new_answer_posted.send(None, answer=answer)

        return question, answer


    @override_settings(ASKBOT_ANALYTICS_EMAIL_DOMAIN_ORGANIZATIONS_ENABLED=True)
    def test_qa_time_on_site(self):
        """Tests the number of questions and answers and time on site"""
        time1 = '2024-02-29 12:00:00'
        with time_machine.travel(time1):
            user, session = self.register_user('test@test.com')

        self.assertEqual(Session.objects.count(), 1) # pylint: disable=no-member
        self.assertEqual(Event.objects.count(), 2) # pylint: disable=no-member

        time2 = '2024-02-29 12:15:00'
        answer_delay = timedelta(minutes=30)
        with time_machine.travel(time2):
            self.post_question_and_answer(session,
                                          answer_delay,
                                          tags='tag1 tag2')
        
        self.assertEqual(Session.objects.count(), 1) # pylint: disable=no-member
        self.assertEqual(Event.objects.count(), 4) # pylint: disable=no-member

        call_command('askbot_create_per_email_domain_groups')

        with time_machine.travel('2024-02-29 13:15:00'):
            call_command('askbot_compile_analytics')

        hus = HourlyUserSummary.objects.filter(user=user).all() # pylint: disable=no-member
        hgs = HourlyGroupSummary.objects.all() # pylint: disable=no-member
        self.assertEqual(hus.count(), 1)
        self.assertEqual(hgs.count(), 1)
        self.assertEqual(hus[0].hour, hgs[0].hour)
        self.assertEqual(hus[0].hour.hour, 12)
        time3 = datetime.strptime(time2, '%Y-%m-%d %H:%M:%S') + answer_delay
        expected_time_on_site = time3 - datetime.strptime(time1, '%Y-%m-%d %H:%M:%S')
        self.assertAlmostEqual(hus[0].time_on_site.total_seconds(),
                               expected_time_on_site.total_seconds(),
                               delta=2)
        self.assertAlmostEqual(hgs[0].time_on_site.total_seconds(),
                               expected_time_on_site.total_seconds(),
                               delta=2)
        self.assertEqual(hus[0].num_questions, 1)
        self.assertEqual(hus[0].num_answers, 1)

        # travel to the next day
        with time_machine.travel('2024-03-01 12:00:00'):
            call_command('askbot_compile_analytics')

        dus = DailyUserSummary.objects.filter(user=user).all() # pylint: disable=no-member
        self.assertEqual(dus.count(), 1)
        self.assertEqual(dus[0].num_questions, 1)
        self.assertEqual(dus[0].num_answers, 1)
        self.assertAlmostEqual(dus[0].time_on_site.total_seconds(),
                                expected_time_on_site.total_seconds(),
                                delta=2)

        dgs = DailyGroupSummary.objects.all() # pylint: disable=no-member
        self.assertEqual(dgs.count(), 1)
        self.assertEqual(dgs[0].num_questions, 1)
        self.assertEqual(dgs[0].num_answers, 1)
        self.assertAlmostEqual(dgs[0].time_on_site.total_seconds(),
                                expected_time_on_site.total_seconds(),
                                delta=2)


    @override_settings(ASKBOT_ANALYTICS_EMAIL_DOMAIN_ORGANIZATIONS_ENABLED=True)
    def test_votes(self):
        """User1 creates question and answer.
        User2 upvotes a question and downvotes an answer.
        Assertion is made for number of upvotes and downvotes.

        Also tests the number of users in the group.
        """
        time1 = '2024-02-29 12:00:00'
        with time_machine.travel(time1):
            user1, session1 = self.register_user('user1@test.com') # pylint: disable=unused-variable
            # admin so that the user can vote
            user2, session2 = self.register_user('user2@test.com', user_status='d')

        call_command('askbot_create_per_email_domain_groups')

        time2 = '2024-02-29 12:15:00'
        answer_delay = timedelta(minutes=30)
        with time_machine.travel(time2):
            question, answer = self.post_question_and_answer(session1, answer_delay)

        time3 = '2024-02-29 12:45:00'
        with time_machine.travel(time3):
            session2.touch()
            user2.upvote(question)
            user2.downvote(answer)

        self.assertEqual(Event.objects.filter(
            event_type=EVENT_TYPE_UPVOTED).count(), 1) # pylint: disable=no-member
        self.assertEqual(Event.objects.filter(
            event_type=EVENT_TYPE_DOWNVOTED).count(), 1) # pylint: disable=no-member

        time4 = '2024-02-29 13:15:00'
        with time_machine.travel(time4):
            call_command('askbot_compile_analytics')

        hus = HourlyUserSummary.objects.filter(user=user2).all() # pylint: disable=no-member
        self.assertEqual(hus.count(), 1)
        self.assertEqual(hus[0].num_upvotes, 1)
        self.assertEqual(hus[0].num_downvotes, 1)
        hgs = HourlyGroupSummary.objects.all() # pylint: disable=no-member
        self.assertEqual(hgs.count(), 1)
        self.assertEqual(hgs[0].num_upvotes, 1)
        self.assertEqual(hgs[0].num_downvotes, 1)
        self.assertEqual(hgs[0].num_users, 2)
        self.assertEqual(hgs[0].num_users_added, 2)

        time5 = '2024-03-01 12:00:00'
        with time_machine.travel(time5):
            call_command('askbot_compile_analytics')

        dus = DailyUserSummary.objects.filter(user=user2).all() # pylint: disable=no-member
        self.assertEqual(dus.count(), 1)
        self.assertEqual(dus[0].num_upvotes, 1)
        self.assertEqual(dus[0].num_downvotes, 1)

        dgs = DailyGroupSummary.objects.all() # pylint: disable=no-member
        self.assertEqual(dgs.count(), 1)
        self.assertEqual(dgs[0].num_upvotes, 1)
        self.assertEqual(dgs[0].num_downvotes, 1)
        self.assertEqual(dgs[0].num_users, 2)
        self.assertEqual(dgs[0].num_users_added, 2)


    @override_settings(ASKBOT_ANALYTICS_EMAIL_DOMAIN_ORGANIZATIONS_ENABLED=True)
    def test_question_visits(self):
        """Tests the number of questions viewed"""
        time1 = '2024-02-29 12:15:00'
        with time_machine.travel(time1):
            user1, session1 = self.register_user('user1@test.com')
            user2, session2 = self.register_user('user2@test.com')
            question = self.post_question(user=user1)
            session1.touch()
            session2.touch()
            self.mock_visit_question(user1, question)
            self.mock_visit_question(user2, question)

        call_command('askbot_create_per_email_domain_groups')

        time2 = '2024-02-29 13:15:00'
        with time_machine.travel(time2):
            call_command('askbot_compile_analytics')

        hus = HourlyUserSummary.objects.all() # pylint: disable=no-member
        self.assertEqual(hus.count(), 2)
        self.assertEqual(hus[0].question_views, 1)
        self.assertEqual(hus[1].question_views, 1)

        hgs = HourlyGroupSummary.objects.all() # pylint: disable=no-member
        self.assertEqual(hgs.count(), 1)
        self.assertEqual(hgs[0].question_views, 2)

        time3 = '2024-03-01 12:00:00'
        with time_machine.travel(time3):
            call_command('askbot_compile_analytics')

        dus = DailyUserSummary.objects.all() # pylint: disable=no-member
        self.assertEqual(dus.count(), 2)
        self.assertEqual(dus[0].question_views, 1)
        self.assertEqual(dus[1].question_views, 1)

        dgs = DailyGroupSummary.objects.all() # pylint: disable=no-member
        self.assertEqual(dgs.count(), 1)
        self.assertEqual(dgs[0].question_views, 2)
