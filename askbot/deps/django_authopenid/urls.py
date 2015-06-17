# -*- coding: utf-8 -*-
from django.conf import settings as django_settings
try:
    from django.conf.urls import patterns, url
except ImportError:
    from django.conf.urls.defaults import patterns, url

if django_settings.ASKBOT_TRANSLATE_URL == True:
    from django.utils.translation import pgettext
else:
    pgettext = lambda context, value: value

urlpatterns = patterns('askbot.deps.django_authopenid.views',
    # yadis rdf
    url(r'^yadis.xrdf$', 'xrdf', name='yadis_xrdf'),
     # manage account registration
    url(r'^%s$' % pgettext('urls', 'signin/'), 'signin', name='user_signin'),
    url(
        r'^%s%s$' % (pgettext('urls', 'widget/'), pgettext('urls', 'signin/')),
        'signin',
        {'template_name': 'authopenid/widget_signin.html'},
        name='widget_signin'
    ),
    url(r'^%s$' % pgettext('urls', 'signout/'), 'signout', name='user_signout'),
    #this view is "complete-openid" signin
    url(
        r'^%s%s$' % (pgettext('urls', 'signin/'), pgettext('urls', 'complete/')),
        'complete_signin',
        name='user_complete_signin'),
    url(
        r'^signin/complete-oauth/',# % (pgettext('urls', 'signin/'), pgettext('urls', 'complete-oauth/')),
        'complete_oauth1_signin',
        name='user_complete_oauth1_signin'
    ),
    url(
        r'^signin/complete-oauth2/',
        'complete_oauth2_signin',
        name='user_complete_oauth2_signin'
    ),
    url(r'^%s$' % pgettext('urls', 'register/'), 'register', name='user_register'),
    url(
        r'^%s$' % pgettext('urls', 'signup/'),
        'signup_with_password',
        name='user_signup_with_password'
    ),
    url(
        r'change-password/',
        'change_password',
        name='change_password'
    ),
    url(r'^%s$' % pgettext('urls', 'logout/'), 'logout_page', name='logout'),
    url(
        r'^%s$' % pgettext('urls', 'recover/'),
        'recover_account',
        name='user_account_recover'
    ),
    url(
        r'^%s$' % pgettext('urls', 'verify-email/'),
        'verify_email_and_register',
        name='verify_email_and_register'
    ),
    url(
        r'^delete_login_method/$',#this method is ajax only
        'delete_login_method',
        name ='delete_login_method'
    ),
)
