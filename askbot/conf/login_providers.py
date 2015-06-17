"""
External service key settings
"""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import LOGIN_USERS_COMMUNICATION
from askbot.deps import livesettings
from django.utils.translation import string_concat
from django.utils.translation import ugettext_lazy as _
from django.conf import settings as django_settings
from askbot.skins import utils as skin_utils

LOGIN_PROVIDERS = livesettings.ConfigurationGroup(
                    'LOGIN_PROVIDERS',
                    _('Login provider setings'),
                    super_group = LOGIN_USERS_COMMUNICATION
                )

settings.register(
    livesettings.BooleanValue(
        LOGIN_PROVIDERS,
        'TERMS_CONSENT_REQUIRED',
        default=False,
        description=_('Acceptance of terms required at registration'),
        help_text=settings.get_related_settings_info(('FLATPAGES', 'TERMS', True))
    )
)

#todo: remove this - we don't want the local login button
#but instead always show the login/password field when used
settings.register(
    livesettings.BooleanValue(
        LOGIN_PROVIDERS,
        'SIGNIN_ALWAYS_SHOW_LOCAL_LOGIN',
        default = True,
        description=_('Always display local login form and hide "Askbot" button.'),
    )
)

settings.register(
    livesettings.BooleanValue(
        LOGIN_PROVIDERS,
        'SIGNIN_WORDPRESS_SITE_ENABLED',
        default = False,
        description=_('Activate to allow login with self-hosted wordpress site'),
        help_text=_('to activate this feature you must fill out the wordpress xml-rpc setting bellow')
    )
)

settings.register(
    livesettings.URLValue(
        LOGIN_PROVIDERS,
        'WORDPRESS_SITE_URL',
        default = '',
        description=_('Fill it with the wordpress url to the xml-rpc, normally http://mysite.com/xmlrpc.php'),
        help_text=_('To enable, go to Settings->Writing->Remote Publishing and check the box for XML-RPC')
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

providers = (
    'local',
    'AOL',
    'Blogger',
    'ClaimID',
    'Facebook',
    'Fedora',
    'Flickr',
    #'Google',
    'Mozilla Persona',
    'Twitter',
    'MediaWiki',
    'LinkedIn',
    'LiveJournal',
    #'myOpenID',
    'OpenID',
    'Technorati',
    'Wordpress',
    'Vidoop',
    'Verisign',
    'Yahoo',
    'identi.ca',
    'LaunchPad',
)

DISABLED_BY_DEFAULT = ('LaunchPad', 'Mozilla Persona')

NEED_EXTRA_SETUP = ('Google Plus', 'Twitter', 'MediaWiki', 'Facebook', 'LinkedIn', 'identi.ca',)

GOOGLE_METHOD_CHOICES = (
    ('openid', 'OpenID (deprecated)'),
    ('google-plus', 'Google Plus'),
    ('disabled', _('disable')),
)

for provider in providers:
    if provider == 'local':
        provider_string = unicode(_('local password'))
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
                help_text=string_concat(
                    _('Allows skipping the registration page after the wiki authentication.'),
                    ' ',
                    settings.get_related_settings_info(
                        ('EMAIL', 'BLANK_EMAIL_ALLOWED', True, _('Must be enabled')),
                        ('ACCESS_CONTROL', 'REQUIRE_VALID_EMAIL_FOR', True, _('Must be not be required')),
                    )
                ),
            )
        )


    if provider == 'local':
        #add Google settings here as one-off
        settings.register(
            livesettings.StringValue(
                LOGIN_PROVIDERS,
                'SIGNIN_GOOGLE_METHOD',
                default='disabled',
                choices=GOOGLE_METHOD_CHOICES,
                description=_('Google login'),
                help_text=_(
                    'To enable Google-Plus login, OAuth keys are required in the "External keys" section'
                )
            )
        )
