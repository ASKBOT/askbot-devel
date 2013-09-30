"""
General skin settings
"""
from askbot.conf.settings_wrapper import settings
from askbot.deps.livesettings import ConfigurationGroup
from askbot.deps.livesettings import values
from django.utils.translation import ugettext_lazy as _
from askbot.skins import utils as skin_utils
from askbot import const
from askbot.conf.super_groups import CONTENT_AND_UI

BUTTON_SETTINGS = ConfigurationGroup(
                    'BUTTON_SETTINGS',
                    _('Text on buttons'),
                    super_group = CONTENT_AND_UI
                )

settings.register(
    values.StringValue(
        BUTTON_SETTINGS,
        'ASK_BUTTON_TEXT',
        default = '',
        description = _('Ask new question button'),
    )
)

settings.register(
    values.StringValue(
        BUTTON_SETTINGS,
        'ASK_GROUP_BUTTON_TEXT',
        default = '',
        description = _('Ask new question to group button'),
    )
)

settings.register(
    values.StringValue(
        BUTTON_SETTINGS,
        'ANSWER_BUTTON_TEXT',
        default = '',
        description = _('Post answer button'),
    )
)

settings.register(
    values.StringValue(
        BUTTON_SETTINGS,
        'ANSWER_OWN_QUESTION_BUTTON_TEXT',
        default = '',
        description = _('Answer your own question button'),
    )
)

#settings.register(
#    values.StringValue(
#        BUTTON_SETTINGS,
#        'EDIT_QUESTION_BUTTON_TEXT',
#        default = '',
#        description = _('Edit Question button text'),
#    )
#)

settings.register(
    values.StringValue(
        BUTTON_SETTINGS,
        'EDIT_ANSWER_BUTTON_TEXT',
        default = '',
        description = _('Edit answer button'),
    )
)
