"""
Settings that modify processing of user text input
"""

from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import DATA_AND_FORMATTING
from askbot.deps.livesettings import ConfigurationGroup
from askbot.deps.livesettings import BooleanValue, StringValue, LongStringValue
from askbot import const
from django.utils.translation import ugettext as _
import re

MARKUP = ConfigurationGroup(
                    'MARKUP',
                    _('Markup in posts'),
                    super_group = DATA_AND_FORMATTING
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
    
    except Exception:
        # The regex is invalid, so we overwrite it with empty string
        return ""


settings.register(
    BooleanValue(
        MARKUP,
        'MARKUP_CODE_FRIENDLY',
        description = _('Enable code-friendly Markdown'),
        help_text = _(
            'If checked, underscore characters will not '
            'trigger italic or bold formatting - '
            'bold and italic text can still be marked up '
            'with asterisks. Note that "MathJax support" '
            'implicitly turns this feature on, because '
            'underscores are heavily used in LaTeX input.'
        ),
        default = False
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
                    ) % {
                            'url': const.DEPENDENCY_URLS['mathjax'],
                        },
        default = False
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
                    '(for example: http://mysite.com/mathjax)'
                    ),
        default = ''
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
        default = False
    )
)


settings.register(
    LongStringValue(
        MARKUP,
        'AUTO_LINK_PATTERNS',
        description=_('Regexes to detect the link patterns'),
        help_text=_(
            'Enter valid regular expressions for the patters,'
            ' one per line.'
            ' For example to'
            ' detect a bug pattern like #bug123,'
            ' use the following regex: #bug(\d+). The numbers'
            ' captured by the pattern in the parentheses will'
            ' be transferred to the link url template.'
            ' Please look up more information about regular'
            ' expressions elsewhere.'
        ),
        update_callback=regex_settings_validation,
        default = ''
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
        default = ''
    )
)
