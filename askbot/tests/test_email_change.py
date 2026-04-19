"""Tests for email change verification."""
import datetime
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.utils import timezone

from askbot.tests.utils import AskbotTestCase, with_settings
from askbot.views.users import set_new_email, verify_email_change
from askbot.deps.django_authopenid.models import UserEmailVerifier


class SetNewEmailTests(AskbotTestCase):
    """Tests for set_new_email()."""

    def setUp(self):
        self.user = self.create_user('emailuser')

    @with_settings(EMAIL_VALIDATION_REQUIRED=True)
    def test_same_email_noop(self):
        """Setting email to the same value should do nothing."""
        original_email = self.user.email
        count_before = UserEmailVerifier.objects.count()
        set_new_email(self.user, original_email, nomessage=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)
        self.assertEqual(UserEmailVerifier.objects.count(), count_before)

    @with_settings(EMAIL_VALIDATION_REQUIRED=False)
    def test_immediate_change_when_disabled(self):
        """Without verification, email should change immediately."""
        set_new_email(self.user, 'new@example.com', nomessage=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new@example.com')
        self.assertFalse(self.user.email_isvalid)

    @with_settings(EMAIL_VALIDATION_REQUIRED=True)
    @patch('askbot.mail.messages.EmailChangeVerification')
    def test_verification_when_enabled(self, mock_email_cls):
        """With verification enabled, email should NOT change yet."""
        mock_email_cls.return_value.send = lambda recipients: None
        original_email = self.user.email

        set_new_email(self.user, 'new@example.com', nomessage=True)

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)  # unchanged
        # Verifier should have been created
        self.assertTrue(UserEmailVerifier.objects.exists())


class VerifyEmailChangeTests(AskbotTestCase):
    """Tests for verify_email_change() view."""

    def setUp(self):
        self.user = self.create_user('verifyuser')
        self.factory = RequestFactory()

    def _make_request(self, key=None):
        url = '/'
        if key:
            url = '/?validation_code=' + key
        request = self.factory.get(url)
        request.user = self.user
        return request

    def test_no_key_redirects(self):
        """Missing validation_code should redirect to index."""
        request = self._make_request()
        response = verify_email_change(request)
        self.assertEqual(response.status_code, 302)

    def test_valid_key_changes_email(self):
        """Valid key should update email and mark it valid."""
        from askbot.utils.functions import generate_random_key

        key = generate_random_key()
        verifier = UserEmailVerifier(key=key)
        verifier.value = {
            'user_id': self.user.id,
            'new_email': 'verified@example.com',
            'action': 'change_email',
        }
        verifier.save()

        request = self._make_request(key=key)
        response = verify_email_change(request)

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'verified@example.com')
        self.assertTrue(self.user.email_isvalid)

        verifier.refresh_from_db()
        self.assertTrue(verifier.verified)

    def test_invalid_key_error(self):
        """Invalid key should not change email and should not raise."""
        original_email = self.user.email
        request = self._make_request(key='badkey123')
        response = verify_email_change(request)

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)

    def test_expired_key_error(self):
        """Expired key should not change email."""
        from askbot.utils.functions import generate_random_key

        key = generate_random_key()
        verifier = UserEmailVerifier(key=key)
        verifier.value = {
            'user_id': self.user.id,
            'new_email': 'expired@example.com',
            'action': 'change_email',
        }
        verifier.expires_on = timezone.now() - datetime.timedelta(days=1)
        verifier.save()

        original_email = self.user.email
        request = self._make_request(key=key)
        response = verify_email_change(request)

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)
