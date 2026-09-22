"""
Settings that modify processing of user text input
"""

import re
from django.utils.translation import gettext_lazy as _
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import DATA_AND_FORMATTING
from livesettings.values import ConfigurationGroup
from livesettings.values import BooleanValue, StringValue, LongStringValue
from askbot import const

MARKUP = ConfigurationGroup(
    'MARKUP',
    _('Markup in posts'),
    super_group=DATA_AND_FORMATTING
)

# Default list of TLDs that may be auto-linked as bare domains.
# Everyday web and common modern gTLDs, plus io/co/me. Two-letter file
# extensions that are also ccTLDs (mk, py, md, sh, rs...) are left out so
# tokens like 'config-user.mk' or 'main.py' are not turned into links.
# This exact string is duplicated in the JS converter and parity runner -
# keep the three copies identical.
LINKIFY_TLD_ALLOWLIST_DEFAULT = (
    'com org net edu gov mil int info biz io dev app co xyz me'
)


def regex_settings_validation(*args):
    """
    Validate the regular expressions
    """
    try:
        new_value = args[1]
        regex_list = new_value.split('\n')

        for i in range(0, len(regex_list)):
            re.compile(regex_list[i].strip())
        return args[1]
    except re.error:
        # The regex is invalid, so we overwrite it with empty string
        return ""


settings.register(
    BooleanValue(
        MARKUP,
        'MARKUP_CODE_FRIENDLY',
        description=_('Enable code-friendly Markdown'),
        help_text=_(
            'If checked, underscore characters will not '
            'trigger italic or bold formatting - '
            'bold and italic text can still be marked up '
            'with asterisks. Note that "MathJax support" '
            'implicitly turns this feature on, because '
            'underscores are heavily used in LaTeX input.'
        ),
        default=False
    )
)

settings.register(
    BooleanValue(
        MARKUP,
        'ENABLE_MATHJAX',
        description=_('Mathjax support (rendering of LaTeX)'),
        help_text=_(
            'If you enable this feature, '
            '<a href="%(url)s">mathjax</a> must be '
            'installed on your server in its own directory.'
        ) % {'url': const.DEPENDENCY_URLS['mathjax']},
        default=False
    )
)

settings.register(
    StringValue(
        MARKUP,
        'MATHJAX_BASE_URL',
        description=_('Base url of MathJax deployment'),
        help_text=_(
            'Note - <strong>MathJax is not included with '
            'askbot</strong> - you should deploy it yourself, '
            'preferably at a separate domain and enter url '
            'pointing to the "mathjax" directory '
            '(for example: http://mysite.com/mathjax)'),
        default=''
    )
)


settings.register(
    BooleanValue(
        MARKUP,
        'ENABLE_AUTO_LINKING',
        description=_('Enable autolinking with specific patterns'),
        help_text=_(
            'If you enable this feature, '
            'the application  will be able to '
            'detect patterns and auto link to URLs'
        ),
        default=False
    )
)


settings.register(
    BooleanValue(
        MARKUP,
        'LINKIFY_FUZZY_ENABLED',
        description=_('Auto-link bare domains and "www." addresses'),
        help_text=_(
            'If checked, text like "example.com" or "www.example.com" '
            'becomes a link even without a "http://" prefix. '
            'When unchecked, only addresses with an explicit scheme '
            '(such as "http://" or "mailto:") are auto-linked. '
            'This change takes effect after a server restart.'
        ),
        default=True
    )
)

settings.register(
    LongStringValue(
        MARKUP,
        'LINKIFY_TLD_ALLOWLIST',
        description=_('Domain endings allowed for bare-domain auto-linking'),
        help_text=_(
            'Only bare domains ending in one of these will be auto-linked, '
            'for example "com" or "org". Separate entries with spaces or '
            'commas. A leading dot is optional (".io" and "io" are the same). '
            'This limits which "word.ending" tokens turn into links, so that '
            'file names like "main.py" are left alone. '
            'This change takes effect after a server restart.'
        ),
        default=LINKIFY_TLD_ALLOWLIST_DEFAULT
    )
)

settings.register(
    LongStringValue(
        MARKUP,
        'AUTO_LINK_PATTERNS',
        description=_('Regexes to detect the link patterns'),
        help_text=_(
            'Enter valid regular expressions for the patterns,'
            ' one per line.'
            ' For example to'
            ' detect a bug pattern like #bug123,'
            ' use the following regex: #bug(\d+). The numbers'
            ' captured by the pattern in the parentheses will'
            ' be transferred to the link url template.'
            ' Please look up more information about regular'
            ' expressions elsewhere. Invalid expressions will'
            ' not be accepted.'
        ),
        update_callback=regex_settings_validation,
        default=''
        )
    )

settings.register(
    LongStringValue(
        MARKUP,
        'AUTO_LINK_URLS',
        description=_('URLs for autolinking'),
        help_text=_(
            'Here, please enter url templates for the patterns'
            ' entered in the previous setting, also one entry per line.'
            ' <strong>Make sure that number of lines in this setting'
            ' and the previous one are the same</strong>'
            ' For example template'
            ' https://bugzilla.redhat.com/show_bug.cgi?id=\\1'
            ' together with the pattern shown above'
            ' and the entry in the post #123'
            ' will produce link to the bug 123 in the redhat bug tracker.'
        ),
        default=''
    )
)
