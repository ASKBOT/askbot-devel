"""OpenId Connect protocol"""
import asyncio
import logging
import requests
from django.core.cache import cache
from askbot.deps.django_authopenid.protocols.oidc.jwt_verifier import JwtVerifier
from okta_jwt_verifier import JWTUtils

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def get_jwt_payload(token):
    """Returns parsed JWT payload as dict"""
    return JWTUtils.parse_token(token)[1]

class OidcProtocol:
    """Encapsulates the basic api necessary for the authorization flow of the
    OpenId Connect protocol authentication"""
    #pylint: disable=too-many-instance-attributes

    def __init__(self, # pylint: disable=too-many-arguments
                 client_id=None,
                 client_secret=None,
                 provider_url=None,
                 trust_email=False,
                 authorization_function=None,
                 custom_scopes=None,
                 audience=None):
        self.protocol_type = 'oidc'
        self.audience = audience
        self.client_id = client_id
        self.client_secret = client_secret
        self.provider_url = provider_url
        self.authorization_function = authorization_function
        self.custom_scopes = custom_scopes
        self.trust_email = trust_email
        discovery = self.load_discovery_data()
        self.authenticate_url = discovery['authorization_endpoint']
        self.jwks_url = discovery['jwks_uri']
        self.token_url = discovery['token_endpoint']

    def load_discovery_data(self):
        """Returns OIDC discovery data in a dictionary"""
        discovery_url = f'{self.provider_url}/.well-known/openid-configuration'
        discovery_data = cache.get(discovery_url)
        if not discovery_data:
            result = requests.get(discovery_url)
            discovery_data = result.json()
            cache.set(discovery_url, discovery_data)
        return discovery_data


    def get_scopes(self):
        """Merges the default scopes with the custom scopes"""
        scopes = ['openid', 'email', 'profile']
        if self.custom_scopes:
            for scope in self.custom_scopes:
                if scope not in scopes:
                    scopes.append(scope)

        return ' '.join(scopes)


    def get_authentication_url(self, redirect_url, csrf_token=None):
        """Returns url at which OpenId-Connect service starts the user authentication"""
        query_params = {
            'client_id': self.client_id,
            'redirect_uri': redirect_url,
            'scope': self.get_scopes(),
            'nonce': csrf_token,
            'response_type': 'code',
            'response_mode': 'query',
            'state': csrf_token #not sure what it is for
        }
        query_params=requests.compat.urlencode(query_params)
        base_url = self.authenticate_url
        return f"{base_url}?{query_params}"

    def execute_token_exchange(self, code, redirect_url=None):
        """Returns OIDC token exchange result given the code"""
        query_params = {'grant_type': 'authorization_code',
                        'code': code,
                        'redirect_uri': redirect_url}
        query_params = requests.compat.urlencode(query_params)
        response = requests.post(self.token_url,
                                 headers={'Content-Type': 'application/x-www-form-urlencoded'},
                                 data=query_params,
                                 auth=(self.client_id, self.client_secret))
        return response.json()

    def get_user_id(self, id_token):
        payload = get_jwt_payload(id_token)
        return payload['sub']

    def get_username(self, id_token):
        payload = get_jwt_payload(id_token)
        return payload['name']

    def get_email(self, id_token):
        payload = get_jwt_payload(id_token)
        return payload['email']

    def is_user_authorized(self, id_token):
        payload = get_jwt_payload(id_token)
        try:
            return self.authorization_function(payload)
        except Exception as error:
            logging.critical('Error in authorization function: %s', error)
            return False

    def is_access_token_valid(self, access_token):
        """Validates the OIDC access token"""
        jwt_verifier = JwtVerifier(issuer=self.provider_url,
                                   client_id=self.client_id,
                                   jwks_uri=self.jwks_url,
                                   audience=self.audience)
        try:
            loop.run_until_complete(jwt_verifier.verify_access_token(access_token))
            return True
        except Exception: #pylint: disable=broad-except
            return False

    def is_id_token_valid(self, id_token, csrf_token):
        """Validates OIDC id token"""
        jwt_verifier = JwtVerifier(issuer=self.provider_url,
                                   client_id=self.client_id,
                                   jwks_uri=self.jwks_url,
                                   audience=self.audience)
        try:
            loop.run_until_complete(jwt_verifier.verify_id_token(id_token, nonce=csrf_token))
            return True
        except Exception: #pylint: disable=broad-except
            return False
