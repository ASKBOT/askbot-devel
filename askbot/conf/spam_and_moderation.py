"""Settings for content moderation and spam control"""
from django.utils.translation import ugettext as _
from askbot import const
from askbot.deps import livesettings
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import EXTERNAL_SERVICES

SPAM_AND_MODERATION = livesettings.ConfigurationGroup(
                    'SPAM_AND_MODERATION',
                    _('Akismet spam protection'),
                    super_group = EXTERNAL_SERVICES
                )

settings.register(
    livesettings.BooleanValue(
        SPAM_AND_MODERATION,
        'USE_AKISMET',
        description=_('Enable Akismet spam detection(keys below are required)'),
        default=False,
        help_text = _(
                         'To get an Akismet key please visit '
                         '<a href="%(url)s">Akismet site</a>'
                     ) % {'url': const.DEPENDENCY_URLS['akismet']}
    )
)

settings.register(
    livesettings.StringValue(
        SPAM_AND_MODERATION,
        'AKISMET_API_KEY',
        description=_('Akismet key for spam detection')
    )
)
