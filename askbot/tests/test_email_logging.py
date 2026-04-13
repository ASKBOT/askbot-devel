"""Tests for email send logging."""
import os
import tempfile
from unittest.mock import patch

from django.test import TestCase, override_settings

from askbot.mail import _log_email_sent


class EmailLoggingTests(TestCase):
    """Tests for _log_email_sent()."""

    def test_no_setting_noop(self):
        """No EMAIL_LOG_FILE setting means no file I/O."""
        with override_settings(**{'EMAIL_LOG_FILE': None}):
            # Should not raise and not create any files
            _log_email_sent('Test subject', ['user@example.com'])

    def test_writes_log_entry(self):
        """Log file should contain subject and recipient."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log',
                                         delete=False) as f:
            log_path = f.name
        try:
            with self.settings(EMAIL_LOG_FILE=log_path):
                _log_email_sent('Hello world', ['alice@example.com'])
            with open(log_path) as f:
                contents = f.read()
            self.assertIn('subject=Hello world', contents)
            self.assertIn('to=alice@example.com', contents)
        finally:
            os.unlink(log_path)

    def test_multiple_recipients(self):
        """Multiple recipients should be comma-separated."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log',
                                         delete=False) as f:
            log_path = f.name
        try:
            with self.settings(EMAIL_LOG_FILE=log_path):
                _log_email_sent('Multi', ['a@example.com', 'b@example.com'])
            with open(log_path) as f:
                contents = f.read()
            self.assertIn('to=a@example.com,b@example.com', contents)
        finally:
            os.unlink(log_path)

    def test_file_error_silenced(self):
        """IOError when writing log should not propagate."""
        with self.settings(EMAIL_LOG_FILE='/nonexistent/dir/email.log'):
            # Should not raise
            _log_email_sent('Test', ['user@example.com'])
