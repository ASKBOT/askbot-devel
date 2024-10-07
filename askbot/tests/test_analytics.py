from datetime import datetime
import time_machine
from django.test.utils import override_settings
from django.http import HttpRequest
from django.core.management import call_command
from askbot.tests.utils import AskbotTestCase
from askbot import signals
from askbot.models.analytics import Session, Event, HourlyUserSummary, HourlyGroupSummary

class TestAnalytics(AskbotTestCase):

    def register_user(self, email):
        """Registers and logs in the user,
        Creates a session. Sends the registration and login signals.
        Returns the user object and session.
        """
        user = self.create_user(email='test@test.com')
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


    @override_settings(ASKBOT_ANALYTICS_EMAIL_DOMAIN_ORGANIZATIONS_ENABLED=True)
    def test_simple_session(self):
        time1 = '2024-02-29 12:00:00'
        with time_machine.travel(time1):
            user, session = self.register_user('test@test.com')

        self.assertEqual(Session.objects.count(), 1) # pylint: disable=no-member
        self.assertEqual(Event.objects.count(), 2) # pylint: disable=no-member

        time2 = '2024-02-29 12:15:00'
        with time_machine.travel(time2):
            question = self.post_question(user=user)
            session.touch()
            signals.new_question_posted.send(None, question=question)

        time3 = '2024-02-29 12:44:00'
        with time_machine.travel(time3):
            answer = self.post_answer(user=user, question=question)
            session.touch()
            signals.new_answer_posted.send(None, answer=answer)

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
        expected_time_on_site = datetime.strptime(time3, '%Y-%m-%d %H:%M:%S') \
                                - datetime.strptime(time1, '%Y-%m-%d %H:%M:%S')
        self.assertAlmostEqual(hus[0].time_on_site.total_seconds(),
                               expected_time_on_site.total_seconds(),
                               delta=2)
        self.assertAlmostEqual(hgs[0].time_on_site.total_seconds(),
                               expected_time_on_site.total_seconds(),
                               delta=2)
        self.assertEqual(hus[0].num_questions, 1)
        self.assertEqual(hus[0].num_answers, 1)
