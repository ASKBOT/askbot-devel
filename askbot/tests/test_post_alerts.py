"""Tests for post alert emails."""
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings

from askbot import signals
from askbot.post_alerts import (
    _send_post_alert, on_new_question, on_new_answer, on_new_comment, connect
)


def _make_post(post_type='question', text='Test content', title='Test title'):
    """Create a mock post object."""
    post = MagicMock()
    post.post_type = post_type
    post.text = text
    post.thread.title = title
    post.get_absolute_url.return_value = '/question/1/test/'
    return post


def _make_user(username='testuser', email='test@example.com'):
    user = MagicMock()
    user.username = username
    user.email = email
    return user


class PostAlertTests(TestCase):
    """Tests for _send_post_alert()."""

    def test_no_setting_noop(self):
        """No POST_ALERT_EMAIL setting means send_mail is not called."""
        with override_settings():
            # Remove the setting entirely
            with self.settings(POST_ALERT_EMAIL=None):
                with patch('askbot.mail.send_mail') as mock_send:
                    _send_post_alert('question', _make_post(), _make_user())
                    mock_send.assert_not_called()

    @override_settings(POST_ALERT_EMAIL='admin@example.com')
    def test_question_alert(self):
        """Question alert should include title in body."""
        post = _make_post(post_type='question', title='How to test?')
        user = _make_user()
        with patch('askbot.mail.send_mail') as mock_send:
            _send_post_alert('question', post, user)
            mock_send.assert_called_once()
            kwargs = mock_send.call_args[1]
            self.assertIn('question', kwargs['subject_line'])
            self.assertIn('How to test?', kwargs['body_text'])
            self.assertEqual(kwargs['recipient_list'], ['admin@example.com'])

    @override_settings(POST_ALERT_EMAIL='admin@example.com')
    def test_answer_alert(self):
        """Answer alert should be sent with answer info."""
        post = _make_post(post_type='answer')
        user = _make_user()
        with patch('askbot.mail.send_mail') as mock_send:
            _send_post_alert('answer', post, user)
            mock_send.assert_called_once()
            self.assertIn('answer', mock_send.call_args[1]['subject_line'])

    @override_settings(POST_ALERT_EMAIL='admin@example.com')
    def test_comment_alert(self):
        """Comment alert should be sent."""
        post = _make_post(post_type='comment')
        user = _make_user()
        with patch('askbot.mail.send_mail') as mock_send:
            _send_post_alert('comment', post, user)
            mock_send.assert_called_once()
            self.assertIn('comment', mock_send.call_args[1]['subject_line'])

    @override_settings(POST_ALERT_EMAIL='admin@example.com')
    def test_exception_caught(self):
        """Exceptions from send_mail should not propagate."""
        post = _make_post()
        user = _make_user()
        with patch('askbot.mail.send_mail',
                   side_effect=Exception('SMTP error')):
            # Should not raise
            _send_post_alert('question', post, user)

    def test_connect_wires_signals(self):
        """connect() should register receivers on the correct signals."""
        # Disconnect first to avoid duplicate connections
        signals.new_question_posted.disconnect(on_new_question)
        signals.new_answer_posted.disconnect(on_new_answer)
        signals.new_comment_posted.disconnect(on_new_comment)

        connect()

        receivers_q = [r[1]() for r in signals.new_question_posted.receivers
                       if r[1]() is not None]
        receivers_a = [r[1]() for r in signals.new_answer_posted.receivers
                       if r[1]() is not None]
        receivers_c = [r[1]() for r in signals.new_comment_posted.receivers
                       if r[1]() is not None]

        self.assertIn(on_new_question, receivers_q)
        self.assertIn(on_new_answer, receivers_a)
        self.assertIn(on_new_comment, receivers_c)
