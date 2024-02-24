"""authentication backend that takes care of the
multiple login methods supported by the authenticator
application
"""
import datetime
import logging
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings as django_settings
from django.utils import timezone
from django.utils.translation import gettext as _
from askbot.deps.django_authopenid.models import UserAssociation
from askbot.deps.django_authopenid import util
from askbot.deps.django_authopenid.ldap_auth import ldap_authenticate
from askbot.deps.django_authopenid.ldap_auth import ldap_create_user
from askbot.conf import settings as askbot_settings
from askbot.signals import user_registered

LOG = logging.getLogger(__name__)

class AuthBackend:
    """Authenticator's authentication backend class
    for more info, see django doc page:
    http://docs.djangoproject.com/en/dev/topics/auth/#writing-an-authentication-backend

    the reason there is only one class - for simplicity of
    adding this application to a django project - users only need
    to extend the AUTHENTICATION_BACKENDS with a single line

    todo: it is not good to have one giant do all 'authenticate' function
    """
    def __init__(self, *args, **kwargs):
        self.login_providers = util.get_enabled_login_providers()
        super().__init__(*args, **kwargs)

    def authenticate(self, request, method=None, provider_name=None, **kwargs):
        """this authentication function supports many login methods"""
        if method == 'password':
            return self.auth_by_password(
                                provider_name,
                                kwargs['username'],
                                kwargs['password'],
                                request
                            )

        elif method == 'ldap':
            return self.auth_by_ldap(kwargs['username'], kwargs['password'], request)

        elif method == 'identifier':
            #methods supporting this are: openid, mozilla-persona, oauth1, oauth2,
            #wordpress_site
            return self.auth_by_identifier(
                                           provider_name,
                                           kwargs['user_identifier']
                                          )

        elif method == 'email_key':
            #with this method we do no use user association
            return self.auth_by_email_key(kwargs['email_key'])

        elif method == 'email':
            return self.auth_by_email(kwargs['email'])

        elif method == 'force':
            return self.get_user(kwargs['user_id'])

        return None
        #raise NotImplementedError('login method "%s" not supported' % method)

    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    def auth_by_password(self, provider_name, username, password, request):
        if provider_name == 'local':
            return self.auth_by_local_password(username, password)
        else:
            user = self.auth_by_external_password(provider_name, username,
                                                  password, request)

        try:
            assoc = UserAssociation.objects.get(
                                        user=user,
                                        provider_name=provider_name
                                    )
        except UserAssociation.DoesNotExist:
            assoc = UserAssociation(user=user, provider_name=provider_name)

        assoc.openid_url = username + '@' + provider_name#has to be this way for external pw logins
        assoc.last_used_timestamp = datetime.datetime.now()
        assoc.save()
        return user

    def auth_by_local_password(self, username, password):
        users = User.objects.filter(username__iexact=username)
        count = users.count()
        if count >= 1:
            user = users[0]
            if count > 1:
                LOG.critical('clashing users for username %s' % username)
            if user.check_password(password):
                return user
            return None

        #try logging in via email address
        email_address = username
        users = User.objects.filter(email__iexact=email_address)
        count = users.count()
        if count >= 1:
            user = users[0]
            if count > 1:
                LOG.critical('clashing users for email %s' % username)
            if user.check_password(password):
                return user
        return None


    def auth_by_external_password(self, provider_name, username, password, request):
        """authenticates by external password
        auto-creates local user account.
        """
        check_pass_func = self.login_providers[provider_name]['check_password']
        if check_pass_func(username, password) == False:
            return None

        try:
            #if have user associated with this username and provider,
            #return the user
            assoc = UserAssociation.objects.get(
                            openid_url=username + '@' + provider_name,
                            provider_name=provider_name
                        )
            return assoc.user
        except UserAssociation.DoesNotExist:
            #race condition here a user with this name may exist
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(password)
                user.save()
                user_registered.send(None, user=user, request=request)
            else:
                #have username collision - so make up a more unique user name
                #bug: - if user already exists with the new username - we are in trouble
                new_username = f'{username}@{provider_name}'
                user = User.objects.create_user(new_username, '', password)
                user_registered.send(None, user=user, request=request)
                message = _(
                    'Welcome! Please set email address (important!) in your '
                    'profile and adjust screen name, if necessary.'
                )
                user.message_set.create(message=message)
            return user

    @classmethod
    def auth_by_email_key(cls, email_key):
        try:
            #todo: add email_key_timestamp field
            #and check key age
            user = User.objects.get(askbot_profile__email_key=email_key)
            user.email_key = None #one time key so delete it
            user.email_isvalid = True
            user.askbot_profile.save()
            return user
        except User.DoesNotExist:
            return None

    @classmethod
    def auth_by_email(cls, email):
        try:
            return User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            LOG.critical(
                ('have more than one user with email %s ' +
                'he/she will not be able to authenticate with ' +
                'the email address in the place of user name') % email
            )
            return None

    @classmethod
    def auth_by_identifier(cls, provider_name, identifier):
        try:
            assoc = UserAssociation.objects.get(
                                    provider_name=provider_name,
                                    openid_url=identifier
                                )
            assoc.update_timestamp()
            return assoc.user
        except UserAssociation.DoesNotExist:
            return None
        except UserAssociation.MultipleObjectsReturned:
            LOG.critical(
                'duplicate user identifier %s for login provider %s',
                identifier, provider_name
            )
            return None

    def auth_by_ldap(self, username, password, request):
        user_info = ldap_authenticate(username, password)
        if user_info['success'] == False:
            return self.auth_by_local_password(username, password)

        #load user by association or maybe auto-create one
        ldap_username = user_info['ldap_username']
        try:
            #todo: provider_name is hardcoded - possible conflict
            assoc = UserAssociation.objects.get(
                                    openid_url=ldap_username + '@ldap',
                                    provider_name='ldap'
                                )
            assoc.update_timestamp()
            return assoc.user
        except UserAssociation.DoesNotExist:
            #email address is required
            if 'email' in user_info and askbot_settings.LDAP_AUTOCREATE_USERS:
                assoc = ldap_create_user(user_info, request)
                return assoc.user
            else:
                return None
