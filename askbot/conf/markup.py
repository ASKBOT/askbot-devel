"""
Settings that modify processing of user text input
"""

from askbot.conf.settings_wrapper import settings
from askbot.deps.livesettings import ConfigurationGroup
from askbot.deps.livesettings import BooleanValue, StringValue, LongStringValue
from django.utils.translation import ugettext as _
import askbot
from askbot import const
import os
import re

MARKUP = ConfigurationGroup(
                    'MARKUP',
                    _('Markup formatting')
                )

AUTOLINK = ConfigurationGroup(
    'AUTOLINK',
    _('Auto link a pattern to an URL')

)

def regex_settings_validation(*args):
    """
    Validate the regular expressions
   
    """
    try:

        new_value = args[1]
        regex_list = new_value.split('\n')
        
        for i in range(0,len(regex_list)):
            re.compile(regex_list[i].strip())
        return args[1]
    
    except Exception, e:
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
            AUTOLINK,
            'ENABLE_AUTO_LINKING',
            description=_('Enable autolinking a specifc pattern'),
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
        AUTOLINK,
        'PATTERN',
        description=_('Regex to detect the pattern'),
        help_text=_(
            ' Enter valid regular expressions to'
            ' detect patterns. If you want to auto'
            ' link more than one key terms enter them'
            ' line by line. For example to'
            ' detect a bug pattern like #rhbz 637402'
            ' you will have use the following regex  #rhbz\s(\d+)'
            ),
        update_callback=regex_settings_validation,
        default = ''
        )
    )

settings.register(
    LongStringValue(
        AUTOLINK,
        'AUTO_LINK_URL',
        description=_('URL for autolinking'),
        help_text=_(
            ' The regex to  detect pattern  #rhbz 637402'
            ' is  #rhbz\s(\d+), If you want to auto link it to the actual bug'
            ' then the autolink URL should be entered here. Example URL can be'
            ' https://bugzilla.redhat.com/show_bug.cgi?id=\\1'
            ' where \\1 is the saved match (bugid) from the regular expression.'
            ' Multiple URLs should be entered in separate lines.'
            ' The URL entered in first line'
            ' will be used to auto link the first pattern or key term'
            ),
        default = ''
        )
    )

