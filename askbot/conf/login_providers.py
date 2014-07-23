"""
External service key settings
"""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import LOGIN_USERS_COMMUNICATION
from askbot.deps import livesettings
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
        'PASSWORD_REGISTER_SHOW_PROVIDER_BUTTONS',
        default = True,
        description=_('Show alternative login provider buttons on the password "Sign Up" page'),
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
        description=_('Upload your icon'),
        url_resolver=skin_utils.get_media_url
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
    'Flickr',
    'Google',
    'Mozilla Persona',
    'Twitter',
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

DISABLED_BY_DEFAULT = ('LaunchPad',)

NEED_EXTRA_SETUP = ('Twitter', 'Facebook', 'LinkedIn', 'identi.ca',)

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
