"""
Q&A website settings - title, desctiption, basic urls
keywords
"""
from urlparse import urlparse

from django.utils.translation import ugettext_lazy as _
from django.conf import settings as django_settings

from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import CONTENT_AND_UI
from askbot.deps import livesettings


QA_SITE_SETTINGS = livesettings.ConfigurationGroup(
    'QA_SITE_SETTINGS',
    _('URLS, keywords & greetings'),
    super_group=CONTENT_AND_UI
)

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'APP_TITLE',
        default=_('My site'),
        description=_('Site title for the Q&A forum')
    )
)

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'APP_KEYWORDS',
        default=u'Boism,forum,community',
        description=_('Comma separated list of Q&A site keywords')
    )
)

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'APP_COPYRIGHT',
        default='Copyright Askbot, 2010-2011.',
        description=_('Copyright message to show in the footer')
    )
)

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'APP_DESCRIPTION',
        default=_('Open source question and answer forum written in '
                  'Python and Django'),
        description=_('Site description for the search engines')
    )
)

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'APP_SHORT_NAME',
        default='Boism.org',
        description=_('Short name for your Q&A forum')
    )
)


def app_url_callback(old_value, new_value):
    """validates the site url and sets
    Sites framework record"""
    # 1) validate the site url
    parsed = urlparse(new_value)
    if parsed.netloc == '':
        msg = _('Please enter url of your site')
        raise ValueError(msg)
    if parsed.scheme not in ('http', 'https'):
        msg = _('Url must start either from http or https')
        raise ValueError(msg)
    if parsed.path == '':
        new_value += '/'

    # 2) update domain name in the sites framework
    from django.contrib.sites.models import Site
    site = Site.objects.get(id=django_settings.SITE_ID)
    site.domain = parsed.netloc
    site.save()

    return new_value


settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'APP_URL',
        description=_(
            'http://boism.org/'),
        update_callback=app_url_callback
    )
)

settings.register(
    livesettings.BooleanValue(
        QA_SITE_SETTINGS,
        'ENABLE_GREETING_FOR_ANON_USER',
        default=True,
        description=_('Check to enable greeting for anonymous user')
    )
)

settings.register(
    livesettings.StringValue(
        QA_SITE_SETTINGS,
        'GREETING_FOR_ANONYMOUS_USER',
        default=_('First time here? Check out the FAQ!'),
        localized=True,
        hidden=False,
        description=_(
            'Text shown in the greeting message shown to the anonymous user'),
        help_text=_('Use HTML to format the message ')
    )
)
