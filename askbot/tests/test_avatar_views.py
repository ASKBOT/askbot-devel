"""Tests for avatar view decorators."""
from unittest.mock import Mock

from django.http import HttpResponse
from django.test import RequestFactory

from askbot.tests.utils import AskbotTestCase
from askbot.views.avatar_views import admin_or_owner_required


class TestAdminOrOwnerRequiredDecorator(AskbotTestCase):
    """Tests for the admin_or_owner_required decorator."""

    def setUp(self):
        self.factory = RequestFactory()
        # First user is automatically made admin by make_admin_if_first_user signal
        self.admin = self.create_user('admin_user')
        self.user1 = self.create_user('user1')
        self.user2 = self.create_user('user2')

        # Create a simple view to decorate
        @admin_or_owner_required
        def dummy_view(request, user_id=None):
            return HttpResponse('OK')

        self.dummy_view = dummy_view

    def test_denies_access_to_other_users_resource(self):
        """Authenticated user cannot access another user's resource."""
        request = self.factory.get('/fake/')
        request.user = self.user1  # user1 is NOT admin (second user created)

        response = self.dummy_view(request, user_id=self.user2.id)

        self.assertEqual(response.status_code, 403)

    def test_allows_owner_access(self):
        """User can access their own resource."""
        request = self.factory.get('/fake/')
        request.user = self.user1

        response = self.dummy_view(request, user_id=self.user1.id)

        self.assertEqual(response.status_code, 200)

    def test_allows_admin_access_to_any_resource(self):
        """Admin can access any user's resource."""
        request = self.factory.get('/fake/')
        request.user = self.admin  # First user is auto-admin

        response = self.dummy_view(request, user_id=self.user2.id)

        self.assertEqual(response.status_code, 200)

    def test_redirects_unauthenticated_user(self):
        """Unauthenticated user is redirected to login."""
        request = self.factory.get('/fake/')
        request.user = Mock()
        request.user.is_authenticated = False

        response = self.dummy_view(request, user_id=self.user1.id)

        self.assertEqual(response.status_code, 302)

    def test_denies_access_with_string_user_id(self):
        """Authenticated user cannot access another user's resource via string ID (URL param)."""
        request = self.factory.get('/fake/')
        request.user = self.user1

        # Simulate how Django URL routing passes user_id as string
        response = self.dummy_view(request, user_id=str(self.user2.id))

        self.assertEqual(response.status_code, 403)

    def test_allows_owner_access_with_string_user_id(self):
        """User can access their own resource even when user_id is a string (URL param)."""
        request = self.factory.get('/fake/')
        request.user = self.user1

        # Simulate how Django URL routing passes user_id as string
        response = self.dummy_view(request, user_id=str(self.user1.id))

        self.assertEqual(response.status_code, 200)
