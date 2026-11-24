import time
from unittest import TestCase, mock
from urllib.parse import parse_qs, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.http import HttpResponse
from django.test import TestCase as DjangoTestCase
from django.urls import reverse

from askbot import const
from askbot.conf import settings as askbot_settings
from askbot.deps.django_authopenid.forms import LoginForm
from askbot.deps.django_authopenid.models import UserEmailVerifier
from askbot.deps.django_authopenid.protocols.oidc.protocol import OidcProtocol, get_jwt_payload
from askbot.tests.utils import with_settings


class LoginFormTests(TestCase):

    def test_fail_change_to_short_password(self):
        new_pass = '1'
        data = {
            'login_provider_name': 'local',
            'password_action': 'change_password',
            'new_password': new_pass,
            'new_password_retyped': new_pass
        }
        assert(len(new_pass) < const.PASSWORD_MIN_LENGTH)
        form = LoginForm(data)
        result = form.is_valid()
        #print form.errors
        self.assertFalse(result)
        self.assertEqual(form.initial.get('new_password'), None)
        #self.assertFalse('new_password_retyped' in form.cleaned_data)


class SignupWithPasswordEmailValidationTests(DjangoTestCase):
    """Exercise EMAIL_VALIDATION_REQUIRED toggle in the password signup
    flow (views.py:1338).

    Forces ``BLANK_EMAIL_ALLOWED=False`` (the ambient default and the
    permanent direction — the setting is slated for removal) and forces
    off ``TERMS_CONSENT_REQUIRED``, ``USE_RECAPTCHA``, and
    ``NEW_REGISTRATIONS_DISABLED`` so the minimal POST payload below is
    sufficient regardless of ambient livesettings state in the test DB.
    """

    def _post_signup(self, username, email):
        return self.client.post(
            reverse('user_signup_with_password'),
            {
                'next': '/',
                'username': username,
                'email': email,
                'password1': 'TestPass12345!',
                'password2': 'TestPass12345!',
            },
        )

    @with_settings(EMAIL_VALIDATION_REQUIRED=False,
                   BLANK_EMAIL_ALLOWED=False,
                   TERMS_CONSENT_REQUIRED=False,
                   USE_RECAPTCHA=False,
                   NEW_REGISTRATIONS_DISABLED=False,
                   REGISTRATION_RATE_LIMIT_ENABLED=False)
    def test_validation_off_creates_user_directly(self):
        response = self._post_signup('ua', 'a@example.com')
        # Validation-off path redirects via get_next_url(request)
        # (views.py:1347). Asserting 302 catches a silent form
        # rejection (which would render 200) before the body
        # assertions below could be misleadingly satisfied.
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='ua').exists())
        # No verification email on the fast path.
        self.assertEqual(len(mail.outbox), 0)


    @with_settings(EMAIL_VALIDATION_REQUIRED=True,
                   BLANK_EMAIL_ALLOWED=False,
                   TERMS_CONSENT_REQUIRED=False,
                   USE_RECAPTCHA=False,
                   NEW_REGISTRATIONS_DISABLED=False,
                   REGISTRATION_RATE_LIMIT_ENABLED=False)
    def test_validation_on_delays_user_creation(self):
        response = self._post_signup('ub', 'b@example.com')
        # Validation-on path redirects to verify_email_and_register
        # (views.py:1357-1359). Without this 302 check, a regression
        # that silently re-renders the signup page (HTTP 200) would
        # leave User absent and outbox empty in the same shape these
        # assertions expect — the test would falsely pass.
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response['Location'].startswith(
                reverse('verify_email_and_register')
            )
        )
        # With validation on, the view stashes the registration in a
        # UserEmailVerifier row (views.py:1349 constructs
        # ``UserEmailVerifier(key=...)`` and ``.save()``s it) and does
        # NOT create the user yet. Assert both sides so a regression
        # gives a clear signal rather than failing silently.
        self.assertFalse(User.objects.filter(username='ub').exists())

        # UserEmailVerifier.value is a PickledObjectField (see
        # ``askbot/deps/django_authopenid/models.py:102``) — ORM
        # lookups into the pickled dict won't work. Filter in Python.
        verifiers = [
            v for v in UserEmailVerifier.objects.all()
            if v.value.get('username') == 'ub'
        ]
        self.assertEqual(len(verifiers), 1)
        self.assertEqual(verifiers[0].value.get('email'), 'b@example.com')

        # send_email_key fires on the validation-required path
        # (views.py:1355).
        self.assertEqual(len(mail.outbox), 1)


class OidcProtocolTests(DjangoTestCase):
    """ID token checks of the OIDC protocol, with tokens signed in the test"""
    provider_url = 'https://idp.example.com'
    client_id = 'askbot-client'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        cache.set(f'{self.provider_url}/.well-known/openid-configuration', {
            'authorization_endpoint': f'{self.provider_url}/authorize',
            'jwks_uri': f'{self.provider_url}/keys',
            'token_endpoint': f'{self.provider_url}/token',
        })
        signing_key = mock.Mock(key=self.private_key.public_key())
        patcher = mock.patch('jwt.PyJWKClient.get_signing_key_from_jwt',
                             return_value=signing_key)
        self.get_signing_key = patcher.start()
        self.addCleanup(patcher.stop)

    def make_protocol(self, **kwargs):
        params = {'client_id': self.client_id,
                  'client_secret': 'secret',
                  'provider_url': self.provider_url}
        params.update(kwargs)
        return OidcProtocol(**params)

    def make_claims(self, **overrides):
        now = int(time.time())
        claims = {'iss': self.provider_url,
                  'aud': self.client_id,
                  'sub': 'user-1',
                  'name': 'Jane',
                  'email': 'jane@example.com',
                  'iat': now,
                  'exp': now + 600,
                  'nonce': 'csrf-1'}
        for key, value in overrides.items():
            if value is None:
                claims.pop(key, None)
            else:
                claims[key] = value
        return claims

    def make_token(self, key=None, algorithm='RS256', **overrides):
        return jwt.encode(self.make_claims(**overrides),
                          key or self.private_key,
                          algorithm=algorithm)

    def assertTokenValid(self, token, valid=True):
        self.assertEqual(self.make_protocol().is_id_token_valid(token, 'csrf-1'), valid)

    def test_valid_token(self):
        self.assertTokenValid(self.make_token())

    def test_wrong_audience(self):
        self.assertTokenValid(self.make_token(aud='someone-else'), False)

    def test_audience_list_with_client_id(self):
        self.assertTokenValid(self.make_token(aud=['other', self.client_id]))

    def test_wrong_issuer(self):
        self.assertTokenValid(self.make_token(iss='https://evil.example.com'), False)

    def test_missing_required_claims(self):
        for claim in ('iss', 'aud', 'exp'):
            with self.subTest(claim=claim):
                self.assertTokenValid(self.make_token(**{claim: None}), False)

    def test_expiry_leeway(self):
        now = int(time.time())
        self.assertTokenValid(self.make_token(iat=now - 1000, exp=now - 60))
        self.assertTokenValid(self.make_token(iat=now - 1000, exp=now - 300), False)

    def test_nonce_mismatch(self):
        self.assertTokenValid(self.make_token(nonce='other'), False)

    def test_token_without_nonce(self):
        self.assertTokenValid(self.make_token(nonce=None))

    def test_signed_by_other_key(self):
        self.assertTokenValid(self.make_token(key=self.other_private_key), False)

    def test_symmetric_and_unsigned_tokens_rejected(self):
        self.assertTokenValid(self.make_token(key='x' * 32, algorithm='HS256'), False)
        unsigned_token = jwt.encode(self.make_claims(), None, algorithm='none')
        self.assertTokenValid(unsigned_token, False)

    def test_key_fetch_error(self):
        self.get_signing_key.side_effect = jwt.PyJWKClientError('no keys')
        self.assertTokenValid(self.make_token(), False)

    def test_access_token_checked_against_audience(self):
        oidc = self.make_protocol(audience='api://askbot')
        self.assertTrue(oidc.is_access_token_valid(self.make_token(aud='api://askbot')))
        self.assertFalse(oidc.is_access_token_valid(self.make_token()))

    def test_access_token_signed_by_other_key(self):
        oidc = self.make_protocol(audience='api://askbot')
        token = self.make_token(key=self.other_private_key, aud='api://askbot')
        self.assertFalse(oidc.is_access_token_valid(token))

    def test_get_jwt_payload(self):
        self.assertEqual(get_jwt_payload(self.make_token()), self.make_claims())

    def test_get_authentication_url(self):
        url = self.make_protocol().get_authentication_url('https://askbot.example.com/done',
                                                          csrf_token='csrf-1')
        parts = urlsplit(url)
        self.assertEqual(f'{parts.scheme}://{parts.netloc}{parts.path}',
                         f'{self.provider_url}/authorize')
        query = parse_qs(parts.query)
        self.assertEqual(query['client_id'], [self.client_id])
        self.assertEqual(query['redirect_uri'], ['https://askbot.example.com/done'])
        self.assertEqual(query['nonce'], ['csrf-1'])
        self.assertEqual(query['state'], ['csrf-1'])

    def complete_signin(self, id_token):
        views_module = 'askbot.deps.django_authopenid.protocols.oidc.views'
        oidc = self.make_protocol(authorization_function=lambda claims: True)
        oidc.execute_token_exchange = mock.Mock(return_value={
            'token_type': 'Bearer',
            'id_token': id_token,
            'access_token': self.make_token(),
        })
        session = self.client.session
        session['provider_name'] = 'test-oidc'
        session['auth_csrf_token'] = 'csrf-1'
        session.save()
        with mock.patch(f'{views_module}.get_protocol', return_value=oidc), \
                mock.patch(f'{views_module}.authenticate', return_value=None), \
                mock.patch(f'{views_module}.finalize_generic_signin',
                           return_value=HttpResponse('ok')) as finalize:
            response = self.client.get(reverse('user_complete_oidc_signin'),
                                       {'code': 'abc'})
        return response, finalize

    def test_complete_signin_with_valid_token(self):
        response, finalize = self.complete_signin(self.make_token())
        self.assertEqual(response.status_code, 200)
        finalize.assert_called_once()
        self.assertEqual(finalize.call_args.kwargs['user_identifier'], 'user-1')

    def test_complete_signin_with_invalid_token(self):
        response, finalize = self.complete_signin(self.make_token(aud='someone-else'))
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'ID token is invalid', response.content)
        finalize.assert_not_called()
