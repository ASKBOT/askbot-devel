"""Settings for LDAP login for Askbot"""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import EXTERNAL_SERVICES
from askbot.deps import livesettings
from django.utils.translation import ugettext_lazy as _

LDAP_SETTINGS = livesettings.ConfigurationGroup(
                    'LDAP_SETTINGS',
                    _('LDAP login configuration'),
                    super_group = EXTERNAL_SERVICES
                )

settings.register(
    livesettings.BooleanValue(
        LDAP_SETTINGS,
        'USE_LDAP_FOR_PASSWORD_LOGIN',
        description=_('Use LDAP authentication for the password login'),
        defaut=False
    )
)

settings.register(
    livesettings.BooleanValue(
        LDAP_SETTINGS,
        'LDAP_AUTOCREATE_USERS',
        description = _('Automatically create user accounts when possible'),
        default = False,
        help_text = _(
            'Potentially reduces number of steps in the registration process '
            'but can expose personal information, e.g. when LDAP login name is '
            'the same as email address or real name.'
        )
    )
)

LDAP_PROTOCOL_VERSION_CHOICES = (
    ('3', _('Version 3')),
    ('2', _('Version 2 (insecure and deprecated)!!!'))
)

settings.register(
    livesettings.StringValue(
        LDAP_SETTINGS,
        'LDAP_PROTOCOL_VERSION',
        default = '3',
        choices = LDAP_PROTOCOL_VERSION_CHOICES,
        description = _('LDAP protocol version'),
        help_text = _(
            'Note that Version 2 protocol is not secure!!! '
            'Do not use it on unprotected network.'
        )
    )
)

settings.register(
    livesettings.StringValue(
        LDAP_SETTINGS,
        'LDAP_URL',
        description=_('LDAP URL'),
        default="ldap://<host>:<port>"
    )
)

settings.register(
    livesettings.StringValue(
        LDAP_SETTINGS,
        'LDAP_ENCODING',
        description = _('LDAP encoding'),
        default = 'utf-8',
        help_text = _(
            'This value in almost all cases is "utf-8". '
            'Change it if yours is different. '
            'This field is required'
        )
    )
)

settings.register(
    livesettings.StringValue(
        LDAP_SETTINGS,
        'LDAP_BASE_DN',
        description=_('Base DN (distinguished name)'),
        default = '',
        help_text = _(
            'Usually base DN mirrors domain name of your organization, '
            'e.g. "dn=example,dn=com" when your site url is "example.com". '
            'This value is the "root" address of your LDAP directory.'
        )
    )
)

settings.register(
    livesettings.StringValue(
        LDAP_SETTINGS,
        'LDAP_USER_FILTER_TEMPLATE',
        description = _('User search filter template'),
        default = '(%s=%s)',
        help_text = _(
            'Python string format template, must have two string placeholders, '
            'which should be left in the intact format. '
            'First placeholder will be used for the user id field name, '
            'and the second - for the user id value. '
            'The template can be extended to match schema of your '
            'LDAP directory.'
        )
    )
)

settings.register(
    livesettings.StringValue(
        LDAP_SETTINGS,
        'LDAP_LOGIN_NAME_FIELD',
        description = _('UserID/login field'),
        default = 'uid',
        help_text = _(
            'This field is required. '
            'For Microsoft Active Directory this value usually '
            'is "sAMAccountName".'
        )
    )
)

settings.register(
    livesettings.StringValue(
        LDAP_SETTINGS,
        'LDAP_COMMON_NAME_FIELD',
        description=_('"Common Name" field'),
        help_text=_(
            'Common name is a formal or informal name '
            'of a person, can be blank. '
            'Use it only if surname and given names are not '
            'available.'
        ),
        default = 'cn'
    )
)

COMMON_NAME_FIELD_FORMAT_CHOICES = (
    ('first,last', _('First name, Last name')),
    ('last,first', _('Last name, First name')),
)

settings.register(
    livesettings.StringValue(
        LDAP_SETTINGS,
        'LDAP_COMMON_NAME_FIELD_FORMAT',
        description = _('"Common Name" field format'),
        default = 'first,last',
        choices = COMMON_NAME_FIELD_FORMAT_CHOICES,
        help_text = _('Use this only if "Common Name" field is used.')
    )
)

settings.register(
    livesettings.StringValue(
        LDAP_SETTINGS,
        'LDAP_GIVEN_NAME_FIELD',
        description = _('Given (First) name'),
        default = 'givenName',
        help_text = _('This field can be blank')
    )
)

settings.register(
    livesettings.StringValue(
        LDAP_SETTINGS,
        'LDAP_SURNAME_FIELD',
        description = _('Surname (last) name'),
        default = 'sn',
        help_text = _('This field can be blank')
    )
)

settings.register(
    livesettings.StringValue(
        LDAP_SETTINGS,
        'LDAP_EMAIL_FIELD',
        description = _('LDAP Server EMAIL field name'),
        default = 'mail',
        help_text = _('This field is required')
    )
)

# May be necessary, but not handled properly.
# --> Commenting out until handled properly in backends.ldap_authenticate()
#settings.register(
#    livesettings.StringValue(
#        LDAP_SETTINGS,
#        'LDAP_PROXYDN',
#        description=_('LDAP PROXY DN'),
#        default=""
#    )
#)
#
#settings.register(
#    livesettings.StringValue(
#        LDAP_SETTINGS,
#        'LDAP_PROXYDN_PASSWORD',
#        description=_('LDAP PROXY DN Password'),
#        defalut="",
#    )
#)
