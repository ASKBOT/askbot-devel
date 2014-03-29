# -*- coding: utf-8 -*-
from django.conf import settings as django_settings
from django.conf.urls import patterns, url

if django_settings.ASKBOT_TRANSLATE_URL == True:
    from django.utils.translation import ugettext as _
else:
    _ = lambda val: val

urlpatterns = patterns('askbot.deps.django_authopenid.views',
    # yadis rdf
    url(r'^yadis.xrdf$', 'xrdf', name='yadis_xrdf'),
     # manage account registration
    url(r'^%s$' % _('signin/'), 'signin', name='user_signin'),
    url(r'^%s$' % _('widget/signin/'), 'signin',
        {'template_name': 'authopenid/widget_signin.html'},
        name='widget_signin'),
    url(r'^%s$' % _('signout/'), 'signout', name='user_signout'),
    #this view is "complete-openid" signin
    url(r'^%s%s$' % (_('signin/'), _('complete/')), 'complete_signin',
        name='user_complete_signin'),
    url(
        r'^%s%s$' % (_('signin/'), _('complete-oauth/')),
        'complete_oauth_signin',
        name='user_complete_oauth_signin'
    ),
    url(
        r'^signin/complete-oauth2/',
        'complete_oauth2_signin',
        name='user_complete_oauth2_signin'
    ),
    url(r'^%s$' % _('register/'), 'register', name='user_register'),
    url(
        r'^%s$' % _('signup/'),
        'signup_with_password',
        name='user_signup_with_password'
    ),
    url(
        r'change-password/',
        'change_password',
        name='change_password'
    ),
    url(r'^%s$' % _('logout/'), 'logout_page', name='logout'),
    #these two commeted out urls should work only with EMAIL_VALIDATION=True
    #but the setting is disabled right now
    #url(r'^%s%s$' % (_('email/'), _('sendkey/')), 'send_email_key', name='send_email_key'),
    #url(r'^%s%s(?P<id>\d+)/(?P<key>[\dabcdef]{32})/$' % (_('email/'), _('verify/')), 'verifyemail', name='user_verifyemail'),
    url(r'^%s$' % _('recover/'), 'account_recover', name='user_account_recover'),
    url(
        r'^%s$' % _('verify-email/'),
        'verify_email_and_register',
        name='verify_email_and_register'
    ),
    url(
        r'^delete_login_method/$',#this method is ajax only
        'delete_login_method',
        name ='delete_login_method'
    ),
)
