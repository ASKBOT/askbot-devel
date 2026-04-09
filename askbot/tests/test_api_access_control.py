"""Tests for API v1 access control modes."""
from django.test import TestCase
from django.urls import reverse

from askbot.tests.utils import AskbotTestCase, with_settings


class ApiAccessControlTests(AskbotTestCase):
    """Tests for API v1 access control modes."""

    def setUp(self):
        self.poster = self.create_user('poster')
        self.user = self.create_user('testuser')
        self.mod = self.create_user('testmod', status='m')
        self.question = self.post_question(user=self.poster)

    @with_settings(API_V1_ACCESS_MODE='public')
    def test_public_mode_allows_anonymous(self):
        response = self.client.get(reverse('api_v1_info'))
        self.assertEqual(response.status_code, 200)

    @with_settings(API_V1_ACCESS_MODE='authenticated')
    def test_authenticated_mode_blocks_anonymous(self):
        response = self.client.get(reverse('api_v1_info'))
        self.assertEqual(response.status_code, 403)

    @with_settings(API_V1_ACCESS_MODE='authenticated')
    def test_authenticated_mode_allows_logged_in(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('api_v1_info'))
        self.assertEqual(response.status_code, 200)

    @with_settings(API_V1_ACCESS_MODE='disabled')
    def test_disabled_mode_blocks_list_endpoints(self):
        """List endpoints return 404 for everyone, even moderators."""
        self.client.force_login(self.mod)
        for url_name in ('api_v1_info', 'api_v1_users', 'api_v1_questions'):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 404,
                             '%s should be blocked in disabled mode' % url_name)

    @with_settings(API_V1_ACCESS_MODE='disabled')
    def test_disabled_mode_blocks_regular_user_item_endpoints(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('api_v1_question', kwargs={'question_id': self.question.id})
        )
        self.assertEqual(response.status_code, 404)

    @with_settings(API_V1_ACCESS_MODE='disabled')
    def test_disabled_mode_allows_moderator_item_endpoints(self):
        self.client.force_login(self.mod)
        response = self.client.get(
            reverse('api_v1_question', kwargs={'question_id': self.question.id})
        )
        self.assertEqual(response.status_code, 200)

    @with_settings(API_V1_ACCESS_MODE='disabled')
    def test_disabled_mode_blocks_anonymous_item_endpoints(self):
        response = self.client.get(
            reverse('api_v1_question', kwargs={'question_id': self.question.id})
        )
        self.assertEqual(response.status_code, 404)
