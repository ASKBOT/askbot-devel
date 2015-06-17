"""
Sidebar settings
"""
from askbot.conf.settings_wrapper import settings
from askbot.deps.livesettings import ConfigurationGroup
from askbot.deps.livesettings import values
from django.utils.translation import ugettext_lazy as _
from askbot.conf.super_groups import CONTENT_AND_UI
SIDEBAR_QUESTION = ConfigurationGroup(#shitty name - why sidebar?
                    'SIDEBAR_QUESTION',
                    _('Question page banners and sidebar'),
                    super_group = CONTENT_AND_UI
                )

settings.register(
    values.LongStringValue(
        SIDEBAR_QUESTION,
        'QUESTION_PAGE_TOP_BANNER',
        description=_('Top banner'),
        default='',
        localized=True,
        help_text=_(
            'When using this option, please '
            'use the HTML validation service to make sure that '
            'your input is valid and works well in all browsers.'
        )
    )
)

settings.register(
    values.BooleanValue(
        SIDEBAR_QUESTION,
        'QUESTION_PAGE_TOP_BANNER_ANON_ONLY',
        default=False,
        description=_('Show above only to anonymous users'),
    )
)

settings.register(
    values.LongStringValue(
        SIDEBAR_QUESTION,
        'QUESTION_PAGE_ANSWER_BANNER',
        description=_('Answers banner'),
        default='',
        localized=True,
        help_text=_(
            'This banner will show under the first answer. '
            'When using this option, please '
            'use the HTML validation service to make sure that '
            'your input is valid and works well in all browsers.'
        )
    )
)

settings.register(
    values.BooleanValue(
        SIDEBAR_QUESTION,
        'QUESTION_PAGE_ANSWER_BANNER_ANON_ONLY',
        default=False,
        description=_('Show above only to anonymous users'),
    )
)

settings.register(
    values.BooleanValue(
        SIDEBAR_QUESTION,
        'QUESTION_PAGE_ALWAYS_SHOW_ANSWER_BANNER',
        default=False,
        description=_('Show answers banner even if there are no answers')
    )
)


settings.register(
    values.LongStringValue(
        SIDEBAR_QUESTION,
        'SIDEBAR_QUESTION_HEADER',
        description=_('Custom sidebar header'),
        default='',
        localized=True,
        help_text=_(
                    'Use this area to enter content at the TOP of the sidebar '
                    'in HTML format. When using this option '
                    '(as well as the sidebar footer), please '
                    'use the HTML validation service to make sure that '
                    'your input is valid and works well in all browsers.'
                    )
    )
)

settings.register(
    values.BooleanValue(
        SIDEBAR_QUESTION,
        'SIDEBAR_QUESTION_HEADER_ANON_ONLY',
        default=False,
        description=_('Show above only to anonymous users')
    )
)

settings.register(
    values.BooleanValue(
        SIDEBAR_QUESTION,
        'SIDEBAR_QUESTION_SHOW_TAGS',
        description = _('Show tag list in sidebar'),
        help_text = _(
                    'Uncheck this if you want to hide the tag '
                    'list from the sidebar '
                    ),
        default = True
    )
)

settings.register(
    values.BooleanValue(
        SIDEBAR_QUESTION,
        'SIDEBAR_QUESTION_SHOW_META',
        description = _('Show meta information in sidebar'),
        help_text = _(
                    'Uncheck this if you want to hide the meta '
                    'information about the question (post date, '
                    'views, last updated). '
                    ),
        default = True
    )
)

settings.register(
    values.BooleanValue(
        SIDEBAR_QUESTION,
        'SIDEBAR_QUESTION_SHOW_RELATED',
        description = _('Show related questions in sidebar'),
        help_text = _(
                    'Uncheck this if you want to hide the list '
                    'of related questions. '
                    ),
        default = True
    )
)

settings.register(
    values.LongStringValue(
        SIDEBAR_QUESTION,
        'SIDEBAR_QUESTION_FOOTER',
        description=_('Custom sidebar footer'),
        default='',
        localized=True,
        help_text=_(
                    'Use this area to enter content at the BOTTOM of the sidebar'
                    'in HTML format.   When using this option '
                    '(as well as the sidebar header), please '
                    'use the HTML validation service to make sure that '
                    'your input is valid and works well in all browsers.'
                    )
    )
)

settings.register(
    values.BooleanValue(
        SIDEBAR_QUESTION,
        'SIDEBAR_QUESTION_FOOTER_ANON_ONLY',
        default=False,
        description=_('Show above only to anonymous users')
    )
)
