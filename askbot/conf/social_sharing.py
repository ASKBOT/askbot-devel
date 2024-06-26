"""
Social sharing settings
"""
from django.utils.translation import gettext_lazy as _
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import EXTERNAL_SERVICES
from livesettings.values import ConfigurationGroup, BooleanValue, \
    StringValue

SOCIAL_SHARING = ConfigurationGroup(
    'SOCIAL_SHARING',
    _('Content sharing'),
    super_group=EXTERNAL_SERVICES
)

settings.register(
    BooleanValue(
        SOCIAL_SHARING,
        'RSS_ENABLED',
        default=True,
        description=_('Check to enable RSS feeds')
    )
)

settings.register(
    StringValue(
        SOCIAL_SHARING,
        'SHARING_SUFFIX_TEXT',
        default='',
        description=_('Hashtag or suffix to sharing messages')
    )
)

settings.register(
    BooleanValue(
        SOCIAL_SHARING,
        'ENABLE_SHARING_TWITTER',
        default=True,
        description=_('Check to enable sharing of questions on Twitter'),
        help_text=_(
            'Important - to actually start sharing on twitter, '
            'it is required to set up Twitter consumer key and secret '
            'in the "keys to external services" section.'
        )
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
