"""Discourse authentication as described at
https://meta.discourse.org/t/using-discourse-as-a-sso-provider/32974/2"""
import base64
import hmac
import hashlib
import time
import urllib
from django.urls import reverse
from askbot.conf import settings as askbot_settings
from django import forms
from askbot.utils.functions import generate_random_key
from askbot.utils.html import site_url

def sign_payload(data):
    """Returns sha256 signed data string as hex digest"""
    secret = askbot_settings.DISCOURSE_SSO_SECRET
    return hmac.new(secret, data, hashlib.sha256).hexdigest()

def get_sso_login_url(request, success_url):
    """Returns the redirect url for the discourse SSO login"""

    # Generate a random nonce.
    nonce = generate_random_key()
    # Save it temporarily so that you can verify it with returned nonce value
    discourse_login_data = {
        'nonce': nonce,
        'timestamp': time.time(),
        'success_url': success_url
    }
    request.session['discourse_login'] = discourse_login_data
    # Create a new payload with nonce and return url
    # (where the Discourse will redirect user after verification).
    # Payload should look like: nonce=NONCE&return_sso_url=RETURN_URL
    return_url = site_url(reverse('user_complete_discourse_signin'))
    payload = f'nonce={nonce}&return_sso_url={return_url}'
    # Base64 encode the above raw payload. -> BASE64_PAYLOAD
    base64_payload = base64.b64encode(payload)
    # URL encode the above BASE64_PAYLOAD.
    url_encoded_payload = urllib.parse.quote(base64_payload)
    # Generate a HMAC-SHA256 signature from BASE64_PAYLOAD, lower case it -> HEX_SIGNATURE
    hex_signature = sign_payload(base64_payload)

    # Redirect the user to DISCOURSE_ROOT_URL/session/sso_provider?sso=URL_ENCODED_PAYLOAD&sig=HEX_SIGNATURE
    url_template = '{}/session/sso_provider?sso={}&sig={}'
    return url_template.format(askbot_settings.DISCOURSE_SITE_URL, url_encoded_payload, hex_signature)


class DiscourseSsoForm(forms.Form):
    """Verifies the signature"""
    sso = forms.CharField(required=True)
    sig = forms.CharField(required=True)

    def __init__(self, *args, **kwargs):
        self.expected_nonce = kwargs.pop('nonce', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        sso = self.cleaned_data['sso']
        sig = self.cleaned_data['sig']
        sso_sig = sign_payload(sso)
        if sso_sig != sig:
            raise forms.ValidationError('Invalid Discourse SSO response')

        try:
            sso_data = self.get_sso_data()
        except Exception:
            raise forms.ValidationError('Could not read the SSO response data')

        if sso_data['nonce'] != self.expected_nonce:
            raise forms.ValidationError('Unexpected value of nonce')

        return self.cleaned_data

    def get_sso_data(self):
        raw_sso_data = self.cleaned_data['sso']
        urlencoded_sso_data = base64.b64decode(raw_sso_data)
        raw_data = urllib.parse.parse_qs(urlencoded_sso_data)
        # the following keys are expected:
        # ['nonce', 'username', 'name', 'admin', 'moderator',
        #  'return_sso_url', 'avatar_url', 'groups', 'external_id', 'email']
        return {'nonce': raw_data['nonce'][0],
                'username': raw_data['username'][0],
                'name': raw_data['name'][0],
                'email': raw_data['email'][0],
                'external_id': raw_data['external_id'][0],
                'avatar_url': raw_data['avatar_url'][0]}
