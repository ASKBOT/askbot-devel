"""settings that allow changing of the license
clause used in askbot instances"""
from askbot import const
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import CONTENT_AND_UI
from askbot.deps import livesettings
from askbot.skins import utils as skin_utils
from django.utils.translation import ugettext as _
from django.conf import settings as django_settings

LICENSE_SETTINGS = livesettings.ConfigurationGroup(
                        'LICENSE_SETTINGS',
                        _('Content LicensContent License'),
                        super_group = CONTENT_AND_UI
                    )

settings.register(
    livesettings.BooleanValue(
        LICENSE_SETTINGS,
        'USE_LICENSE',
        description = _('Show license clause in the site footer'),
        default = True
    )
)

settings.register(
    livesettings.StringValue(
        LICENSE_SETTINGS,
        'LICENSE_ACRONYM',
        description = _('Short name for the license'),
        default = 'cc-by-sa'
    )
)

settings.register(
    livesettings.StringValue(
        LICENSE_SETTINGS,
        'LICENSE_TITLE',
        description = _('Full name of the license'),
        default = _('Creative Commons Attribution Share Alike 3.0'),
    )
)

settings.register(
    livesettings.BooleanValue(
        LICENSE_SETTINGS,
        'LICENSE_USE_URL',
        description = _('Add link to the license page'),
        default = True
    )
)

settings.register(
    livesettings.URLValue(
        LICENSE_SETTINGS,
        'LICENSE_URL',
        description = _('License homepage'),
        help_text = _(
            'URL of the official page with all the license legal clauses'
        ),
        default = const.DEPENDENCY_URLS['cc-by-sa']
    )
)

settings.register(
    livesettings.BooleanValue(
        LICENSE_SETTINGS,
        'LICENSE_USE_LOGO',
        description = _('Use license logo'),
        default = True
    )
)

settings.register(
    livesettings.ImageValue(
        LICENSE_SETTINGS,
        'LICENSE_LOGO_URL',
        description = _('License logo image'),
        default = '/images/cc-by-sa.png',
        url_resolver = skin_utils.get_media_url
    )
)
