"""Tests for session datetime serialization in record_question_visit."""
import datetime
from unittest.mock import patch

from django.test import RequestFactory
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

        value = request.session['question_view_times'][self.question.id]
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
            self.question.id: past
        }

        # Should not raise
        record_question_visit(request, self.question, timezone.now())

        # Value should be updated — verify it's still a string
        value = request.session['question_view_times'][self.question.id]
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
