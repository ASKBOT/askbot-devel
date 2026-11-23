from askbot.tests.utils import AskbotTestCase
from askbot.utils.functions import decode_jwt
from askbot.views.users import owner_or_moderator_required
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from django.http import HttpResponseRedirect
from unittest.mock import Mock
import urllib.request, urllib.parse, urllib.error
import urllib.parse

class UserViewsTests(AskbotTestCase):

    def test_owner_or_mod_required_passes_url_parameters(self):
        @owner_or_moderator_required
        def mock_view(request, user, context):
            return None

        request = Mock(spec=('path', 'POST', 'user', 'method'))
        request.method = "POST"
        request.user = AnonymousUser()
        request.POST = {'abra': 'cadabra', 'foo': 'bar'}
        request.path = '/some/path/'
        user = self.create_user('user')
        response = mock_view(request, user, {})
        self.assertEqual(isinstance(response, HttpResponseRedirect), True)

        url = response['location']
        parsed_url = urllib.parse.urlparse(url)

        self.assertEqual(parsed_url.path, reverse('user_signin'))

        next_jwt = dict(urllib.parse.parse_qsl(parsed_url.query))['next']
        next_url = decode_jwt(next_jwt).get('next_url')
        parsed_url = urllib.parse.urlparse(next_url)

        self.assertEqual(parsed_url.path, request.path)

        query = dict(urllib.parse.parse_qsl(parsed_url.query))
        self.assertEqual(set(query.keys()), set(['foo', 'abra']))
        self.assertEqual(set(query.values()), set(['bar', 'cadabra']))
        self.assertEqual(query['abra'], 'cadabra')
