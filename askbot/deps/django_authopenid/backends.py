"""authentication backend that takes care of the
multiple login methods supported by the authenticator
application
"""
import datetime
import logging
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings as django_settings
from django.utils.translation import ugettext as _
from askbot.deps.django_authopenid.models import UserAssociation
from askbot.deps.django_authopenid import util
from askbot.deps.django_authopenid.ldap_auth import ldap_authenticate
from askbot.deps.django_authopenid.ldap_auth import ldap_create_user
from askbot.conf import settings as askbot_settings
from askbot.signals import user_registered

LOG = logging.getLogger(__name__)

class AuthBackend(object):
    """Authenticator's authentication backend class
    for more info, see django doc page:
    http://docs.djangoproject.com/en/dev/topics/auth/#writing-an-authentication-backend

    the reason there is only one class - for simplicity of
    adding this application to a django project - users only need
    to extend the AUTHENTICATION_BACKENDS with a single line

    todo: it is not good to have one giant do all 'authenticate' function
    """

    def authenticate(
                self,
                username = None,#for 'password' and 'ldap'
                password = None,#for 'password' and 'ldap'
                user_id = None,#for 'force'
                provider_name = None,#required with all except email_key
                openid_url = None,
                email_key = None,
                email = None, # used with mozilla-persona method
                oauth_user_id = None,#used with oauth
                facebook_user_id = None,#user with facebook
                wordpress_url = None, # required for self hosted wordpress
                wp_user_id = None, # required for self hosted wordpress
                method = None,#requried parameter
            ):
        """this authentication function supports many login methods
        just which method it is going to use it determined
        from the signature of the function call
        """
        login_providers = util.get_enabled_login_providers()
        assoc = None # UserAssociation not needed for ldap
        if method == 'password':
            if login_providers[provider_name]['type'] != 'password':
                raise ImproperlyConfigured('login provider must use password')
            if provider_name == 'local':
                try:
                    user = User.objects.get(username=username)
                    if not user.check_password(password):
                        return None
                except User.DoesNotExist:
                    try:
                        email_address = username
                        user = User.objects.get(email = email_address)
                        if not user.check_password(password):
                            return None
                    except User.DoesNotExist:
                        return None
                    except User.MultipleObjectsReturned:
                        LOG.critical(
                            ('have more than one user with email %s ' +
                            'he/she will not be able to authenticate with ' +
                            'the email address in the place of user name') % email_address
                        )
                        return None
            else:
                if login_providers[provider_name]['check_password'](username, password):
                    try:
                        #if have user associated with this username and provider,
                        #return the user
                        assoc = UserAssociation.objects.get(
                                        openid_url = username + '@' + provider_name,#a hack - par name is bad
                                        provider_name = provider_name
                                    )
                        return assoc.user
                    except UserAssociation.DoesNotExist:
                        #race condition here a user with this name may exist
                        user, created = User.objects.get_or_create(username = username)
                        if created:
                            user.set_password(password)
                            user.save()
                            user_registered.send(None, user = user)
                        else:
                            #have username collision - so make up a more unique user name
                            #bug: - if user already exists with the new username - we are in trouble
                            new_username = '%s@%s' % (username, provider_name)
                            user = User.objects.create_user(new_username, '', password)
                            user_registered.send(None, user = user)
                            message = _(
                                'Welcome! Please set email address (important!) in your '
                                'profile and adjust screen name, if necessary.'
                            )
                            user.message_set.create(message = message)
                else:
                    return None

            #this is a catch - make login token a little more unique
            #for the cases when passwords are the same for two users
            #from the same provider
            try:
                assoc = UserAssociation.objects.get(
                                            user = user,
                                            provider_name = provider_name
                                        )
            except UserAssociation.DoesNotExist:
                assoc = UserAssociation(
                                    user = user,
                                    provider_name = provider_name
                                )
            assoc.openid_url = username + '@' + provider_name#has to be this way for external pw logins

        elif method == 'openid':
            try:
                assoc = UserAssociation.objects.get(openid_url=openid_url)
                user = assoc.user
            except UserAssociation.DoesNotExist:
                return None
            except UserAssociation.MultipleObjectsReturned:
                logging.critical(
                    'duplicate openid url in the database!!! %s' % openid_url
                )
                return None

        elif method == 'mozilla-persona':
            try:
                assoc = UserAssociation.objects.get(
                                        openid_url=email,
                                        provider_name='mozilla-persona'
                                    )
                return assoc.user
            except UserAssociation.DoesNotExist:
                return None
            except UserAssociation.MultipleObjectsReturned:
                logging.critical(
                    'duplicate user with mozilla persona %s!!!' % email
                )

        elif method == 'email':
            #with this method we do no use user association
            try:
                #todo: add email_key_timestamp field
                #and check key age
                user = User.objects.get(email_key = email_key)
                user.email_key = None #one time key so delete it
                user.email_isvalid = True
                user.save()
                return user
            except User.DoesNotExist:
                return None

        elif method in ('valid_email', 'any_email'):
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return None
            except User.MultipleObjectsReturned:
                LOG.critical(
                    ('have more than one user with email %s ' +
                    'he/she will not be able to authenticate with ' +
                    'the email address in the place of user name') % email_address
                )
                return None

            if method == 'valid_email' and user.email_isvalid == False:
                return None

            return user

        elif method == 'oauth':
            if login_providers[provider_name]['type'] in ('oauth', 'oauth2'):
                try:
                    assoc = UserAssociation.objects.get(
                                                openid_url = oauth_user_id,
                                                provider_name = provider_name
                                            )
                    user = assoc.user
                except UserAssociation.DoesNotExist:
                    return None
            else:
                return None

        elif method == 'facebook':
            try:
                #assert(provider_name == 'facebook')
                assoc = UserAssociation.objects.get(
                                            openid_url = facebook_user_id,
                                            provider_name = 'facebook'
                                        )
                user = assoc.user
            except UserAssociation.DoesNotExist:
                return None

        elif method == 'ldap':
            user_info = ldap_authenticate(username, password)
            if user_info['success'] == False:
                # Maybe a user created internally (django admin user)
                try:
                    user = User.objects.get(username__exact=username)
                    if user.check_password(password):
                        return user
                    else:
                        return None
                except User.DoesNotExist:
                    return None
            else:
                #load user by association or maybe auto-create one
                ldap_username = user_info['ldap_username']
                try:
                    #todo: provider_name is hardcoded - possible conflict
                    assoc = UserAssociation.objects.get(
                                            openid_url = ldap_username + '@ldap',
                                            provider_name = 'ldap'
                                        )
                    user = assoc.user
                except UserAssociation.DoesNotExist:
                    #email address is required
                    if 'email' in user_info and askbot_settings.LDAP_AUTOCREATE_USERS:
                        assoc = ldap_create_user(user_info)
                        user = assoc.user
                    else:
                        return None

        elif method == 'wordpress_site':
            try:
                custom_wp_openid_url = '%s?user_id=%s' % (wordpress_url, wp_user_id)
                assoc = UserAssociation.objects.get(
                                            openid_url = custom_wp_openid_url,
                                            provider_name = 'wordpress_site'
                                            )
                user = assoc.user
            except UserAssociation.DoesNotExist:
                return None
        elif method == 'force':
            return self.get_user(user_id)
        else:
            raise TypeError('only openid and password supported')

        if assoc:
            #update last used time
            assoc.last_used_timestamp = datetime.datetime.now()
            assoc.save()
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @classmethod
    def set_password(cls,
                    user=None,
                    password=None,
                    provider_name=None
                ):
        """generic method to change password of
        any for any login provider that uses password
        and allows the password change function
        """
        login_providers = util.get_enabled_login_providers()
        if login_providers[provider_name]['type'] != 'password':
            raise ImproperlyConfigured('login provider must use password')

        if provider_name == 'local':
            user.set_password(password)
            user.save()
            scrambled_password = user.password + str(user.id)
        else:
            raise NotImplementedError('external passwords not supported')

        try:
            assoc = UserAssociation.objects.get(
                                        user = user,
                                        provider_name = provider_name
                                    )
        except UserAssociation.DoesNotExist:
            assoc = UserAssociation(
                        user = user,
                        provider_name = provider_name
                    )

        assoc.openid_url = scrambled_password
        assoc.last_used_timestamp = datetime.datetime.now()
        assoc.save()
