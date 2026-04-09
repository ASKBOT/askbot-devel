"""Tests for spam defense: Bayesian check and first-post confirmation."""
import datetime
from unittest.mock import patch, MagicMock

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.utils import timezone

from askbot.tests.utils import AskbotTestCase, with_settings
from askbot.views.writers import _check_spam_and_act, _SilentSpamDeletion
from askbot.models.post_confirmation import PostConfirmation


class CheckSpamTests(AskbotTestCase):
    """Tests for _check_spam_and_act()."""

    def setUp(self):
        self.factory = RequestFactory()
        self.watched = self.create_user('watched_spam', status='w')
        self.approved = self.create_user('approved_spam', status='a')

    def _make_request(self, user=None):
        request = self.factory.get('/')
        request.user = user or self.watched
        return request

    @with_settings(SPAM_FILTER_ENABLED=False)
    def test_disabled_allows_all(self):
        """When spam filter is disabled, _check_spam_and_act returns None."""
        request = self._make_request()
        result = _check_spam_and_act(request, self.watched, 'buy viagra now')
        self.assertIsNone(result)

    @with_settings(SPAM_FILTER_ENABLED=True)
    @patch('askbot.spam_checker.bayesian_spam_checker.check_content',
           return_value=(False, False))
    def test_no_spam_allows(self, mock_check):
        """When no spam detected, returns None."""
        request = self._make_request()
        result = _check_spam_and_act(request, self.watched, 'normal text')
        self.assertIsNone(result)

    @with_settings(SPAM_FILTER_ENABLED=True)
    @patch('askbot.spam_checker.bayesian_spam_checker.check_content', return_value=(True, True))
    def test_spam_ham_first_post_watched_held(self, mock_check):
        """Spam+ham, watched user, no prior posts -> PermissionDenied."""
        request = self._make_request()
        with self.assertRaises(PermissionDenied):
            _check_spam_and_act(request, self.watched, 'spam text')

    @with_settings(SPAM_FILTER_ENABLED=True)
    @patch('askbot.spam_checker.bayesian_spam_checker.check_content', return_value=(True, True))
    def test_spam_ham_approved_user_allows(self, mock_check):
        """Spam+ham, user with prior posts -> returns None."""
        self.post_question(user=self.approved)
        request = self._make_request(user=self.approved)
        result = _check_spam_and_act(request, self.approved, 'spam text')
        self.assertIsNone(result)

    @with_settings(SPAM_FILTER_ENABLED=True, BAYESIAN_SPAM_SILENT_DELETE=True)
    @patch('askbot.spam_checker.bayesian_spam_checker.check_content', return_value=(True, False))
    def test_spam_only_silent_delete(self, mock_check):
        """Spam only, watched, silent delete enabled -> user deleted."""
        request = self._make_request()
        user_id = self.watched.id
        with self.assertRaises(_SilentSpamDeletion):
            _check_spam_and_act(request, self.watched, 'buy stuff')
        from django.contrib.auth.models import User
        self.assertFalse(User.objects.filter(id=user_id).exists())

    @with_settings(SPAM_FILTER_ENABLED=True, BAYESIAN_SPAM_SILENT_DELETE=False)
    @patch('askbot.spam_checker.bayesian_spam_checker.check_content', return_value=(True, False))
    def test_spam_only_held(self, mock_check):
        """Spam only, watched, silent delete disabled -> PermissionDenied."""
        request = self._make_request()
        with self.assertRaises(PermissionDenied):
            _check_spam_and_act(request, self.watched, 'buy stuff')


class SendFirstPostConfirmationTests(AskbotTestCase):
    """Tests for _send_first_post_confirmation()."""

    def setUp(self):
        self.factory = RequestFactory()
        self.watched = self.create_user('watched_conf', status='w')
        self.approved = self.create_user('approved_conf', status='a')

    def _make_request(self, user):
        request = self.factory.get('/')
        request.user = user
        return request

    @with_settings(FIRST_POST_EMAIL_CONFIRMATION=False)
    def test_disabled_returns_false(self):
        """When disabled, returns False."""
        from askbot.views.writers import _send_first_post_confirmation
        question = self.post_question(user=self.watched)
        request = self._make_request(self.watched)
        result = _send_first_post_confirmation(request, self.watched, question)
        self.assertFalse(result)

    @with_settings(FIRST_POST_EMAIL_CONFIRMATION=True)
    def test_non_watched_returns_false(self):
        """Approved user should return False."""
        from askbot.views.writers import _send_first_post_confirmation
        question = self.post_question(user=self.approved)
        request = self._make_request(self.approved)
        result = _send_first_post_confirmation(request, self.approved, question)
        self.assertFalse(result)

    @with_settings(FIRST_POST_EMAIL_CONFIRMATION=True)
    def test_has_prior_posts_returns_false(self):
        """Watched user with prior posts should return False."""
        from askbot.views.writers import _send_first_post_confirmation
        prior = self.post_question(user=self.watched, title='prior question')
        new_q = self.post_question(user=self.watched, title='new question')
        request = self._make_request(self.watched)
        result = _send_first_post_confirmation(request, self.watched, new_q)
        self.assertFalse(result)

    @with_settings(FIRST_POST_EMAIL_CONFIRMATION=True)
    @patch('askbot.mail.send_mail')
    def test_first_post_creates_confirmation(self, mock_send):
        """First post by watched user should create PostConfirmation."""
        from askbot.views.writers import _send_first_post_confirmation
        question = self.post_question(user=self.watched)
        request = self._make_request(self.watched)

        with patch('askbot.mail.messages.PostConfirmationEmail'):
            result = _send_first_post_confirmation(
                request, self.watched, question
            )

        self.assertTrue(result)
        question.refresh_from_db()
        self.assertFalse(question.approved)
        self.assertTrue(PostConfirmation.objects.filter(
            user=self.watched, post=question
        ).exists())


class PostConfirmationModelTests(AskbotTestCase):
    """Tests for the PostConfirmation model."""

    def setUp(self):
        self.watched = self.create_user('pc_watched', status='w')
        self.question = self.post_question(user=self.watched)

    def test_auto_expiry_date(self):
        """expires_on should be approximately created_at + 3 days."""
        conf = PostConfirmation(post=self.question, user=self.watched)
        conf.save()
        expected = conf.created_at + datetime.timedelta(days=3)
        diff = abs((conf.expires_on - expected).total_seconds())
        self.assertLess(diff, 1)

    def test_is_expired(self):
        """is_expired should return True after expiry."""
        conf = PostConfirmation(post=self.question, user=self.watched)
        conf.save()

        future = conf.expires_on + datetime.timedelta(seconds=1)
        with patch('askbot.models.post_confirmation.timezone.now',
                   return_value=future):
            self.assertTrue(conf.is_expired)

    @with_settings(FIRST_POST_MODERATE_AFTER_CONFIRMATION=False)
    def test_confirm_approves_post_when_moderation_disabled(self):
        """confirm() should approve the post and promote user."""
        conf = PostConfirmation(post=self.question, user=self.watched)
        conf.save()

        self.question.approved = False
        self.question.save(update_fields=['approved'])

        conf.confirm()

        self.question.refresh_from_db()
        self.assertTrue(self.question.approved)
        self.assertIsNotNone(conf.confirmed_at)

        self.watched.askbot_profile.refresh_from_db()
        self.assertEqual(self.watched.askbot_profile.status, 'a')

    @with_settings(FIRST_POST_MODERATE_AFTER_CONFIRMATION=True)
    def test_confirm_leaves_post_unapproved_when_moderation_enabled(self):
        """confirm() should leave post unapproved when moderation is on."""
        conf = PostConfirmation(post=self.question, user=self.watched)
        conf.save()

        self.question.approved = False
        self.question.save(update_fields=['approved'])

        conf.confirm()

        self.question.refresh_from_db()
        self.assertFalse(self.question.approved)
        self.assertIsNotNone(conf.confirmed_at)

        self.watched.askbot_profile.refresh_from_db()
        self.assertEqual(self.watched.askbot_profile.status, 'w')
