from unittest import TestCase

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase as DjangoTestCase
from django.urls import reverse

from askbot import const
from askbot.conf import settings as askbot_settings
from askbot.deps.django_authopenid.forms import LoginForm
from askbot.deps.django_authopenid.models import UserEmailVerifier
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
                   NEW_REGISTRATIONS_DISABLED=False)
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
                   NEW_REGISTRATIONS_DISABLED=False)
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
