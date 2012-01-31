"""
External service key settings
"""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import LOGIN_USERS_COMMUNICATION
from askbot.deps import livesettings
from django.utils.translation import ugettext as _
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

providers = (
    'local',
    'AOL',
    'Blogger',
    'ClaimID',
    'Facebook',
    'Flickr',
    'Google',
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
)

need_extra_setup = ('Twitter', 'Facebook', 'LinkedIn', 'identi.ca',)

for provider in providers:
    kwargs = {
        'description': _('Activate %(provider)s login') % {'provider': provider},
        'default': True,
    }
    if provider in need_extra_setup:
        kwargs['help_text'] = _(
            'Note: to really enable %(provider)s login '
            'some additional parameters will need to be set '
            'in the "External keys" section'
        ) % {'provider': provider}

    setting_name = 'SIGNIN_%s_ENABLED' % provider.upper()
    settings.register(
        livesettings.BooleanValue(
            LOGIN_PROVIDERS,
            setting_name,
            **kwargs
        )
    )
