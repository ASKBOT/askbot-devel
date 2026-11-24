"""Tests for session datetime serialization in record_question_visit."""
import datetime
from unittest.mock import patch

from django.test import RequestFactory, override_settings
from django.utils import timezone
from django.contrib.sessions.backends.db import SessionStore

from askbot.tests.utils import AskbotTestCase


class SessionDatetimeTests(AskbotTestCase):
    """Tests that record_question_visit stores ISO strings in session."""

    def setUp(self):
        self.user = self.create_user('visitor')
        self.question = self.post_question(user=self.user)
        self.factory = RequestFactory()

    def _make_request(self, user=None):
        request = self.factory.get(self.question.get_absolute_url())
        request.user = user or self.user
        request.session = SessionStore()
        return request

    @patch('askbot.models.defer_celery_task')
    @patch('askbot.models.functions.not_a_robot_request', return_value=True)
    def test_stores_iso_string(self, mock_robot, mock_defer):
        """record_question_visit should store ISO string, not datetime."""
        from askbot.models import record_question_visit
        request = self._make_request()

        record_question_visit(request, self.question, timezone.now())

        value = request.session['question_view_times'][str(self.question.id)]
        self.assertIsInstance(value, str)
        # Should be parseable as ISO
        parsed = datetime.datetime.fromisoformat(value)
        self.assertIsNotNone(parsed)

    @patch('askbot.models.defer_celery_task')
    @patch('askbot.models.functions.not_a_robot_request', return_value=True)
    def test_reads_iso_string(self, mock_robot, mock_defer):
        """record_question_visit should handle pre-existing ISO strings."""
        from askbot.models import record_question_visit
        request = self._make_request()

        # Pre-populate session with an ISO string from a past visit
        past = (timezone.now() - datetime.timedelta(hours=1)).isoformat()
        request.session['question_view_times'] = {
            str(self.question.id): past
        }

        # Should not raise
        record_question_visit(request, self.question, timezone.now())

        # Value should be updated — verify it's still a string
        value = request.session['question_view_times'][str(self.question.id)]
        self.assertIsInstance(value, str)
        # Parse both to compare timestamps (new should be >= past)
        parsed_new = datetime.datetime.fromisoformat(value)
        parsed_past = datetime.datetime.fromisoformat(past)
        self.assertGreaterEqual(parsed_new, parsed_past)

    @patch('askbot.models.defer_celery_task')
    @patch('askbot.models.functions.not_a_robot_request', return_value=True)
    def test_first_visit_updates_view_count(self, mock_robot, mock_defer):
        """First visit to a question should pass update_view_count=True."""
        from askbot.models import record_question_visit

        # Use a different user so last_activity_by check passes
        other_user = self.create_user('other_visitor')
        request = self._make_request(user=other_user)

        record_question_visit(request, self.question, timezone.now())

        mock_defer.assert_called_once()
        call_kwargs = mock_defer.call_args[1]['kwargs']
        self.assertTrue(call_kwargs['update_view_count'])


@override_settings(
    SESSION_SERIALIZER='django.contrib.sessions.serializers.JSONSerializer'
)
class SessionReloadTests(AskbotTestCase):
    """Visit times must survive saving and reloading a JSON session."""

    def setUp(self):
        self.author = self.create_user('author')
        self.visitor = self.create_user('visitor')
        self.question = self.post_question(user=self.author)
        self.factory = RequestFactory()

    def _make_request(self, session):
        request = self.factory.get(self.question.get_absolute_url())
        request.user = self.visitor
        request.session = session
        return request

    def _reload(self, session):
        session.save()
        return SessionStore(session_key=session.session_key)

    def _visit(self, session, timestamp=None):
        from askbot.models import record_question_visit
        request = self._make_request(session)
        record_question_visit(request, self.question, timestamp or timezone.now())
        return request

    @staticmethod
    def _last_update_view_count(mock_defer):
        return mock_defer.call_args_list[-1][1]['kwargs']['update_view_count']

    @patch('askbot.models.defer_celery_task')
    @patch('askbot.models.functions.not_a_robot_request', return_value=True)
    def test_repeat_visit_after_session_reload_does_not_count(self, mock_robot, mock_defer):
        session = SessionStore()
        self._visit(session)
        self.assertTrue(self._last_update_view_count(mock_defer))

        self._visit(self._reload(session))
        self.assertFalse(self._last_update_view_count(mock_defer))

    @patch('askbot.models.defer_celery_task')
    @patch('askbot.models.functions.not_a_robot_request', return_value=True)
    def test_visit_marks_session_modified(self, mock_robot, mock_defer):
        first = timezone.now() - datetime.timedelta(hours=1)
        session = SessionStore()
        self._visit(session, first)
        session = self._reload(session)

        second = timezone.now()
        request = self._visit(session, second)
        self.assertTrue(request.session.modified)

        session = self._reload(request.session)
        stored = session['question_view_times'][str(self.question.id)]
        self.assertEqual(datetime.datetime.fromisoformat(stored), second)

    @patch('askbot.models.defer_celery_task')
    @patch('askbot.models.functions.not_a_robot_request', return_value=True)
    def test_new_activity_after_reload_counts_again(self, mock_robot, mock_defer):
        session = SessionStore()
        self._visit(session, timezone.now() - datetime.timedelta(hours=1))
        session = self._reload(session)

        thread = self.question.thread
        thread.last_activity_at = timezone.now()
        thread.last_activity_by = self.author
        thread.save()
        self.question = self.reload_object(self.question)

        self._visit(session)
        self.assertTrue(self._last_update_view_count(mock_defer))

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_question_page_reload_counts_view_once(self):
        self.client.force_login(self.visitor)
        url = self.question.get_absolute_url()
        for _ in range(2):
            response = self.client.get(
                url, HTTP_ACCEPT_LANGUAGE='en', HTTP_USER_AGENT='Mozilla Gecko'
            )
            self.assertEqual(response.status_code, 200)
        thread = self.reload_object(self.question.thread)
        self.assertEqual(thread.view_count, 1)
