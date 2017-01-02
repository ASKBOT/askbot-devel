"""
Sidebar settings
"""
from django.utils.translation import ugettext_lazy as _
from askbot.conf.settings_wrapper import settings
from askbot.deps.livesettings import ConfigurationGroup
from askbot.deps.livesettings import values
from askbot.conf.super_groups import CONTENT_AND_UI

LEADING_SIDEBAR = ConfigurationGroup(
    'LEADING_SIDEBAR',
    _('Common left sidebar'),
    super_group=CONTENT_AND_UI
)

settings.register(
    values.BooleanValue(
        LEADING_SIDEBAR,
        'ENABLE_LEADING_SIDEBAR',
        description=_('Enable left sidebar'),
        default=False,
    )
)

settings.register(
    values.LongStringValue(
        LEADING_SIDEBAR,
        'LEADING_SIDEBAR',
        description=_('HTML for the left sidebar'),
        default='',
        help_text=_(
            'Use this area to enter content at the LEFT sidebar '
            'in HTML format.  When using this option, please '
            'use the HTML validation service to make sure that '
            'your input is valid and works well in all browsers.'
        )
    )
)
