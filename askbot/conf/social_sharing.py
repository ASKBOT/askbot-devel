"""
Social sharing settings
"""
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import EXTERNAL_SERVICES
from askbot.deps.livesettings import ConfigurationGroup, BooleanValue, StringValue
from django.utils.translation import ugettext as _

SOCIAL_SHARING = ConfigurationGroup(
            'SOCIAL_SHARING',
            _('Sharing content on social networks'), 
            super_group = EXTERNAL_SERVICES
        )

settings.register(
    BooleanValue(
        SOCIAL_SHARING,
        'ENABLE_SHARING_TWITTER',
        default=True,
        description=_('Check to enable sharing of questions on Twitter')
    )
)

settings.register(
    BooleanValue(
        SOCIAL_SHARING,
        'ENABLE_SHARING_FACEBOOK',
        default=True,
        description=_('Check to enable sharing of questions on Facebook')
    )
)

settings.register(
    BooleanValue(
        SOCIAL_SHARING,
        'ENABLE_SHARING_LINKEDIN',
        default=True,
        description=_('Check to enable sharing of questions on LinkedIn')
    )
)

settings.register(
    BooleanValue(
        SOCIAL_SHARING,
        'ENABLE_SHARING_IDENTICA',
        default=True,
        description=_('Check to enable sharing of questions on Identi.ca')
    )
)

settings.register(
    BooleanValue(
        SOCIAL_SHARING,
        'ENABLE_SHARING_GOOGLE',
        default=True,
        description=_('Check to enable sharing of questions on Google+')
    )
)

settings.register(
    StringValue(
        SOCIAL_SHARING,
        'SHARING_SUFFIX_TEXT',
        default='',
        description=_('Text (e.g. Hashtag) to add to all social sharing options'),
        help_text=_(
                    'Text to add to all social sharing options. Keep it short!'
                    )
    )
)
