"""
Q&A forum flatpages (about, etc.)
"""
from askbot.conf.settings_wrapper import settings
from askbot.deps.livesettings import ConfigurationGroup, LongStringValue
from askbot.conf.super_groups import CONTENT_AND_UI
from django.utils.translation import ugettext as _

FLATPAGES = ConfigurationGroup(
                'FLATPAGES',
                _('Flatpages - about, privacy policy, etc.'),
                super_group = CONTENT_AND_UI
            )

settings.register(
    LongStringValue(
        FLATPAGES,
        'FORUM_ABOUT',
        description=_('Text of the Q&A forum About page (html format)'),
        help_text=\
        _(
            'Save, then <a href="http://validator.w3.org/">'
            'use HTML validator</a> on the "about" page to check your input.'
        )
    )
)

settings.register(
    LongStringValue(
        FLATPAGES,
        'FORUM_FAQ',
        description=_('Text of the Q&A forum FAQ page (html format)'),
        help_text=\
        _(
            'Save, then <a href="http://validator.w3.org/">'
            'use HTML validator</a> on the "faq" page to check your input.'
        )
    )
)


settings.register(
    LongStringValue(
        FLATPAGES,
        'FORUM_PRIVACY',
        description=_('Text of the Q&A forum Privacy Policy (html format)'),
        help_text=\
        _(
            'Save, then <a href="http://validator.w3.org/">'
            'use HTML validator</a> on the "privacy" page to check your input.'
        )
    )
)
