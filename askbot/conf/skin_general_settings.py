"""
General skin settings
"""
from askbot.conf.settings_wrapper import settings
from askbot.deps.livesettings import ConfigurationGroup
from askbot.deps.livesettings import values
from django.utils.translation import ugettext as _
from django.conf import settings as django_settings
from askbot.skins import utils as skin_utils
from askbot import const
from askbot.conf.super_groups import CONTENT_AND_UI

GENERAL_SKIN_SETTINGS = ConfigurationGroup(
                    'GENERAL_SKIN_SETTINGS',
                    _('Logos and HTML <head> parts'),
                    super_group = CONTENT_AND_UI
                )

settings.register(
    values.ImageValue(
        GENERAL_SKIN_SETTINGS,
        'SITE_LOGO_URL',
        description = _('Q&A site logo'),
        help_text = _(
                        'To change the logo, select new file, '
                        'then submit this whole form.'
                    ),
        default = '/images/logo.gif',
        url_resolver = skin_utils.get_media_url
    )
)

settings.register(
    values.BooleanValue(
        GENERAL_SKIN_SETTINGS,
        'SHOW_LOGO',
        description = _('Show logo'),
        help_text = _(
                        'Check if you want to show logo in the forum header '
                        'or uncheck in the case you do not want the logo to '
                        'appear in the default location'
                    ),
        default = False
    )
)

settings.register(
    values.ImageValue(
        GENERAL_SKIN_SETTINGS,
        'SITE_FAVICON',
        description = _('Site favicon'),
        help_text = _(
                        'A small 16x16 or 32x32 pixel icon image '
                        'used to distinguish your site in the browser '
                        'user interface. Please find more information '
                        'about favicon '
                        'at <a href="%(favicon_info_url)s">this page</a>.'
                    ) % {'favicon_info_url': const.DEPENDENCY_URLS['favicon']},
        allowed_file_extensions = ('ico',),#only allow .ico files
        default = '/images/favicon.gif',
        url_resolver = skin_utils.get_media_url
    )
)

settings.register(
    values.ImageValue(
        GENERAL_SKIN_SETTINGS,
        'LOCAL_LOGIN_ICON',
        description = _('Password login button'),
        help_text = _(
                        'An 88x38 pixel image that is used on the login screen '
                        'for the password login button.'
                    ),
        default = '/images/pw-login.gif',
        url_resolver = skin_utils.get_media_url
    )
)

settings.register(
    values.BooleanValue(
        GENERAL_SKIN_SETTINGS,
        'ALWAYS_SHOW_ALL_UI_FUNCTIONS',
        default = False,
        description = _('Show all UI functions to all users'),
        help_text = _(
                        'If checked, all forum functions '
                        'will be shown to users, regardless of their '
                        'reputation. However to use those functions, '
                        'moderation rules, reputation and other limits '
                        'will still apply.'
                    )
    )
)

settings.register(
    values.StringValue(
        GENERAL_SKIN_SETTINGS,
        'ASKBOT_DEFAULT_SKIN',
        default = 'default',
        choices = skin_utils.get_skin_choices(),
        description = _('Select skin'),
    )
)



settings.register(
    values.BooleanValue(
        GENERAL_SKIN_SETTINGS,
        'USE_CUSTOM_HTML_HEAD',
        default = False,
        description = _('Customize HTML <HEAD>')
    )
)

settings.register(
    values.LongStringValue(
        GENERAL_SKIN_SETTINGS,
        'CUSTOM_HTML_HEAD',
        default = '',
        description = _('Custom portion of the HTML <HEAD>'),
        help_text = _(
                    '<strong>To use this option</strong>, '
                    'check "Customize HTML &lt;HEAD&gt;" '
                    'above. Contents of this box will be inserted '
                    'into the &lt;HEAD&gt; portion of the HTML '
                    'output, where elements such as &lt;script&gt;, '
                    '&lt;link&gt;, &lt;meta&gt; may be added. '
                    'Please, keep in mind that adding external '
                    'javascript to the &lt;HEAD&gt; is not recommended '
                    'because it slows loading of the pages. '
                    'Instead, it will be more efficient to place '
                    'links to the javascript files into the footer. '
                    '<strong>Note:</strong> if you do use this setting, '
                    'please test the site with the W3C HTML validator service.'
                    )
    )
)

settings.register(
    values.LongStringValue(
        GENERAL_SKIN_SETTINGS,
        'CUSTOM_HEADER',
        default = '',
        description = _('Custom header additions'),
        help_text = _(
                    'Header is the bar at the top of the content '
                    'that contains user info and site links, '
                    'and is common to all pages. '
                    'Use this area to enter contents of the header'
                    'in the HTML format.   When customizing the site header '
                    '(as well as footer and the HTML &lt;HEAD&gt;), '
                    'use the HTML validation service to make sure that '
                    'your input is valid and works well in all browsers.'
                    )
    )
)

settings.register(
    values.StringValue( GENERAL_SKIN_SETTINGS,
        'FOOTER_MODE',
        description = _('Site footer mode'),
        help_text = _(
                    'Footer is the bottom portion of the content, '
                    'which is common to all pages. '
                    'You can disable, customize, or use the default footer.'
                ),
        choices = (
                    ('default', 'default'),
                    ('customize', 'customize'),
                    ('disable', 'disable')
                ),
        default = 'default',
    )
)

settings.register(
    values.LongStringValue(
        GENERAL_SKIN_SETTINGS,
        'CUSTOM_FOOTER',
        description = _('Custom footer (HTML format)'),
        help_text = _(
                    '<strong>To enable this function</strong>, please select '
                    'option \'customize\' in the "Site footer mode" above. '
                    'Use this area to enter contents of the footer '
                    'in the HTML format. When customizing the site footer '
                    '(as well as the header and HTML &lt;HEAD&gt;), '
                    'use the HTML validation service to make sure that '
                    'your input is valid and works well in all browsers.'
                    )
    )
)

settings.register(
    values.BooleanValue(
        GENERAL_SKIN_SETTINGS,
        'USE_CUSTOM_CSS',
        description = _('Apply custom style sheet (CSS)'),
        help_text = _(
                    'Check if you want to change appearance '
                    'of your form by adding custom style sheet rules ' 
                    '(please see the next item)'
                    ),
        default = False
    )
)

settings.register(
    values.LongStringValue(
        GENERAL_SKIN_SETTINGS,
        'CUSTOM_CSS',
        description = _('Custom style sheet (CSS)'),
        help_text = _(
                    '<strong>To use this function</strong>, check '
                    '"Apply custom style sheet" option above. '
                    'The CSS rules added in this window will be applied '
                    'after the default style sheet rules. ' 
                    'The custom style sheet will be served dynamically at '
                    'url "&lt;forum url&gt;/custom.css", where '
                    'the "&lt;forum url&gt; part depends (default is '
                    'empty string) on the url configuration in your urls.py.'
                    )
    )
)

settings.register(
    values.BooleanValue(
        GENERAL_SKIN_SETTINGS,
        'USE_CUSTOM_JS',
        description = _('Add custom javascript'),
        default = False,
        help_text = _(
            'Check to enable javascript that you can enter '
            'in the next field'
        )
    )
)

settings.register(
    values.LongStringValue(
        GENERAL_SKIN_SETTINGS,
        'CUSTOM_JS',
        description = _('Custom javascript'),
        help_text = _(
            'Type or paste plain javascript that you would like '
            'to run on your site. Link to the script will be inserted '
            'at the bottom of the HTML output and will be served '
            'at the url "&lt;forum url&gt;/custom.js". Please, '
            'bear in mind that your javascript code may break other '
            'functionalities of the site and that the behavior may '
            'not be consistent across different browsers '
            '(<strong>to enable your custom code</strong>, check '
            '"Add custom javascript" option above).'
        )
    )
)

settings.register(
    values.IntegerValue(
        GENERAL_SKIN_SETTINGS,
        'MEDIA_RESOURCE_REVISION',
        default = 1,
        description = _('Skin media revision number'),
        help_text = _(
            'Will be set automatically '
            'but you can modify it if necessary.'
       )
    )
)

settings.register(
    values.StringValue(
        GENERAL_SKIN_SETTINGS,
        'MEDIA_RESOURCE_REVISION_HASH',
        description = _(
            'Hash to update the media revision number automatically.'
        ),
        default='',
        help_text = _(
            'Will be set automatically, it is not necesary to modify manually.'
        )
    )
)
