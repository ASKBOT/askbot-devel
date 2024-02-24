import logging
from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.forms import EmailField, ValidationError
from askbot.conf import settings as askbot_settings
from askbot.deps.django_authopenid.models import UserAssociation
from askbot.signals import user_registered
from askbot.utils.loading import load_function

LOG = logging.getLogger(__name__)

def split_name(full_name, name_format):
    """splits full name into first and last,
    according to the order given in the name_format parameter"""
    bits = full_name.strip().split()
    if len(bits) == 1:
        bits.push('')
    elif len(bits) == 0:
        bits = ['', '']

    if name_format == 'first,last':
        return bits[0], bits[1]
    elif name_format == 'last,first':
        return bits[1], bits[0]
    else:
        raise ValueError('Unexpected value of name_format')


def ldap_authenticate_default(username, password):
    """
    Authenticate using ldap.
    LDAP parameter setup is described in
    askbot/doc/source/optional-modules.rst
    See section about LDAP.

    returns a dict with keys:

    * first_name
    * last_name
    * ldap_username
    * email (optional only if there is valid email)
    * success - boolean, True if authentication succeeded

    python-ldap must be installed
    http://pypi.python.org/pypi/python-ldap/2.4.6

    NOTE: if you are planning to implement a custom
    LDAP authenticate function (python path to which can
    be provided via setting `ASKBOT_LDAP_AUTHENTICATE`
    setting in the settings.py file) - implement
    the function just like this - accepting user name
    and password and returning dict with the same values.
    The returned dictionary can contain additional values
    that you might find useful.
    """
    import ldap
    user_information = None
    user_info = {}#the return value
    try:
        ldap_session = ldap.initialize(askbot_settings.LDAP_URL)

        #set protocol version
        if askbot_settings.LDAP_PROTOCOL_VERSION == '2':
            ldap_session.protocol_version = ldap.VERSION2
        elif askbot_settings.LDAP_PROTOCOL_VERSION == '3':
            ldap_session.protocol_version = ldap.VERSION3
        else:
            raise NotImplementedError('unsupported version of ldap protocol')

        ldap.set_option(ldap.OPT_REFERRALS, 0)

        #set extra ldap options, if given
        if hasattr(django_settings, 'LDAP_EXTRA_OPTIONS'):
            options = django_settings.LDAP_EXTRA_OPTIONS
            for key, value in options:
                if key.startswith('OPT_'):
                    ldap_key = getattr(ldap, key)
                    ldap.set_option(ldap_key, value)
                else:
                    raise ValueError('Invalid LDAP option %s' % key)

        #add optional "master" LDAP authentication, if required
        master_username = getattr(django_settings, 'LDAP_LOGIN_DN', None)
        master_password = getattr(django_settings, 'LDAP_PASSWORD', None)

        login_name_field = askbot_settings.LDAP_LOGIN_NAME_FIELD
        base_dn = askbot_settings.LDAP_BASE_DN
        login_template = login_name_field + '=%s,' + base_dn
        encoding = askbot_settings.LDAP_ENCODING

        if master_username and master_password:
            ldap_session.simple_bind_s(
                master_username,
                master_password
            )

        user_filter = askbot_settings.LDAP_USER_FILTER_TEMPLATE % (
                        askbot_settings.LDAP_LOGIN_NAME_FIELD,
                        username
                    )

        email_field = askbot_settings.LDAP_EMAIL_FIELD

        get_attrs = [
            email_field,
            login_name_field
            #str(askbot_settings.LDAP_USERID_FIELD)
            #todo: here we have a chance to get more data from LDAP
            #maybe a point for some plugin
        ]

        common_name_field = askbot_settings.LDAP_COMMON_NAME_FIELD.strip()
        given_name_field = askbot_settings.LDAP_GIVEN_NAME_FIELD.strip()
        surname_field = askbot_settings.LDAP_SURNAME_FIELD.strip()

        if given_name_field and surname_field:
            get_attrs.append(given_name_field)
            get_attrs.append(surname_field)
        elif common_name_field:
            get_attrs.append(common_name_field)

        # search ldap directory for user
        user_search_result = ldap_session.search_s(
            askbot_settings.LDAP_BASE_DN,
            ldap.SCOPE_SUBTREE,
            user_filter,
            get_attrs
        )
        if user_search_result: # User found in LDAP Directory
            user_dn = user_search_result[0][0]
            user_information = user_search_result[0][1]
            ldap_session.simple_bind_s(user_dn, password) #raises INVALID_CREDENTIALS
            ldap_session.unbind_s()

            if given_name_field and surname_field:
                last_name = user_information.get(surname_field, [''])[0]
                first_name = user_information.get(given_name_field, [''])[0]
            elif surname_field:
                common_name_format = askbot_settings.LDAP_COMMON_NAME_FIELD_FORMAT
                common_name = user_information.get(common_name_field, [''])[0]
                first_name, last_name = split_name(common_name, common_name_format)

            user_info = {
                'first_name': first_name.decode('utf-8'),
                'last_name': last_name.decode('utf-8'),
                'ldap_username': user_information[login_name_field][0].decode('utf-8'),
                'success': True
            }

            try:
                email = user_information.get(email_field, [''])[0]
                user_info['email'] = EmailField().clean(email)
            except ValidationError:
                user_info['email'] = ''
                pass
        else:
            user_info['success'] = False

    except ldap.INVALID_CREDENTIALS as e:
        user_info['success'] = False
    except ldap.LDAPError as e:
        LOG.error("LDAPError Exception")
        LOG.exception(e)
        user_info['success'] = False
    except Exception as e:
        LOG.error("Unexpected Exception Occurred")
        LOG.exception(e)
        user_info['success'] = False

    return user_info


def ldap_create_user_default(user_info, request):
    """takes the result returned by the :func:`ldap_authenticate`

    and returns a :class:`UserAssociation` object
    """
    # create new user in local db
    user = User()
    user.username = user_info.get('django_username', user_info['ldap_username'])
    user.set_unusable_password()
    user.first_name = user_info['first_name']
    user.last_name = user_info['last_name']
    user.email = user_info['email']
    user.is_staff = False
    user.is_superuser = False
    user.is_active = True
    user.save()
    user_registered.send(None, user=user, request=request)
    LOG.info('Created New User : [{}]'.format(user_info['ldap_username']))

    assoc = UserAssociation()
    assoc.user = user
    assoc.openid_url = user_info['ldap_username'] + '@ldap'
    assoc.provider_name = 'ldap'
    assoc.save()
    return assoc

LDAP_AUTH_FUNC_PATH = getattr(django_settings, 'LDAP_AUTHENTICATE_FUNCTION', None)
if LDAP_AUTH_FUNC_PATH:
    ldap_authenticate = load_function(LDAP_AUTH_FUNC_PATH)
else:
    ldap_authenticate = ldap_authenticate_default

LDAP_CREATE_FUNC_PATH = getattr(django_settings, 'LDAP_CREATE_USER_FUNCTION', None)
if LDAP_CREATE_FUNC_PATH:
    ldap_create_user = load_function(LDAP_CREATE_FUNC_PATH)
else:
    ldap_create_user = ldap_create_user_default
