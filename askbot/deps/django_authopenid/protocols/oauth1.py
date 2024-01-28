from askbot.utils.html import site_url
from askbot.deps.django_authopenid.exceptions import OAuthError
from askbot.deps.django_authopenid.protocols.base import BaseProtocol
import cgi
from django.core.exceptions import ImproperlyConfigured
import oauth2 as oauth # OAuth1 protocol
import urllib.request, urllib.parse, urllib.error

class OAuth1Provider(BaseProtocol):
    """a simple class wrapping oauth2 library
    Which is actually implementing the Oauth1 protocol (version 1)
    """

    def __init__(self):
        """Override this, according to the template below
        """
        raise NotImplementedError
        #init function must have the following:
        self.name = 'provider-name'
        self.protocol_type = 'oauth'
        self.display_name = 'Display Name'
        self.request_token_url = 'https://example.com/request_token'
        self.access_token_url = 'https://example.com/access_token'
        self.authorize_url = 'https://example.com/authorize'
        self.authenticate_url = 'https://example.com/authenticate'
        self.identify_url = 'https://example.com/identify'
        self.consumer_key = 'consumer-key'
        self.consumer_secret = 'consumer-secret'
        self.icon_media_path = 'https//example.com/button.png'
        self.callback_is_oob = True
        #skip entry of username and email and get the values
        #from the OAuth1 server
        self.one_click_registration = False

    def get_user_id(self):
        """Returns user ID within the OAuth1 provider system,
        based on self.access_token and parameters of provider.

        Must override this as user id is required
        to link remote OAuth server user id with the
        django user account.
        """
        raise NotImplementedError

    def get_user_email(self):
        """Optionally, override this method to read email
        from the OAuth1 server"""
        return ''

    def get_username(self):
        """Optionally, override this method to read username
        from the OAuth1 server"""
        return ''

    @classmethod
    def parse_request_url(cls, url):
        """returns url and the url parameters dict
        """
        if '?' not in url:
            return url, dict()

        url, params = url.split('?')
        if params:
            kv = [v.split('=') for v in params.split('&')]
            if kv:
                #kv must be list of two-element arrays
                params = dict(kv)
            else:
                params = {}
        else:
            params = {}
        return url, params

    @classmethod
    def format_request_params(cls, params):
        #convert to tuple
        params = list(params.items())
        #sort lexicographically by key
        params = sorted(params, key=lambda x: x[0])
        #urlencode the tuples
        return urllib.parse.urlencode(params)

    @classmethod
    def normalize_url_and_params(cls, url, params):
        #if request url contains query string, we split them
        url, url_params = cls.parse_request_url(url)
        #merge parameters with the query parameters in the url
        #NOTE: there may be a collision
        params = params or dict()
        params.update(url_params)
        #put all of the parameters into the request body
        #sorted as specified by the OAuth1 protocol
        encoded_params = cls.format_request_params(params)
        return url, encoded_params

    def start(self, callback_url=None):
        """starts the OAuth protocol communication and
        saves request token as :attr:`request_token`"""

        client = oauth.Client(self.get_consumer())
        request_url = self.request_token_url

        params = dict()
        if self.callback_is_oob:
            params['oauth_callback'] = 'oob' #callback_url
        else:
            params['oauth_callback'] = site_url(callback_url)

        self.request_token = self.send_request(
                                        client=client,
                                        url=request_url,
                                        method='POST',
                                        params=params
                                    )

    def send_request(self, client=None, url=None, method='GET', params=None, **kwargs):
        url, body = self.normalize_url_and_params(url, params)
        response, content = client.request(url, method, body=body, **kwargs)
        if response['status'] == '200':
            parsed_response = dict(cgi.parse_qsl(content))
            #todo: validate parsed response. For now
            #a simple check for the dictionary emptiness
            if parsed_response:
                return parsed_response
            else:
                raise OAuthError(f'error obtaining request token {content}')
        else:
            raise OAuthError(f'response is {response}')

    def get_token(self):
        return self.request_token

    def get_consumer(self):
        return oauth.Consumer(self.consumer_key, self.consumer_secret)

    def get_client(self, oauth_token=None, oauth_verifier=None):
        token = oauth.Token(
                    oauth_token['oauth_token'],
                    oauth_token['oauth_token_secret']
                )
        if oauth_verifier:
            token.set_verifier(oauth_verifier)
        return oauth.Client(self.get_consumer(), token=token)

    def obtain_access_token(self, oauth_token=None, oauth_verifier=None):
        """returns data as returned upon visiting te access_token_url"""
        client = self.get_client(oauth_token, oauth_verifier)
        url = self.access_token_url
        #there must be some provider-specific post-processing
        self.access_token = self.send_request(
                                    client=client,
                                    url=url,
                                    method='POST'
                                )

    def get_auth_url(self, login_only=False):
        """returns OAuth redirect url.
        if ``login_only`` is True, authentication
        endpoint will be used, if available, otherwise authorization
        url (potentially granting full access to the server) will
        be used.

        Typically, authentication-only endpoint simplifies the
        signin process, but does not allow advanced access to the
        content on the OAuth-enabled server
        """
        if login_only == True:
            endpoint_url = self.authenticate_url
        else:
            endpoint_url = self.authorize_url

        endpoint_url, query_params = self.parse_request_url(endpoint_url)
        query_params['oauth_token'] = self.request_token['oauth_token']

        if endpoint_url is None:
            raise ImproperlyConfigured('oauth parameters are incorrect')
        return endpoint_url + '?' + self.format_request_params(query_params)
