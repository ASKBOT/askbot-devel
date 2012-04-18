"""
Settings for embeddable widgets
"""
from django.utils.translation import ugettext as _
from django.utils.html import escape
from askbot.conf.settings_wrapper import settings
from askbot.deps.livesettings import ConfigurationGroup
from askbot.deps.livesettings import values
from askbot.conf.super_groups import CONTENT_AND_UI

EMBEDDABLE_WIDGETS = ConfigurationGroup(
    'EMBEDDABLE_WIDGETS',
    _('Embeddable widgets'),
    super_group = CONTENT_AND_UI
)

#we need better capabilities for the settings here
#

settings.register(
    values.IntegerValue(
        EMBEDDABLE_WIDGETS,
        'QUESTIONS_WIDGET_MAX_QUESTIONS',
        default = 7,
        description = _('Number of questions to show'),
        help_text = escape(
            _(
                'To embed the widget, add the following code '
                'to your site (and fill in correct base url, preferred tags, width and height):'
                '<iframe '
                'src="{{base_url}}/widgets/questions?tags={{comma-separated-tags}}" '
                'width="100%" '
                'height="300"'
                'scrolling="no">'
                '<p>Your browser does not support iframes.</p>'
                '</iframe>'
            )
        )
    )
)
settings.register(
    values.LongStringValue(
        EMBEDDABLE_WIDGETS,
        'QUESTIONS_WIDGET_CSS',
        default = """
body {
    overflow: hidden;
}
#container {
    width: 200px;
    height: 350px;
}
ul {
    list-style: none;
    padding: 5px;
    margin: 5px;
}
li {
    border-bottom: #CCC 1px solid;
    padding-bottom: 5px;
    padding-top: 5px;
}
li:last-child {
    border: none;
}
a {
    text-decoration: none;
    color: #464646;
    font-family: 'Yanone Kaffeesatz', sans-serif;
    font-size: 15px;
}
""",
        descripton = _('CSS for the questions widget')
    )
)

settings.register(
    values.LongStringValue(
        EMBEDDABLE_WIDGETS,
        'QUESTIONS_WIDGET_HEADER',
        description = _('Header for the questions widget'),
        default = ''
    )
)

settings.register(
    values.LongStringValue(
        EMBEDDABLE_WIDGETS,
        'QUESTIONS_WIDGET_FOOTER',
        description = _('Footer for the questions widget'),
        default = """
<link 
    href='http://fonts.googleapis.com/css?family=Yanone+Kaffeesatz:300,400,700'
    rel='stylesheet'
    type='text/css'
>
"""
    )
)
