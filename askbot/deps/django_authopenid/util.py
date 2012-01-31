# -*- coding: utf-8 -*-
import cgi
import urllib
import functools
import re
from openid.store.interface import OpenIDStore
from openid.association import Association as OIDAssociation
from openid.extensions import sreg
from openid import store as openid_store
import oauth2 as oauth

from django.db.models.query import Q
from django.conf import settings
from django.utils import simplejson
from django.utils.datastructures import SortedDict
from django.utils.translation import ugettext as _
from django.core.exceptions import ImproperlyConfigured

try:
    from hashlib import md5
except:
    from md5 import md5

from askbot.conf import settings as askbot_settings

# needed for some linux distributions like debian
try:
    from openid.yadis import xri
except:
    from yadis import xri

import time, base64, hmac, hashlib, operator, logging
from models import Association, Nonce

__all__ = ['OpenID', 'DjangoOpenIDStore', 'from_openid_response', 'clean_next']

ALLOWED_LOGIN_TYPES = ('password', 'oauth', 'openid-direct', 'openid-username', 'wordpress')

class OpenID:
    def __init__(self, openid_, issued, attrs=None, sreg_=None):
        logging.debug('init janrain openid object')
        self.openid = openid_
        self.issued = issued
        self.attrs = attrs or {}
        self.sreg = sreg_ or {}
        self.is_iname = (xri.identifierScheme(openid_) == 'XRI')
    
    def __repr__(self):
        return '<OpenID: %s>' % self.openid
    
    def __str__(self):
        return self.openid

class DjangoOpenIDStore(OpenIDStore):
    def __init__(self):
        self.max_nonce_age = 6 * 60 * 60 # Six hours
    
    def storeAssociation(self, server_url, association):
        assoc = Association(
            server_url = server_url,
            handle = association.handle,
            secret = base64.encodestring(association.secret),
            issued = association.issued,
            lifetime = association.issued,
            assoc_type = association.assoc_type
        )
        assoc.save()
    
    def getAssociation(self, server_url, handle=None):
        assocs = []
        if handle is not None:
            assocs = Association.objects.filter(
                server_url = server_url, handle = handle
            )
        else:
            assocs = Association.objects.filter(
                server_url = server_url
            )
        if not assocs:
            return None
        associations = []
        for assoc in assocs:
            association = OIDAssociation(
                assoc.handle, base64.decodestring(assoc.secret), assoc.issued,
                assoc.lifetime, assoc.assoc_type
            )
            if association.getExpiresIn() == 0:
                self.removeAssociation(server_url, assoc.handle)
            else:
                associations.append((association.issued, association))
        if not associations:
            return None
        return associations[-1][1]
    
    def removeAssociation(self, server_url, handle):
        assocs = list(Association.objects.filter(
            server_url = server_url, handle = handle
        ))
        assocs_exist = len(assocs) > 0
        for assoc in assocs:
            assoc.delete()
        return assocs_exist

    def useNonce(self, server_url, timestamp, salt):
        if abs(timestamp - time.time()) > openid_store.nonce.SKEW:
            return False
        
        query = [
                Q(server_url__exact=server_url),
                Q(timestamp__exact=timestamp),
                Q(salt__exact=salt),
        ]
        try:
            ononce = Nonce.objects.get(reduce(operator.and_, query))
        except Nonce.DoesNotExist:
            ononce = Nonce(
                    server_url=server_url,
                    timestamp=timestamp,
                    salt=salt
            )
            ononce.save()
            return True
        
        ononce.delete()

        return False
   
    def cleanupNonce(self):
        Nonce.objects.filter(timestamp<int(time.time()) - nonce.SKEW).delete()

    def cleanupAssociations(self):
        Association.objects.extra(where=['issued + lifetimeint<(%s)' % time.time()]).delete()

    def getAuthKey(self):
        # Use first AUTH_KEY_LEN characters of md5 hash of SECRET_KEY
        return hashlib.md5(settings.SECRET_KEY).hexdigest()[:self.AUTH_KEY_LEN]
    
    def isDumb(self):
        return False

def from_openid_response(openid_response):
    """ return openid object from response """
    issued = int(time.time())
    sreg_resp = sreg.SRegResponse.fromSuccessResponse(openid_response) \
            or []
    
    return OpenID(
        openid_response.identity_url, issued, openid_response.signed_fields, 
         dict(sreg_resp)
    )

def get_provider_name(openid_url):
    """returns provider name from the openid_url
    """
    openid_str = openid_url
    bits = openid_str.split('/')
    base_url = bits[2] #assume this is base url
    url_bits = base_url.split('.')
    return url_bits[-2].lower()

def use_password_login():
    """password login is activated
    either if USE_RECAPTCHA is false
    of if recaptcha keys are set correctly
    """
    if askbot_settings.SIGNIN_WORDPRESS_SITE_ENABLED:
        return True
    if askbot_settings.USE_RECAPTCHA:
        if askbot_settings.RECAPTCHA_KEY and askbot_settings.RECAPTCHA_SECRET:
            return True
        else:
            logging.critical('if USE_RECAPTCHA == True, set recaptcha keys!!!')
            return False
    else:
        return True

def filter_enabled_providers(data):
    """deletes data about disabled providers from
    the input dictionary
    """
    delete_list = list()
    for provider_key, provider_settings in data.items():
        name = provider_settings['name']
        is_enabled = getattr(askbot_settings, 'SIGNIN_' + name.upper() + '_ENABLED')
        if is_enabled == False:
            delete_list.append(provider_key)

    for provider_key in delete_list:
        del data[provider_key]

    return data

class LoginMethod(object):
    """Helper class to add custom authentication modules
    as plugins for the askbot's version of django_authopenid
    """
    def __init__(self, login_module_path):
        from askbot.utils.loading import load_module
        self.mod = load_module(login_module_path)
        self.mod_path = login_module_path
        self.read_params()

    def get_required_attr(self, attr_name, required_for_what):
        attr_value = getattr(self.mod, attr_name, None)
        if attr_value is None:
            raise ImproperlyConfigured(
                '%s.%s is required for %s' % (
                    self.mod_path,
                    attr_name,
                    required_for_what
                )
            )
        return attr_value

    def read_params(self):
        self.is_major = getattr(self.mod, 'BIG_BUTTON', True)
        if not isinstance(self.is_major, bool):
            raise ImproperlyConfigured(
                'Boolean value expected for %s.BIG_BUTTON' % self.mod_path
            )

        self.order_number = getattr(self.mod, 'ORDER_NUMBER', 1)
        if not isinstance(self.order_number, int):
            raise ImproperlyConfigured(
                'Integer value expected for %s.ORDER_NUMBER' % self.mod_path
            )
            
        self.name = getattr(self.mod, 'NAME', None)
        if self.name is None or not isinstance(self.name, basestring):
            raise ImproperlyConfigured(
                '%s.NAME is required as a string parameter' % self.mod_path
            )
        if not re.search(r'^[a-zA-Z0-9]+$', self.name):
            raise ImproperlyConfigured(
                '%s.NAME must be a string of ASCII letters and digits only'
            )

        self.display_name = getattr(self.mod, 'DISPLAY_NAME', None)
        if self.display_name is None or not isinstance(self.display_name, basestring):
            raise ImproperlyConfigured(
                '%s.DISPLAY_NAME is required as a string parameter' % self.mod_path
            )
        self.extra_token_name = getattr(self.mod, 'EXTRA_TOKEN_NAME', None)
        self.login_type = getattr(self.mod, 'TYPE', None)
        if self.login_type is None or self.login_type not in ALLOWED_LOGIN_TYPES:
            raise ImproperlyConfigured(
                "%s.TYPE must be a string "
                "and the possible values are : 'password', 'oauth', "
                "'openid-direct', 'openid-username'." % self.mod_path
            )
        self.icon_media_path = getattr(self.mod, 'ICON_MEDIA_PATH', None)
        if self.icon_media_path is None:
            raise ImproperlyConfigured(
                '%s.ICON_MEDIA_PATH is required and must be a url '
                'to the image used as login button' % self.mod_path
            )

        self.create_password_prompt = getattr(self.mod, 'CREATE_PASSWORD_PROMPT', None)
        self.change_password_prompt = getattr(self.mod, 'CHANGE_PASSWORD_PROMPT', None)

        if self.login_type == 'password':
            self.check_password_function = self.get_required_attr(
                                                        'check_password',
                                                        'custom password login'
                                                    )
        if self.login_type == 'oauth':
            for_what = 'custom OAuth login'
            self.oauth_consumer_key = self.get_required_attr('OAUTH_CONSUMER_KEY', for_what)
            self.oauth_consumer_secret = self.get_required_attr('OAUTH_CONSUMER_SECRET', for_what)
            self.oauth_request_token_url = self.get_required_attr('OAUTH_REQUEST_TOKEN_URL', for_what)
            self.oauth_access_token_url = self.get_required_attr('OAUTH_ACCESS_TOKEN_URL', for_what)
            self.oauth_authorize_url = self.get_required_attr('OAUTH_AUTHORIZE_URL', for_what)
            self.oauth_get_user_id_function = self.get_required_attr('oauth_get_user_id_function', for_what)

        if self.login_type.startswith('openid'):
            self.openid_endpoint = self.get_required_attr('OPENID_ENDPOINT', 'custom OpenID login')
            if self.login_type == 'openid-username':
                if '%(username)s' not in self.openid_endpoint:
                    msg = 'If OpenID provider requires a username, ' + \
                        'then value of %s.OPENID_ENDPOINT must contain ' + \
                        '%(username)s so that the username can be transmitted to the provider'
                    raise ImproperlyConfigured(msg % self.mod_path)

        self.tooltip_text = getattr(self.mod, 'TOOLTIP_TEXT', None)

    def as_dict(self):
        """returns parameters as dictionary that
        can be inserted into one of the provider data dictionaries
        for the use in the UI"""
        params = (
            'name', 'display_name', 'type', 'icon_media_path',
            'extra_token_name', 'create_password_prompt',
            'change_password_prompt', 'consumer_key', 'consumer_secret',
            'request_token_url', 'access_token_url', 'authorize_url',
            'get_user_id_function', 'openid_endpoint', 'tooltip_text',
            'check_password',
        )
        #some parameters in the class have different names from those
        #in the dictionary
        parameter_map = {
            'type': 'login_type',
            'consumer_key': 'oauth_consumer_key',
            'consumer_secret': 'oauth_consumer_secret',
            'request_token_url': 'oauth_request_token_url',
            'access_token_url': 'oauth_access_token_url',
            'authorize_url': 'oauth_authorize_url',
            'get_user_id_function': 'oauth_get_user_id_function',
            'check_password': 'check_password_function'
        }
        data = dict()
        for param in params:
            attr_name = parameter_map.get(param, param)
            data[param] = getattr(self, attr_name, None)
        if self.login_type == 'password':
            #passwords in external login systems are not changeable
            data['password_changeable'] = False
        return data

def add_custom_provider(func):
    @functools.wraps(func)
    def wrapper():
        providers = func()
        login_module_path = getattr(settings, 'ASKBOT_CUSTOM_AUTH_MODULE', None)
        if login_module_path:
            mod = LoginMethod(login_module_path)
            if mod.is_major != func.is_major:
                return providers#only patch the matching provider set
            providers.insert(mod.order_number - 1, mod.name, mod.as_dict())
        return providers
    return wrapper

def get_enabled_major_login_providers():
    """returns a dictionary with data about login providers
    whose icons are to be shown in large format

    disabled providers are excluded
    
    items of the dictionary are dictionaries with keys:

    * name
    * display_name
    * icon_media_path (relative to /media directory)
    * type (oauth|openid-direct|openid-generic|openid-username|password)

    Fields dependent on type of the login provider type
    ---------------------------------------------------

    Password (type = password) - login provider using login name and password:

    * extra_token_name - a phrase describing what the login name and the
      password are from
    * create_password_prompt - a phrase prompting to create an account
    * change_password_prompt - a phrase prompting to change password

    OpenID (type = openid) - Provider of login using the OpenID protocol

    * openid_endpoint (required for type=openid|openid-username)
      for type openid-username - the string must have %(username)s
      format variable, plain string url otherwise
    * extra_token_name - required for type=openid-username
      describes name of required extra token - e.g. "XYZ user name"

    OAuth2 (type = oauth)

    * request_token_url - url to initiate OAuth2 protocol with the resource
    * access_token_url - url to access users data on the resource via OAuth2
    * authorize_url - url at which user can authorize the app to access a resource
    * authenticate_url - url to authenticate user (lower privilege than authorize)
    * get_user_id_function - a function that returns user id from data dictionary
      containing: response to the access token url & consumer_key
      and consumer secret. The purpose of this function is to hide the differences
      between the ways user id is accessed from the different OAuth providers
    """
    data = SortedDict()

    if use_password_login():
        site_name = askbot_settings.APP_SHORT_NAME
        prompt = _('%(site)s user name and password') % {'site': site_name}
        data['local'] = {
            'name': 'local',
            'display_name': site_name,
            'extra_token_name': prompt,
            'type': 'password',
            'create_password_prompt': _('Create a password-protected account'),
            'change_password_prompt': _('Change your password'),
            'icon_media_path': askbot_settings.LOCAL_LOGIN_ICON,
            'password_changeable': True
        }

    if askbot_settings.FACEBOOK_KEY and askbot_settings.FACEBOOK_SECRET:
        data['facebook'] = {
            'name': 'facebook',
            'display_name': 'Facebook',
            'type': 'facebook',
            'icon_media_path': '/jquery-openid/images/facebook.gif',
        }
    if askbot_settings.TWITTER_KEY and askbot_settings.TWITTER_SECRET:
        data['twitter'] = {
            'name': 'twitter',
            'display_name': 'Twitter',
            'type': 'oauth',
            'request_token_url': 'https://api.twitter.com/oauth/request_token',
            'access_token_url': 'https://api.twitter.com/oauth/access_token',
            'authorize_url': 'https://api.twitter.com/oauth/authorize',
            'authenticate_url': 'https://api.twitter.com/oauth/authenticate',
            'get_user_id_url': 'https://twitter.com/account/verify_credentials.json',
            'icon_media_path': '/jquery-openid/images/twitter.gif',
            'get_user_id_function': lambda data: data['user_id'],
        }
    def get_identica_user_id(data):
        consumer = oauth.Consumer(data['consumer_key'], data['consumer_secret'])
        token = oauth.Token(data['oauth_token'], data['oauth_token_secret'])
        client = oauth.Client(consumer, token=token)
        url = 'https://identi.ca/api/account/verify_credentials.json'
        json = simplejson.loads(content)
        return json['id']
    if askbot_settings.IDENTICA_KEY and askbot_settings.IDENTICA_SECRET:
        data['identi.ca'] = {
            'name': 'identi.ca',
            'display_name': 'identi.ca',
            'type': 'oauth',
            'request_token_url': 'https://identi.ca/api/oauth/request_token',
            'access_token_url': 'https://identi.ca/api/oauth/access_token',
            'authorize_url': 'https://identi.ca/api/oauth/authorize',
            'authenticate_url': 'https://identi.ca/api/oauth/authorize',
            'icon_media_path': '/jquery-openid/images/identica.png',
            'get_user_id_function': get_identica_user_id,
        }
    def get_linked_in_user_id(data):
        consumer = oauth.Consumer(data['consumer_key'], data['consumer_secret'])
        token = oauth.Token(data['oauth_token'], data['oauth_token_secret'])
        client = oauth.Client(consumer, token=token)
        url = 'https://api.linkedin.com/v1/people/~:(first-name,last-name,id)'
        response, content = client.request(url, 'GET')
        if response['status'] == '200':
            id_re = re.compile(r'<id>([^<]+)</id>')
            matches = id_re.search(content)
            if matches:
                return matches.group(1)
        raise OAuthError()

    if askbot_settings.SIGNIN_WORDPRESS_SITE_ENABLED and askbot_settings.WORDPRESS_SITE_URL:
        data['wordpress_site'] = {
            'name': 'wordpress_site',
            'display_name': 'Self hosted wordpress blog', #need to be added as setting.
            'icon_media_path': askbot_settings.WORDPRESS_SITE_ICON,
            'type': 'wordpress_site',
        }
    if askbot_settings.LINKEDIN_KEY and askbot_settings.LINKEDIN_SECRET:
        data['linkedin'] = {
            'name': 'linkedin',
            'display_name': 'LinkedIn',
            'type': 'oauth',
            'request_token_url': 'https://api.linkedin.com/uas/oauth/requestToken',
            'access_token_url': 'https://api.linkedin.com/uas/oauth/accessToken',
            'authorize_url': 'https://www.linkedin.com/uas/oauth/authorize',
            'authenticate_url': 'https://www.linkedin.com/uas/oauth/authenticate',
            'icon_media_path': '/jquery-openid/images/linkedin.gif',
            'get_user_id_function': get_linked_in_user_id
        }
    data['google'] = {
        'name': 'google',
        'display_name': 'Google',
        'type': 'openid-direct',
        'icon_media_path': '/jquery-openid/images/google.gif',
        'openid_endpoint': 'https://www.google.com/accounts/o8/id',
    }
    data['yahoo'] = {
        'name': 'yahoo',
        'display_name': 'Yahoo',
        'type': 'openid-direct',
        'icon_media_path': '/jquery-openid/images/yahoo.gif',
        'tooltip_text': _('Sign in with Yahoo'),
        'openid_endpoint': 'http://yahoo.com',
    }
    data['aol'] = {
        'name': 'aol',
        'display_name': 'AOL',
        'type': 'openid-username',
        'extra_token_name': _('AOL screen name'),
        'icon_media_path': '/jquery-openid/images/aol.gif',
        'openid_endpoint': 'http://openid.aol.com/%(username)s'
    }
    data['openid'] = {
        'name': 'openid',
        'display_name': 'OpenID',
        'type': 'openid-generic',
        'extra_token_name': _('OpenID url'),
        'icon_media_path': '/jquery-openid/images/openid.gif',
        'openid_endpoint': None,
    }
    return filter_enabled_providers(data)
get_enabled_major_login_providers.is_major = True
get_enabled_major_login_providers = add_custom_provider(get_enabled_major_login_providers)

def get_enabled_minor_login_providers():
    """same as get_enabled_major_login_providers
    but those that are to be displayed with small buttons

    disabled providers are excluded

    structure of dictionary values is the same as in get_enabled_major_login_providers
    """
    data = SortedDict()
    #data['myopenid'] = {
    #    'name': 'myopenid',
    #    'display_name': 'MyOpenid',
    #    'type': 'openid-username',
    #    'extra_token_name': _('MyOpenid user name'),
    #    'icon_media_path': '/jquery-openid/images/myopenid-2.png',
    #    'openid_endpoint': 'http://%(username)s.myopenid.com'
    #}
    data['flickr'] = {
        'name': 'flickr',
        'display_name': 'Flickr',
        'type': 'openid-username',
        'extra_token_name': _('Flickr user name'),
        'icon_media_path': '/jquery-openid/images/flickr.png',
        'openid_endpoint': 'http://flickr.com/%(username)s/'
    }
    data['technorati'] = {
        'name': 'technorati',
        'display_name': 'Technorati',
        'type': 'openid-username',
        'extra_token_name': _('Technorati user name'),
        'icon_media_path': '/jquery-openid/images/technorati-1.png',
        'openid_endpoint': 'http://technorati.com/people/technorati/%(username)s/'
    }
    data['wordpress'] = {
        'name': 'wordpress',
        'display_name': 'WordPress',
        'type': 'openid-username',
        'extra_token_name': _('WordPress blog name'),
        'icon_media_path': '/jquery-openid/images/wordpress.png',
        'openid_endpoint': 'http://%(username)s.wordpress.com'
    }
    data['blogger'] = {
        'name': 'blogger',
        'display_name': 'Blogger',
        'type': 'openid-username',
        'extra_token_name': _('Blogger blog name'),
        'icon_media_path': '/jquery-openid/images/blogger-1.png',
        'openid_endpoint': 'http://%(username)s.blogspot.com'
    }
    data['livejournal'] = {
        'name': 'livejournal',
        'display_name': 'LiveJournal',
        'type': 'openid-username',
        'extra_token_name': _('LiveJournal blog name'),
        'icon_media_path': '/jquery-openid/images/livejournal-1.png',
        'openid_endpoint': 'http://%(username)s.livejournal.com'
    }
    data['claimid'] = {
        'name': 'claimid',
        'display_name': 'ClaimID',
        'type': 'openid-username',
        'extra_token_name': _('ClaimID user name'),
        'icon_media_path': '/jquery-openid/images/claimid-0.png',
        'openid_endpoint': 'http://claimid.com/%(username)s/'
    }
    data['vidoop'] = {
        'name': 'vidoop',
        'display_name': 'Vidoop',
        'type': 'openid-username',
        'extra_token_name': _('Vidoop user name'),
        'icon_media_path': '/jquery-openid/images/vidoop.png',
        'openid_endpoint': 'http://%(username)s.myvidoop.com/'
    }
    data['verisign'] = {
        'name': 'verisign',
        'display_name': 'Verisign',
        'type': 'openid-username',
        'extra_token_name': _('Verisign user name'),
        'icon_media_path': '/jquery-openid/images/verisign-2.png',
        'openid_endpoint': 'http://%(username)s.pip.verisignlabs.com/'
    }
    return filter_enabled_providers(data)
get_enabled_minor_login_providers.is_major = False
get_enabled_minor_login_providers = add_custom_provider(get_enabled_minor_login_providers)

def have_enabled_federated_login_methods():
    providers = get_enabled_major_login_providers()
    providers.update(get_enabled_minor_login_providers())
    provider_types = [provider['type'] for provider in providers.values()]
    for provider_type in provider_types:
        if provider_type.startswith('openid') or provider_type == 'oauth':
            return True
    return False

def get_enabled_login_providers():
    """return all login providers in one sorted dict
    """
    data = get_enabled_major_login_providers()
    data.update(get_enabled_minor_login_providers())
    return data

def set_login_provider_tooltips(provider_dict, active_provider_names = None):
    """adds appropriate tooltip_text field to each provider
    record, if second argument is None, then tooltip is of type
    signin with ..., otherwise it's more elaborate - 
    depending on the type of provider and whether or not it's one of 
    currently used
    """
    for provider in provider_dict.values():
        if active_provider_names:
            if provider['name'] in active_provider_names:
                if provider['type'] == 'password':
                    tooltip = _('Change your %(provider)s password') % \
                                {'provider': provider['display_name']}
                else:
                    tooltip = _(
                        'Click to see if your %(provider)s '
                        'signin still works for %(site_name)s'
                    ) % {
                        'provider': provider['display_name'],
                        'site_name': askbot_settings.APP_SHORT_NAME
                    }
            else:
                if provider['type'] == 'password':
                    tooltip = _(
                            'Create password for %(provider)s'
                        ) % {'provider': provider['display_name']}
                else:
                    tooltip = _(
                        'Connect your %(provider)s account '
                        'to %(site_name)s'
                    ) % {
                        'provider': provider['display_name'],
                        'site_name': askbot_settings.APP_SHORT_NAME
                    }
        else:
            if provider['type'] == 'password':
                tooltip = _(
                        'Signin with %(provider)s user name and password'
                    ) % {
                        'provider': provider['display_name'],
                        'site_name': askbot_settings.APP_SHORT_NAME
                    }
            else:
                tooltip = _(
                        'Sign in with your %(provider)s account'
                    ) % {'provider': provider['display_name']}
        provider['tooltip_text'] = tooltip


def get_oauth_parameters(provider_name):
    """retrieves OAuth protocol parameters
    from hardcoded settings and adds some
    from the livesettings

    because this function uses livesettings
    it should not be called at compile time
    otherwise there may be strange errors
    """
    providers = get_enabled_login_providers()
    data = providers[provider_name]
    if data['type'] != 'oauth':
        raise ValueError('oauth provider expected, %s found' % data['type'])

    if provider_name == 'twitter':
        consumer_key = askbot_settings.TWITTER_KEY
        consumer_secret = askbot_settings.TWITTER_SECRET
    elif provider_name == 'linkedin':
        consumer_key = askbot_settings.LINKEDIN_KEY
        consumer_secret = askbot_settings.LINKEDIN_SECRET
    elif provider_name == 'identi.ca':
        consumer_key = askbot_settings.IDENTICA_KEY
        consumer_secret = askbot_settings.IDENTICA_SECRET
    else:
        raise ValueError('sorry, only linkedin and twitter oauth for now')

    data['consumer_key'] = consumer_key
    data['consumer_secret'] = consumer_secret

    return data


class OAuthError(Exception):
    """Error raised by the OAuthConnection class
    """
    pass


class OAuthConnection(object):
    """a simple class wrapping oauth2 library
    """

    def __init__(self, provider_name, callback_url = None):
        """initializes oauth connection
        """
        self.provider_name = provider_name
        self.parameters = get_oauth_parameters(provider_name)
        self.callback_url = callback_url
        self.consumer = oauth.Consumer(
                            self.parameters['consumer_key'],
                            self.parameters['consumer_secret'],
                        )

    def start(self, callback_url = None):
        """starts the OAuth protocol communication and
        saves request token as :attr:`request_token`"""

        if callback_url is None:
            callback_url = self.callback_url
        
        client = oauth.Client(self.consumer)
        request_url = self.parameters['request_token_url']

        if callback_url:
            callback_url = '%s%s' % (askbot_settings.APP_URL, callback_url)
            request_body = urllib.urlencode(dict(oauth_callback=callback_url))

            self.request_token = self.send_request(
                                            client = client,
                                            url = request_url,
                                            method = 'POST',
                                            body = request_body 
                                        )
        else:
            self.request_token = self.send_request(
                                            client,
                                            request_url,
                                            'GET'
                                        )

    def send_request(self, client=None, url=None, method='GET', **kwargs):

        response, content = client.request(url, method, **kwargs)
        if response['status'] == '200':
            return dict(cgi.parse_qsl(content))
        else:
            raise OAuthError('response is %s' % response)

    def get_token(self):
        return self.request_token

    def get_user_id(self, oauth_token = None, oauth_verifier = None):
        """Returns user ID within the OAuth provider system,
        based on ``oauth_token`` and ``oauth_verifier``
        """

        token = oauth.Token(
                    oauth_token['oauth_token'],
                    oauth_token['oauth_token_secret']
                )
        token.set_verifier(oauth_verifier)
        client = oauth.Client(self.consumer, token = token)
        url = self.parameters['access_token_url']
        #there must be some provider-specific post-processing
        data = self.send_request(client = client, url=url, method='GET')
        data['consumer_key'] = self.parameters['consumer_key']
        data['consumer_secret'] = self.parameters['consumer_secret']
        return self.parameters['get_user_id_function'](data)

    def get_auth_url(self, login_only = False):
        """returns OAuth redirect url.
        if ``login_only`` is True, authentication
        endpoint will be used, if available, otherwise authorization
        url (potentially granting full access to the server) will
        be used.

        Typically, authentication-only endpoint simplifies the
        signin process, but does not allow advanced access to the
        content on the OAuth-enabled server
        """

        endpoint_url = self.parameters.get('authorize_url', None)
        if login_only == True:
            endpoint_url = self.parameters.get(
                                        'authenticate_url',
                                        endpoint_url
                                    )
        if endpoint_url is None:
            raise ImproperlyConfigured('oauth parameters are incorrect')

        auth_url =  '%s?oauth_token=%s' % \
                    (
                        endpoint_url,
                        self.request_token['oauth_token'],
                    )

        return auth_url

class FacebookError(Exception):
    """Raised when there's something not right 
    with FacebookConnect
    """
    pass

def urlsafe_b64decode(input):
    length = len(input)
    return base64.urlsafe_b64decode(
        input.ljust(length + length % 4, '=')
    )

def parse_signed_facebook_request(signed_request, secret):
    """
    Parse signed_request given by Facebook (usually via POST),
    decrypt with app secret.

    Arguments:
    signed_request -- Facebook's signed request given through POST
    secret -- Application's app_secret required to decrpyt signed_request

    slightly edited copy from https://gist.github.com/1190267
    """

    if "." in signed_request:
        esig, payload = signed_request.split(".")
    else:
        return {}

    sig = urlsafe_b64decode(str(esig))
    data = simplejson.loads(urlsafe_b64decode(str(payload)))

    if not isinstance(data, dict):
        raise ValueError("Pyload is not a json string!")
        return {}

    if data["algorithm"].upper() == "HMAC-SHA256":
        if hmac.new(str(secret), str(payload), hashlib.sha256).digest() == sig:
            return data
    else:
        raise ValueError("Not HMAC-SHA256 encrypted!")

    return {}

def get_facebook_user_id(request):
    try:
        key = askbot_settings.FACEBOOK_KEY
        fb_cookie = request.COOKIES['fbsr_%s' % key]
        if not fb_cookie:
            raise ValueError('cannot access facebook cookie')

        secret = askbot_settings.FACEBOOK_SECRET
        response = parse_signed_facebook_request(fb_cookie, secret)
        return response['user_id']
    except Exception, e:
        raise FacebookError(e)

def ldap_check_password(username, password):
    import ldap
    try:
        ldap_session = ldap.initialize(askbot_settings.LDAP_URL)
        ldap_session.simple_bind_s(username, password)
        ldap_session.unbind_s()
        return True
    except ldap.LDAPError, e:
        logging.critical(unicode(e))
        return False
