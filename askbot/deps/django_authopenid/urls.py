from django.conf import settings as django_settings
from django.urls import re_path

if django_settings.ASKBOT_TRANSLATE_URL == True:
    from django.utils.translation import pgettext
else:
    pgettext = lambda context, value: value

from askbot.deps.django_authopenid import views as OpenidViews
from askbot.deps.django_authopenid.protocols.oidc.views import complete_oidc_signin

urlpatterns = [
    # yadis rdf
    re_path(r'^yadis.xrdf$', OpenidViews.xrdf, name='yadis_xrdf'),
     # manage account registration
    re_path(r'^%s$' % pgettext('urls', 'signin/'), OpenidViews.signin, name='user_signin'),
    re_path(r'^%s$' % pgettext('urls', 'signout/'), OpenidViews.signout, name='user_signout'),
    #this view is "complete-openid" signin
    re_path(
        r'^%s%s$' % (pgettext('urls', 'signin/'), pgettext('urls', 'complete/')),
        OpenidViews.complete_openid_signin,
        name='user_complete_openid_signin'),
    re_path(
        r'^%s%s$' % (pgettext('urls', 'signin/'), pgettext('urls', 'complete-cas/')),
        OpenidViews.complete_cas_signin,
        name='user_complete_cas_signin'),
    re_path(
        r'^signin/complete-oauth/',# % (pgettext('urls', 'signin/'), pgettext('urls', 'complete-oauth/')),
        OpenidViews.complete_oauth1_signin,
        name='user_complete_oauth1_signin'
    ),
    re_path(
        r'^signin/complete-discourse/',
        OpenidViews.complete_discourse_signin,
        name='user_complete_discourse_signin'
    ),
    re_path(
        r'^signin/complete-oauth2/',
        OpenidViews.complete_oauth2_signin,
        name='user_complete_oauth2_signin'
    ),
    re_path(
        r'^signin/complete-oidc/',
        complete_oidc_signin,
        name='user_complete_oidc_signin'
    ),
    re_path(r'^%s$' % pgettext('urls', 'register/'), OpenidViews.register, name='user_register'),
    re_path(
        r'^%s$' % pgettext('urls', 'signup/'),
        OpenidViews.signup_with_password,
        name='user_signup_with_password'
    ),
    re_path(
        r'change-password/',
        OpenidViews.change_password,
        name='change_password'
    ),
    re_path(r'^%s$' % pgettext('urls', 'logout/'), OpenidViews.logout_page, name='logout'),
    re_path(
        r'^%s$' % pgettext('urls', 'recover/'),
        OpenidViews.recover_account,
        name='user_account_recover'
    ),
    re_path(
        r'^%s$' % pgettext('urls', 'verify-email/'),
        OpenidViews.verify_email_and_register,
        name='verify_email_and_register'
    ),
    re_path(
        r'^delete_login_method/$',#this method is ajax only
        OpenidViews.delete_login_method,
        name ='delete_login_method'
    )
]
