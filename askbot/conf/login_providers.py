"""
External service key settings
"""
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import LOGIN_USERS_COMMUNICATION
from livesettings import values as livesettings
from askbot.skins import utils as skin_utils
from askbot.utils.loading import module_exists

LOGIN_PROVIDERS = livesettings.ConfigurationGroup(
                    'LOGIN_PROVIDERS',
                    _('Login provider settings'),
                    super_group=LOGIN_USERS_COMMUNICATION
                )

settings.register(
    livesettings.BooleanValue(
        LOGIN_PROVIDERS,
        'TERMS_CONSENT_REQUIRED',
        default=False,
        description=_('Acceptance of terms required at registration'),
        help_text=settings.get_related_settings_info(('FLATPAGES', 'TERMS',
                                                      True))
    )
)

settings.register(
    livesettings.BooleanValue(
        LOGIN_PROVIDERS,
        'SIGNIN_WORDPRESS_SITE_ENABLED',
        default=False,
        description=_('Activate to allow login with self-hosted '
                      'wordpress site'),
        help_text=_('to activate this feature you must fill out the wordpress '
                    'xml-rpc setting bellow')
    )
)

settings.register(
    livesettings.URLValue(
        LOGIN_PROVIDERS,
        'WORDPRESS_SITE_URL',
        default='',
        description=_('Fill it with the wordpress url to the xml-rpc, '
                      'normally http://mysite.com/xmlrpc.php'),
        help_text=_('To enable, go to Settings->Writing->Remote Publishing '
                    'and check the box for XML-RPC')
    )
)

settings.register(
    livesettings.ImageValue(
        LOGIN_PROVIDERS,
        'WORDPRESS_SITE_ICON',
        default='/images/logo.gif',
        description=_('WordPress login button image'),
        url_resolver=skin_utils.get_media_url
    )
)

settings.register(
    livesettings.BooleanValue(
        LOGIN_PROVIDERS,
        'SIGNIN_FEDORA_ENABLED',
        default=False,
        description=_('Enable Fedora OpenID login')
    )
)

settings.register(
    livesettings.BooleanValue(
        LOGIN_PROVIDERS,
        'SIGNIN_CUSTOM_OPENID_ENABLED',
        default=False,
        description=_('Enable custom OpenID login')
    )
)

if module_exists('cas'):
    settings.register(
        livesettings.BooleanValue(
            LOGIN_PROVIDERS,
            'SIGNIN_CAS_ENABLED',
            default=False,
            description=_('Enable CAS authentication')
        )
    )
    settings.register(
        livesettings.StringValue(
            LOGIN_PROVIDERS,
            'CAS_SERVER_URL',
            default='',
            description=_('CAS server url')
        )
    )
    settings.register(
        livesettings.StringValue(
            LOGIN_PROVIDERS,
            'CAS_SERVER_NAME',
            default='CAS Server',
            description=_('CAS server name')
        )
    )
    settings.register(
        livesettings.StringValue(
            LOGIN_PROVIDERS,
            'CAS_PROTOCOL_VERSION',
            default='3',
            choices=(('1', '1'), ('2', '2'), ('3', '3')),
            description=_('CAS protocol version'),
        )
    )
    settings.register(
        livesettings.ImageValue(
            LOGIN_PROVIDERS,
            'CAS_LOGIN_BUTTON',
            default='/images/jquery-openid/cas.png',
            description=_('Upload CAS login icon'),
            url_resolver=skin_utils.get_media_url
        )
    )

"""
    settings.register(
        livesettings.BooleanValue(
            LOGIN_PROVIDERS,
            'CAS_ONE_CLICK_REGISTRATION_ENABLED',
            default=False,
            description=_('CAS - enable one click registration'),
            help_text=string_concat(
                _('Allows skipping the registration page after the CAS authentication.'),
                ' ',
                settings.get_related_settings_info(
                    ('EMAIL', 'BLANK_EMAIL_ALLOWED', True, _('Must be enabled')),
                    ('ACCESS_CONTROL', 'EMAIL_VALIDATION_REQUIRED', True, _('Must be disabled')),
                )
            ),
        )
    )
"""

settings.register(
    livesettings.BooleanValue(
        LOGIN_PROVIDERS,
        'SIGNIN_DISCOURSE_ENABLED',
        default=False,
        description=_('Enable Discourse login')
    )
)

settings.register(
    livesettings.StringValue(
        LOGIN_PROVIDERS,
        'DISCOURSE_SITE_URL',
        description=_('Base url of your Discourse site')
    )
)

settings.register(
    livesettings.StringValue(
        LOGIN_PROVIDERS,
        'DISCOURSE_SSO_SECRET',
        description=_('Secret key of the Discourse site')
    )
)


settings.register(
    livesettings.StringValue(
        LOGIN_PROVIDERS,
        'SIGNIN_CUSTOM_OPENID_NAME',
        default=_('Custom OpenID'),
        description=_('Short name for the custom OpenID provider')
    )
)

CUSTOM_OPENID_MODE_CHOICES = (
    ('openid-direct', _('Direct button login')),
    ('openid-username', _('Requires username'))
)

settings.register(
    livesettings.StringValue(
        LOGIN_PROVIDERS,
        'SIGNIN_CUSTOM_OPENID_MODE',
        default='openid-direct',
        description=_('Type of OpenID login'),
        choices=CUSTOM_OPENID_MODE_CHOICES
    )
)

settings.register(
    livesettings.ImageValue(
        LOGIN_PROVIDERS,
        'SIGNIN_CUSTOM_OPENID_LOGIN_BUTTON',
        default='/images/logo.gif',
        description=_('Upload custom OpenID icon'),
        url_resolver=skin_utils.get_media_url
    )
)

settings.register(
    livesettings.StringValue(
        LOGIN_PROVIDERS,
        'SIGNIN_CUSTOM_OPENID_ENDPOINT',
        default='http://example.com',
        description=_('Custom OpenID endpoint'),
        help_text=_('Important: with the "username" mode there must be a '
                    '%%(username)s placeholder e.g. '
                    'http://example.com/%%(username)s/'),
    )
)

settings.register(
    livesettings.StringValue(
        LOGIN_PROVIDERS,
        'OPENSTACKID_ENDPOINT_URL',
        default='https://openstackid.org',
        description=_('OpenStackID service endpoint url'),
    )
)

providers = (
    'local',
    'AOL',
    'Blogger',
    'ClaimID',
    'Facebook',
    'Fedora',
    'Flickr',
    'GitHub',
    'Google Plus',
    'Mozilla Persona',
    'Twitter',
    'MediaWiki',
    'LinkedIn',
    'LiveJournal',
    # 'myOpenID',
    'OpenID',
    'Technorati',
    'Wordpress',
    'Vidoop',
    'Verisign',
    'Yahoo',
    'identi.ca',
    'LaunchPad',
    'OpenStackID',
    'Yammer',
    'Windows Live',
    'Microsoft Azure',
)

DISABLED_BY_DEFAULT = ('LaunchPad', 'Mozilla Persona', 'OpenStackID')

NEED_EXTRA_SETUP = ('Google Plus', 'Twitter', 'MediaWiki', 'Facebook',
                    'LinkedIn', 'identi.ca', 'Yammer', 'Windows Live', 'Microsoft Azure', 'GitHub',)

for provider in providers:
    if provider == 'local':
        provider_string = str(_('local password'))
    else:
        provider_string = provider

    kwargs = {
        'description': _('Activate %(provider)s login') % {'provider': provider_string},
        'default': not (provider in DISABLED_BY_DEFAULT)
    }
    if provider in NEED_EXTRA_SETUP:
        kwargs['help_text'] = _(
            'Note: to really enable %(provider)s login '
            'some additional parameters will need to be set '
            'in the "External keys" section'
        ) % {'provider': provider}

    setting_name = 'SIGNIN_%s_ENABLED' % provider.upper().replace(' ', '_')
    settings.register(
        livesettings.BooleanValue(
            LOGIN_PROVIDERS,
            setting_name,
            **kwargs
        )
    )

    if provider == 'MediaWiki':
        settings.register(
            livesettings.ImageValue(
                LOGIN_PROVIDERS,
                'MEDIAWIKI_SITE_ICON',
                default='/images/jquery-openid/mediawiki.png',
                description=_('MediaWiki login button image'),
                url_resolver=skin_utils.get_media_url
            )
        )

        settings.register(
            livesettings.BooleanValue(
                LOGIN_PROVIDERS,
                'MEDIAWIKI_ONE_CLICK_REGISTRATION_ENABLED',
                default=False,
                description=_('MediaWiki - enable one click registration'),
                help_text=format_lazy('{} {}',
                    _('Allows skipping the registration page after the wiki '
                      'authentication.'),
                    settings.get_related_settings_info(
                        ('EMAIL', 'BLANK_EMAIL_ALLOWED', True, _('Must be enabled')),
                        ('ACCESS_CONTROL', 'EMAIL_VALIDATION_REQUIRED', True, _('Must be disabled')),
                    )
                ),
            )
        )
