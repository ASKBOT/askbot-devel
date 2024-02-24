# Copyright (c) 2007, 2008, Benoît Chesneau
# Copyright (c) 2007 Simon Willison, original work on django-openid
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#      * Redistributions of source code must retain the above copyright
#      * notice, this list of conditions and the following disclaimer.
#      * Redistributions in binary form must reproduce the above copyright
#      * notice, this list of conditions and the following disclaimer in the
#      * documentation and/or other materials provided with the
#      * distribution.  Neither the name of the <ORGANIZATION> nor the names
#      * of its contributors may be used to endorse or promote products
#      * derived from this software without specific prior written
#      * permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import html
import json
import logging
from django.conf import settings as django_settings
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login as _login
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import smart_str
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.views.decorators import csrf
from openid.consumer.consumer import Consumer, \
    SUCCESS, CANCEL, FAILURE, SETUP_NEEDED
from openid.consumer.discover import DiscoveryFailure
from openid.extensions import sreg
from openid.yadis import xri
from requests_oauthlib.oauth2_session import OAuth2Session
from askbot.auth import logout
from askbot import forms as askbot_forms
from askbot.conf import settings as askbot_settings
from askbot.deps.django_authopenid import forms, protocols, util
from askbot.deps.django_authopenid.models import UserAssociation, UserEmailVerifier
from askbot.deps.django_authopenid.providers.cas_provider import CASLoginProvider
from askbot.mail.messages import AccountActivation, AccountRecovery
from askbot.models import greet_new_user, AnonymousAnswer, AnonymousQuestion
from askbot.signals import user_logged_in, user_registered
from askbot.utils import decorators as askbot_decorators
from askbot.utils import url_utils
from askbot.utils.forms import get_next_url, get_next_jwt
from askbot.utils.functions import format_setting_name
from askbot.utils.functions import generate_random_key, encode_jwt
from askbot.utils.html import site_url
from askbot.deps.django_authopenid.ldap_auth import ldap_create_user
from askbot.deps.django_authopenid.ldap_auth import ldap_authenticate
from askbot.deps.django_authopenid.exceptions import OAuthError
from askbot.deps.django_authopenid.providers import discourse
from askbot.utils.http import get_request_info, get_request_params, is_ajax
from askbot.utils.loading import load_module

try:
    from xmlrpc.client import Fault as WpFault
    from wordpress_xmlrpc import Client
    from wordpress_xmlrpc.methods.users import GetUserInfo
except ImportError:
    pass


def create_authenticated_user_account(
    username=None, email=None, password=None,
    user_identifier=None, login_provider_name=None,
    request=None
):
    """creates a user account, user association with
    the login method and the the default email subscriptions
    """

    user = User.objects.create_user(username, email)
    user_registered.send(None, user=user, request=request)

    logging.debug('creating new openid user association for %s', username)

    if password:
        user.set_password(password)
        user.save()
    else:
        UserAssociation(
            openid_url = user_identifier,
            user = user,
            provider_name = login_provider_name,
            last_used_timestamp = timezone.now()
        ).save()

    subscribe_form = askbot_forms.SimpleEmailSubscribeForm({'subscribe': 'y'})
    subscribe_form.full_clean()
    logging.debug('saving email feed settings')
    subscribe_form.save(user)

    logging.debug('logging the user in')
    user = authenticate(method='force', user_id=user.id)
    if user is None:
        error_message = 'please make sure that ' + \
                        'askbot.deps.django_authopenid.backends.AuthBackend' + \
                        'is in your settings.AUTHENTICATION_BACKENDS'
        raise Exception(error_message)

    return user


def cleanup_post_register_session(request):
    """delete keys from session after registration is complete"""
    keys = (
        'user_identifier',
        'login_provider_name',
        'username',
        'email',
        'password',
        'validation_code'
    )
    for key in keys:
        if key in request.session:
            del request.session[key]


#todo: move to askbot.auth
def login(request, user):
    # get old session key
    session_key = request.session.session_key

    # login and get new session key
    _login(request, user)

    # send signal with old session key as argument
    logging.debug('logged in user %s with session key %s', user.username, session_key)
    user_logged_in.send(
                    request=request,
                    user=user,
                    session_key=session_key,
                    sender=None
                )

def logout_page(request):
    data = {'have_federated_login_methods': util.have_enabled_federated_login_methods()}
    return render(request, 'authopenid/logout.html', data)

def get_url_host(request):
    if request.is_secure():
        protocol = 'https'
    else:
        protocol = 'http'
    host = escape(request.get_host())
    return f'{protocol}://{host}'

def get_full_url(request):
    return get_url_host(request) + request.get_full_path()

def ask_openid(
            request,
            openid_url,
            redirect_to,
            sreg_request=None
        ):
    """ basic function to ask openid and return response """
    trust_root = getattr(
        django_settings, 'OPENID_TRUST_ROOT', get_url_host(request) + '/'
    )
    if xri.identifierScheme(openid_url) == 'XRI' and getattr(
            django_settings, 'OPENID_DISALLOW_INAMES', False
    ):
        msg = _("i-names are not supported")
        logging.debug('openid failed because i-names are not supported')
        return signin_failure(request, msg)
    consumer = Consumer(request.session, util.DjangoOpenIDStore())
    try:
        auth_request = consumer.begin(openid_url)
    except DiscoveryFailure:
        openid_url = html.escape(openid_url)
        msg = _("OpenID {openid_url} is invalid".format(openid_url=openid_url)) # pylint: disable=consider-using-f-string
        logging.debug(msg)
        return signin_failure(request, msg)

    logging.debug('openid seemed to work')
    if sreg_request:
        logging.debug('adding sreg_request - wtf it is?')
        auth_request.addExtension(sreg_request)
    redirect_url = auth_request.redirectURL(trust_root, redirect_to)
    logging.debug('redirecting to %s', redirect_url)
    return HttpResponseRedirect(redirect_url)


def not_authenticated(func):
    """ decorator that redirect user to next page if
    he/she is already logged in."""
    def decorated(request, *args, **kwargs):
        if request.user.is_authenticated:
            return HttpResponseRedirect(get_next_url(request))
        return func(request, *args, **kwargs)
    return decorated


def complete_discourse_signin(request):
    """Logs in a discourse user, creates an account, if needed"""
    discourse_login_session = request.session.get('discourse_login')
    nonce = discourse_login_session.get('nonce', None)
    form = discourse.DiscourseSsoForm(get_request_params(request), nonce=nonce)
    next_url = discourse_login_session.get('success_url', reverse('questions'))
    if not form.is_valid():
        # if form is invalid - show login screen with error message
        logging.error('Could not aunenticate via a Discourse site %s', str(form.errors))
        login_form = forms.LoginForm(initial={'next': next_url})
        message = _('Unfortunately, there was some problem logging in via the Discourse site')
        request.user.message_set.create(message=message)
        return show_signin_view(request, login_form=login_form)

    sso_data = form.get_sso_data()
    user_identifier = sso_data['username'] + '@discourse'

    user = authenticate(method='identifier',
                        user_identifier=user_identifier,
                        provider_name='discourse')

    request.session['username'] = sso_data['username']
    request.session['email'] = sso_data['email']

    return finalize_generic_signin(request=request,
                                   user=user,
                                   user_identifier=user_identifier,
                                   login_provider_name='discourse',
                                   redirect_url=next_url)


def complete_oauth2_signin(request):
    next_url = util.get_next_url_from_session(request.session)

    if 'error' in request.GET:
        return HttpResponseRedirect(reverse('index'))

    csrf_token = request.GET.get('state', None)
    oauth2_csrf_token = request.session.pop('oauth2_csrf_token', None)
    if csrf_token is None or csrf_token != oauth2_csrf_token:
        return HttpResponseBadRequest()

    providers = util.get_enabled_login_providers()
    provider_name = request.session.pop('provider_name')
    params = providers[provider_name]
    assert params['type'] == 'oauth2'

    name_token = format_setting_name(provider_name)
    client_id = getattr(
            askbot_settings,
            name_token + '_KEY',
        )

    client_secret = getattr(
            askbot_settings,
            name_token + '_SECRET',
        )

    session = OAuth2Session(
            redirect_uri=site_url(reverse('user_complete_oauth2_signin')),
            client_id=client_id,
            auto_refresh_url=params['token_endpoint'],
            token_updater = params.get('token_transport', None)
        )

    session.fetch_token(
        params['token_endpoint'],
        code=request.GET['code'],
        client_secret=client_secret
    )

    user_id = params['get_user_id_function'](session, params)

    user = authenticate(
                user_identifier=user_id,
                provider_name=provider_name,
                method='identifier'
            )

    logging.debug('finalizing oauth signin')

    request.session['email'] = ''#todo: pull from profile
    request.session['username'] = ''#todo: pull from profile

    if provider_name == 'facebook':
        response = session.get(params['resource_endpoint'])
        profile = params['response_parser'](response.text)
        request.session['email'] = profile.get('email', '')
        request.session['username'] = profile.get('username', '')
    elif provider_name == 'google-plus' and not user:
        #attempt to migrate user from the old OpenId protocol
        openid_url, email = util.google_gplus_get_openid_data(session)
        if openid_url:
            msg_tpl = 'trying to migrate user from OpenID %s to g-plus %s'
            logging.critical(msg_tpl, str(openid_url), str(user_id))
            user = authenticate(
                        method='identifier',
                        provider_name='google',
                        user_identifier=openid_url
                   )
            if user:
                util.google_migrate_from_openid_to_gplus(openid_url, user_id)
                logging.critical('migrated login from OpenID to g-plus')
            elif email:
                user = authenticate(
                            method='email',
                            email=email
                            #don't check whether email was validated
                        )
                if user:
                    #create association
                    assoc = UserAssociation(
                                        user=user,
                                        openid_url=user_id,
                                        provider_name='google-plus'
                                    )
                    assoc.save()

    return finalize_generic_signin(
                        request=request,
                        user=user,
                        user_identifier=user_id,
                        login_provider_name=provider_name,
                        redirect_url=next_url
                    )


def complete_cas_signin(request):
    next_url = util.get_next_url_from_session(request.session)
    provider = CASLoginProvider(success_redirect_url=next_url)
    cas_login_url = provider.get_login_url()

    ticket = request.GET.get('ticket')
    if not ticket:
        return HttpResponseRedirect(cas_login_url)

    username, _attributes, _pgtiou = provider.verify_ticket(ticket)
    if not username:
        return HttpResponseRedirect(cas_login_url)

    user_identifier = username + '@cas'

    user = authenticate(
                        method='identifier',
                        user_identifier=user_identifier,
                        provider_name='cas'
                       )

    #<----
    #settings ASKBOT_CAS_USER_FILTER, ASKBOT_CAS_GET_USERNAME, ASKBOT_CAS_GET_EMAIL
    #are temporary, to be replaced by ability to specify custom auth backend.
    user_filter_path = django_settings.ASKBOT_CAS_USER_FILTER
    if user_filter_path:
        user_filter_func = load_module(user_filter_path)
        if not user_filter_func(username):
            #de-authenticate the user
            user = None
            deny_msg = django_settings.CAS_USER_FILTER_DENIED_MSG
            if deny_msg:
                request.user.message_set.create(message=deny_msg)
                return HttpResponseRedirect(next_url)

    get_username_func_path = django_settings.ASKBOT_CAS_GET_USERNAME
    if get_username_func_path:
        get_username_func = load_module(get_username_func_path)
        request.session['username'] = get_username_func(username) or username
    else:
        request.session['username'] = username

    get_email_func_path = django_settings.ASKBOT_CAS_GET_EMAIL
    if get_email_func_path:
        get_email_func = load_module(get_email_func_path)
        request.session['email'] = get_email_func(username)
    #<----end of temp stuff

    return finalize_generic_signin(
                        request=request,
                        user=user,
                        user_identifier=user_identifier,
                        login_provider_name='cas',
                        redirect_url=next_url
                    )


def complete_oauth1_signin(request):
    next_url = util.get_next_url_from_session(request.session)

    if 'denied' in request.GET:
        return HttpResponseRedirect(next_url)
    if 'oauth_problem' in request.GET:
        return HttpResponseRedirect(next_url)

    try:
        oauth_token = request.GET['oauth_token']
        logging.debug('have token %s', oauth_token)
        oauth_verifier = request.GET['oauth_verifier']
        logging.debug('have verifier %s', oauth_verifier)
        session_oauth_token = request.session['oauth_token']
        logging.debug('have token from session')
        assert oauth_token == session_oauth_token['oauth_token']

        oauth_provider_name = request.session['oauth_provider_name']
        logging.debug('have saved provider name')
        del request.session['oauth_provider_name']

        oauth = util.OAuthConnection(oauth_provider_name)
        oauth.obtain_access_token(
                            oauth_token=session_oauth_token,
                            oauth_verifier=oauth_verifier
                        )
        user_id = oauth.get_user_id()
        request.session['email'] = oauth.get_user_email()
        request.session['username'] = oauth.get_username()

        logging.debug('have %s user id=%s', oauth_provider_name, user_id)
    except Exception as err: # pylint: disable=broad-except
        logging.critical(err)
        msg = _('Unfortunately, there was some problem when '
                'connecting to %(provider)s, please try again '
                'or use another provider'
            ) % {'provider': request.session['oauth_provider_name']}
        request.user.message_set.create(message=msg)
        return HttpResponseRedirect(next_url)
    else:
        user = authenticate(
                            method='identifier',
                            user_identifier=user_id,
                            provider_name=oauth_provider_name,
                           )

        logging.debug('finalizing oauth signin')

        return finalize_generic_signin(
                            request=request,
                            user=user,
                            user_identifier=user_id,
                            login_provider_name=oauth_provider_name,
                            redirect_url=next_url
                        )


@csrf.csrf_protect
def signin(request):
    """
    signin page. It manages the legacy authentification (user/password)
    and openid authentification

    url: /signin/

    template : authopenid/signin.htm
    """
    logging.debug('in signin view')

    askbot_login_url = url_utils.get_login_url()
    if askbot_login_url != reverse('user_signin'):
        if request.user.is_anonymous:
            return HttpResponseRedirect(askbot_login_url)


    login_redirect_url = getattr(django_settings, 'LOGIN_REDIRECT_URL', None)
    next_url = get_next_url(request, default=login_redirect_url)
    logging.debug('next url is %s', next_url)

    if not askbot_settings.ALLOW_ADD_REMOVE_LOGIN_METHODS \
        and request.user.is_authenticated:
        return HttpResponseRedirect(next_url)

    next_jwt = encode_jwt({'next_url': next_url})

    if next_url == reverse('user_signin'):
        # the sticky signin page
        next_url = f'{next_url}?next={next_jwt}'

    login_form = forms.LoginForm(initial={'next': next_jwt})

    if request.method == 'POST':

        login_form = forms.LoginForm(request.POST)
        if login_form.is_valid():
            provider_name = login_form.cleaned_data['login_provider_name']
            if login_form.cleaned_data['login_type'] == 'password':

                password_action = login_form.cleaned_data['password_action']
                if askbot_settings.USE_LDAP_FOR_PASSWORD_LOGIN:
                    assert password_action == 'login'
                    username = login_form.cleaned_data['username']
                    password = login_form.cleaned_data['password']

                    user = authenticate(
                                    method='ldap',
                                    username=username,
                                    password=password,
                                    request=request
                                )

                    if user:
                        login(request, user)
                        return HttpResponseRedirect(next_url)

                    #try to login again via LDAP
                    user_info = ldap_authenticate(username, password)
                    if user_info['success']:
                        if askbot_settings.LDAP_AUTOCREATE_USERS:
                            #create new user or
                            user = ldap_create_user(user_info, request).user
                            user = authenticate(method='force', user_id=user.pk)
                            assert user is not None
                            login(request, user)
                            return HttpResponseRedirect(next_url)

                        #continue with proper registration
                        ldap_username = user_info['ldap_username']
                        request.session['email'] = user_info['email']
                        request.session['ldap_user_info'] = user_info
                        if askbot_settings.AUTOFILL_USER_DATA:
                            request.session['username'] = ldap_username
                            request.session['first_name'] = \
                                user_info['first_name']
                            request.session['last_name'] = \
                                user_info['last_name']
                        return finalize_generic_signin(
                            request,
                            login_provider_name = 'ldap',
                            user_identifier = ldap_username + '@ldap',
                            redirect_url = next_url
                        )

                    auth_fail_func_path = getattr(
                                        django_settings,
                                        'LDAP_AUTHENTICATE_FAILURE_FUNCTION',
                                        None
                                    )

                    if auth_fail_func_path:
                        auth_fail_func = load_module(auth_fail_func_path)
                        auth_fail_func(user_info, login_form)
                    else:
                        login_form.set_password_login_error()
                    #return HttpResponseRedirect(request.path)
                else:
                    if password_action == 'login':
                        user = authenticate(
                                            method='password',
                                            username=login_form.cleaned_data['username'],
                                            password=login_form.cleaned_data['password'],
                                            provider_name=provider_name
                                           )
                        if user:
                            login(request, user)
                            return HttpResponseRedirect(next_url)

                        login_form.set_password_login_error()

                    elif password_action == 'change_password':
                        if request.user.is_authenticated:
                            new_password = \
                                login_form.cleaned_data['new_password']
                            request.user.set_password(new_password)
                            request.user.save()
                            request.user.message_set.create(
                                        message = _('Your new password is saved')
                                    )
                            return HttpResponseRedirect(next_url)
                    else:
                        logging.critical('unknown password action %s', password_action)
                        raise Http404

            elif login_form.cleaned_data['login_type'] == 'discourse':
                return HttpResponseRedirect(discourse.get_sso_login_url(request, next_url))

            elif login_form.cleaned_data['login_type'] == 'mozilla-persona':
                assertion = login_form.cleaned_data['persona_assertion']
                email = util.mozilla_persona_get_email_from_assertion(assertion)
                if email:
                    user = authenticate(
                                method='identifier',
                                user_identifier=email,
                                provider_name='mozilla-persona'
                            )
                    if user is None:
                        user = authenticate(email=email, method='email')
                        if user and not user.email_isvalid:
                            user = None
                        if user:
                            #create mozilla persona user association
                            #because we trust the given email address belongs
                            #to the same user
                            UserAssociation(
                                openid_url=email,
                                user=user,
                                provider_name='mozilla-persona',
                                last_used_timestamp=timezone.now()
                            ).save()

                    if user:
                        login(request, user)
                        return HttpResponseRedirect(next_url)

                    #else - create new user account
                    #pre-fill email address with persona registration
                    request.session['email'] = email
                    return finalize_generic_signin(
                        request,
                        login_provider_name='mozilla-persona',
                        user_identifier=email,
                        redirect_url=next_url
                    )

            elif login_form.cleaned_data['login_type'] == 'openid':
                #initiate communication process
                logging.debug('processing signin with openid submission')

                if login_form.cleaned_data['sreg_required']:
                    sreg_req = sreg.SRegRequest(required=['nickname', 'email'])
                else:
                    sreg_req = sreg.SRegRequest(optional=['nickname', 'email'])

                next_jwt = encode_jwt({'next_url': next_url})
                host_url = get_url_host(request)
                path_url = reverse('user_complete_openid_signin')
                redirect_to = f"{host_url}{path_url}?next={next_jwt}"

                return ask_openid(
                            request,
                            login_form.cleaned_data['openid_url'],
                            redirect_to,
                            sreg_request=sreg_req
                        )

            elif login_form.cleaned_data['login_type'] == 'cas':
                provider = CASLoginProvider(success_redirect_url=next_url)
                request.session['next_url'] = next_url
                return HttpResponseRedirect(provider.get_login_url())

            elif login_form.cleaned_data['login_type'] == 'oauth':
                try:
                    #this url may need to have "next" piggibacked onto
                    connection = util.OAuthConnection(provider_name)
                    connection.start(
                        callback_url=reverse('user_complete_oauth1_signin')
                    )

                    request.session['oauth_token'] = connection.get_token()
                    request.session['oauth_provider_name'] = provider_name
                    request.session['next_url'] = next_url#special case for oauth

                    oauth_url = connection.get_auth_url(login_only=True)
                    return HttpResponseRedirect(oauth_url)

                except OAuthError as err:
                    logging.critical(str(err))
                    msg = _('Unfortunately, there was some problem when '
                            'connecting to %(provider)s, please try again '
                            'or use another provider'
                        ) % {'provider': provider_name}
                    request.user.message_set.create(message=msg)

            elif login_form.cleaned_data['login_type'] == 'oauth2':
                try:
                    csrf_token = generate_random_key(length=32)
                    redirect_url = util.get_oauth2_starter_url(provider_name, csrf_token)
                    request.session['oauth2_csrf_token'] = csrf_token
                    request.session['provider_name'] = provider_name
                    request.session['next_url'] = next_url
                    return HttpResponseRedirect(redirect_url)
                except OAuthError as err:
                    logging.critical(str(err))
                    msg = _('Unfortunately, there was some problem when '
                            'connecting to %(provider)s, please try again '
                            'or use another provider'
                        ) % {'provider': provider_name}
                    request.user.message_set.create(message=msg)

            elif login_form.cleaned_data['login_type'] == 'oidc':
                csrf_token = generate_random_key(length=32)
                request.session['auth_csrf_token'] = csrf_token
                request.session['provider_name'] = provider_name
                request.session['next_url'] = next_url
                oidc = protocols.get_protocol(provider_name)
                redirect_url = site_url(reverse('user_complete_oidc_signin'))
                oidc_auth_url = oidc.get_authentication_url(redirect_url, csrf_token=csrf_token)
                return HttpResponseRedirect(oidc_auth_url)

            elif login_form.cleaned_data['login_type'] == 'wordpress_site':
                #here wordpress_site means for a self hosted wordpress blog not a wordpress.com blog
                wp_cli = Client(
                            askbot_settings.WORDPRESS_SITE_URL,
                            login_form.cleaned_data['username'],
                            login_form.cleaned_data['password']
                        )
                try:
                    wp_user = wp_cli.call(GetUserInfo())
                    wp_user_identifier = f'{wp_cli.url}?user_id={wp_user.user_id}'
                    user = authenticate(
                                        method='identifier',
                                        user_identifier=wp_user_identifier,
                                        provider_name='wordpress_site'
                                       )
                    return finalize_generic_signin(
                                    request=request,
                                    user=user,
                                    user_identifier=wp_user_identifier,
                                    login_provider_name=provider_name,
                                    redirect_url=next_url
                                )
                except WpFault as err:
                    logging.critical(str(err))
                    msg = _('The login password combination was not correct')
                    request.user.message_set.create(message=msg)
            else:
                #raise 500 error - unknown login type
                pass
        else:
            logging.debug('login form is not valid')
            logging.debug(login_form.errors)

    if request.method == 'GET' and request.user.is_authenticated:
        view_subtype = 'change_openid'
    else:
        view_subtype = 'default'

    return show_signin_view(request,
                            login_form=login_form,
                            view_subtype=view_subtype)

@csrf.csrf_protect
def show_signin_view(request,
                     login_form=None,
                     account_recovery_form=None,
                     account_recovery_message=None,
                     sticky=False,
                     view_subtype='default'):
    """url-less utility function that populates
    context of template 'authopenid/signin.html'
    and returns its rendered output
    """

    allowed_subtypes = (
                    'default', 'add_openid',
                    'email_sent', 'change_openid'
                )

    assert view_subtype in allowed_subtypes

    if sticky:
        next_url = reverse('user_signin')
    else:
        next_url = get_next_url(request)

    if login_form is None:
        next_jwt = encode_jwt({'next_url': next_url})
        login_form = forms.LoginForm(initial = {'next': next_jwt})

    if account_recovery_form is None:
        account_recovery_form = forms.AccountRecoveryForm()#initial = initial_data)

    #if request is GET
    if request.method == 'GET':
        logging.debug('request method was GET')

    # todo: this must be executed on some signal
    # because askbot should have nothing to do with the login app
    session_key = request.session.session_key
    logging.debug('retrieving anonymously posted question associated with session %s', session_key)
    qlist = AnonymousQuestion.objects.filter(session_key=session_key).order_by('-added_at') #pylint: disable=no-member
    if len(qlist) > 0:
        question = qlist[0]
    else:
        question = None

    session_key = request.session.session_key
    logging.debug('retrieving posted answer associated with session %s', session_key)
    alist = AnonymousAnswer.objects.filter(session_key=session_key).order_by('-added_at') #pylint: disable=no-member
    if len(alist) > 0:
        answer = alist[0]
    else:
        answer = None

    if request.user.is_authenticated:
        existing_login_methods = UserAssociation.objects.filter(user=request.user) #pylint: disable=no-member
        #annotate objects with extra data
        providers = util.get_enabled_login_providers()
        for login_method in existing_login_methods:
            try:
                provider_data = providers[login_method.provider_name]
                if provider_data['type'] == 'password':
                    #only external password logins will not be deletable
                    #this is because users with those can lose access to their accounts permanently
                    login_method.is_deletable = provider_data.get('password_changeable', False)
                else:
                    login_method.is_deletable = True
            except KeyError:
                logging.critical(
                    'login method %s is no longer available '
                    'please delete records for this login method '
                    'from the UserAssociation table',
                    login_method.provider_name
                )
                continue



    if view_subtype == 'default':
        page_title = _('Click any of the icons below to sign in')
    elif view_subtype == 'email_sent':
        page_title = _('Account recovery email sent')
    elif view_subtype == 'change_openid':
        if len(existing_login_methods) == 0:
            page_title = _('Add at least one login method')
        else:
            page_title = _('If you wish, please add, remove or re-validate your login methods')
    elif view_subtype == 'add_openid':
        if len(existing_login_methods) == 0:
            page_title = _('Add at least one login method')
        else:
            page_title = _('Please wait a second! Your account is recovered, but ...')

    logging.debug('showing signin view')
    data = {
        'account_recovery_form': account_recovery_form,
        'account_recovery_message': account_recovery_message,
        'answer': answer,
        'login_form': login_form,
        'openid_error_message':  request.GET.get('msg',request.POST.get('msg','')),
        'page_title': page_title,
        'question': question,
        'use_password_login': util.use_password_login(),
        'view_subtype': view_subtype, #add_openid|default
    }

    major_login_providers = util.get_enabled_major_login_providers()
    minor_login_providers = util.get_enabled_minor_login_providers()

    #determine if we are only using password login
    active_provider_names = [p['name'] for p in list(major_login_providers.values())]
    active_provider_names.extend([p['name'] for p in list(minor_login_providers.values())])

    have_buttons = True
    if (len(active_provider_names) == 1 and active_provider_names[0] == 'local'):
        have_buttons = False
        login_form.initial['login_provider_name'] = 'local'
        if request.user.is_authenticated:
            login_form.initial['password_action'] = 'change_password'
        else:
            login_form.initial['password_action'] = 'login'

    data['have_buttons'] = have_buttons

    if request.user.is_authenticated:
        data['existing_login_methods'] = existing_login_methods
        active_provider_names = [
                        item.provider_name for item in existing_login_methods
                    ]

    util.set_login_provider_tooltips(
                        major_login_providers,
                        active_provider_names = active_provider_names
                    )
    util.set_login_provider_tooltips(
                        minor_login_providers,
                        active_provider_names = active_provider_names
                    )

    data['major_login_providers'] = list(major_login_providers.values())
    data['minor_login_providers'] = list(minor_login_providers.values())

    return render(request, 'authopenid/signin.html', data)

@csrf.csrf_protect
@askbot_decorators.post_only
@askbot_decorators.ajax_login_required
def change_password(request):
    form = forms.ChangePasswordForm(request.POST)
    data = {}
    if form.is_valid():
        request.user.set_password(form.cleaned_data['new_password'])
        request.user.save()
        data['message'] = _('Your new password is saved')
    else:
        data['errors'] = form.errors
    return HttpResponse(json.dumps(data), content_type='application/json')

@login_required
def delete_login_method(request):
    if askbot_settings.ALLOW_ADD_REMOVE_LOGIN_METHODS is False:
        raise Http404
    if is_ajax(request) and request.method == 'POST':
        provider_name = request.POST['provider_name']
        try:
            login_method = UserAssociation.objects.get(user=request.user, #pylint: disable=no-member
                                                       provider_name=provider_name)
            login_method.delete()
            return HttpResponse('', content_type='application/json')
        except UserAssociation.DoesNotExist: #pylint: disable=no-member
            #error response
            message = _('Login method %(provider_name)s does not exist')
            return HttpResponse(message, status=500, content_type='application/json')
        except UserAssociation.MultipleObjectsReturned: #pylint: disable=no-member
            logging.critical('have multiple %s logins for user %s',
                             provider_name,
                             request.user.id)
            message = _('Oops, sorry - there was some error - please try again')
            return HttpResponse(message, status=500, content_type='application/json')
    else:
        raise Http404

def complete_openid_signin(request):
    """ in case of complete signin with openid """
    logging.debug('in askbot.deps.django_authopenid.complete')
    consumer = Consumer(request.session, util.DjangoOpenIDStore())
    # make sure params are encoded in utf8
    params = dict((k, smart_str(v)) for k, v in list(request.GET.items()))
    return_to = get_url_host(request) + reverse('user_complete_openid_signin')
    openid_response = consumer.complete(params, return_to)

    logging.debug('returned openid parameters were: %s', str(params))

    if openid_response.status == SUCCESS:
        logging.debug('openid response status is SUCCESS')
        return signin_success(
                    request,
                    openid_response.identity_url,
                    openid_response
                )

    if openid_response.status == CANCEL:
        logging.debug('CANCEL')
        return signin_failure(request, 'The request was canceled')
    if openid_response.status == FAILURE:
        logging.debug('FAILURE')
        return signin_failure(request, openid_response.message)
    if openid_response.status == SETUP_NEEDED:
        logging.debug('SETUP NEEDED')
        return signin_failure(request, 'Setup needed')

    logging.debug('BAD OPENID STATUS')
    assert False, f"Bad openid status: {openid_response.status}"


def signin_success(request, _identity_url, openid_response):
    """
    this is not a view, has no url pointing to this

    this function is called when OpenID provider returns
    successful response to user authentication

    Does actual authentication in Django site and
    redirects to the registration page, if necessary
    or adds another login method.
    """

    logging.debug('')
    openid_data = util.from_openid_response(openid_response) #create janrain OpenID object
    request.session['openid'] = openid_data

    openid_url = str(openid_data)
    provider_name = util.get_provider_name_by_endpoint(openid_url)
    if provider_name is None:
        provider_name = util.get_provider_name(openid_url)

    user = authenticate(
                    method='identifier',
                    user_identifier=openid_url,
                    provider_name=provider_name
                )

    next_url = get_next_url(request)
    request.session['email'] = openid_data.sreg.get('email', '')
    request.session['username'] = openid_data.sreg.get('nickname', '')

    return finalize_generic_signin(
                        request=request,
                        user=user,
                        user_identifier=openid_url,
                        login_provider_name=provider_name,
                        redirect_url=next_url
                    )

def finalize_generic_signin(
                    request=None,
                    user=None,
                    login_provider_name=None,
                    user_identifier=None,
                    redirect_url=None
                ):
    """non-view function
    generic signin, run after all protocol-dependent details
    have been resolved
    """

    if 'in_recovery' in request.session:
        del request.session['in_recovery']
        redirect_url = getattr(django_settings, 'LOGIN_REDIRECT_URL', reverse('questions'))

    if request.user.is_authenticated:
        #this branch is for adding a new association
        if user is None:
            try:
                #see if currently logged in user has login with the given provider
                UserAssociation.objects.get(user=request.user, #pylint: disable=no-member
                                            provider_name=login_provider_name)
                logging.info('switching account or open id changed???')
                #did openid url change? or we are dealing with a brand new open id?
                message = _(
                    'If you are trying to sign in to another account, '
                    'please sign out first. Otherwise, please report the incident '
                    'to the site administrator.'
                )
                request.user.message_set.create(message=message)
                return HttpResponseRedirect(redirect_url)
            except UserAssociation.DoesNotExist: #pylint: disable=no-member
                #register new association
                UserAssociation(
                    user=request.user,
                    provider_name=login_provider_name,
                    openid_url=user_identifier,
                    last_used_timestamp=timezone.now()
                ).save()
                return HttpResponseRedirect(redirect_url)

        if user != request.user:
            #prevent theft of account by another pre-existing user
            logging.critical('possible account theft attempt by %s,%d to %s %d',
                             request.user.username,
                             request.user.id,
                             user.username,
                             user.id)
            logout(request) # log out current user
            login(request, user) # login freshly authenticated user
            return HttpResponseRedirect(redirect_url)

        #user just checks if another login still works
        msg = _('Your %(provider)s login works fine') % \
                {'provider': login_provider_name}
        request.user.message_set.create(message = msg)
        return HttpResponseRedirect(redirect_url)

    if user:
        #login branch
        login(request, user)
        logging.debug('login success')
        return HttpResponseRedirect(redirect_url)

    #needs to register
    request.method = 'GET'#this is not a good thing to do
    #but necessary at the moment to reuse the register() method
    return register(
                request,
                login_provider_name=login_provider_name,
                user_identifier=user_identifier,
                redirect_url=redirect_url
            )

@not_authenticated
@csrf.csrf_protect
def register(request, login_provider_name=None,
    user_identifier=None, redirect_url=None):
    """
    this function is used via it's own url with request.method=POST
    or as a simple function call from "finalize_generic_signin"
    in which case request.method must ge 'GET'
    and login_provider_name and user_identifier arguments must not be None

    user_identifier will be stored in the UserAssociation as openid_url
    login_provider_name - as provider_name

    this function may need to be refactored to simplify the usage pattern

    template : authopenid/complete.html
    """

    registration_enabled = (not askbot_settings.NEW_REGISTRATIONS_DISABLED)

    logging.debug('')

    next_url = redirect_url or get_next_url(request)

    username = request.session.get('username', '')
    email = request.session.get('email', '')

    #1) handle "one-click registration"
    if registration_enabled and login_provider_name:

        def email_is_acceptable(email):
            email = email.strip()

            is_blank = (email == '')
            is_blank_and_ok = is_blank \
                                and askbot_settings.BLANK_EMAIL_ALLOWED \
                                and askbot_settings.REQUIRE_VALID_EMAIL_FOR == 'nothing'
            if is_blank_and_ok:
                return True

            blacklisting_on = askbot_settings.BLACKLISTED_EMAIL_PATTERNS_MODE != 'disabled'
            is_blacklisted = blacklisting_on and util.email_is_blacklisted(email)
            is_good = not is_blacklisted

            is_available = User.objects.filter(email__iexact=email).count() == 0

            return is_available and is_good

        def username_is_acceptable(username):
            if username.strip() == '':
                return False
            return User.objects.filter(username__iexact=username).count() == 0

        #new style login providers support one click registration
        providers = util.get_enabled_login_providers()
        provider_data = providers.get(login_provider_name)

        if provider_data and hasattr(provider_data, 'one_click_registration') \
            and provider_data.one_click_registration:

            if username_is_acceptable(username) and email_is_acceptable(email):
                #try auto-registration and redirect to the next_url
                user = create_authenticated_user_account(
                            username=username,
                            email=email,
                            user_identifier=user_identifier,
                            login_provider_name=login_provider_name,
                            request=request
                        )
                login(request, user)
                cleanup_post_register_session(request)
                return HttpResponseRedirect(next_url)
        #end of one-click registration

    user = None
    logging.debug('request method is %s', request.method)

    form_class = forms.get_federated_registration_form_class()
    register_form = form_class(
                request=request,
                initial={
                    'next': encode_jwt({'next_url': next_url}),
                    'username': request.session.get('username', ''),
                    'email': request.session.get('email', ''),
                }
            )

    if (not registration_enabled) or request.method == 'GET':
        try:
            assert login_provider_name is not None
            assert user_identifier is not None
        except AssertionError:
            return HttpResponseRedirect(reverse('user_signin'))
        #store this data into the session
        #to persist for the post request
        request.session['login_provider_name'] = login_provider_name
        request.session['user_identifier'] = user_identifier

    elif request.method == 'POST':

        if 'login_provider_name' not in request.session \
            or 'user_identifier' not in request.session:
            logging.critical('illegal attempt to register')
            return HttpResponseRedirect(reverse('user_signin'))

        #load this data from the session
        user_identifier = request.session['user_identifier']
        login_provider_name = request.session['login_provider_name']

        logging.debug('trying to create new account associated with openid')
        form_class = forms.get_federated_registration_form_class()
        register_form = form_class(request.POST, request=request)
        if not register_form.is_valid():
            logging.debug('registration form is INVALID')
        else:
            username = register_form.cleaned_data['username']
            email = register_form.cleaned_data['email']

            if 'ldap_user_info' in request.session:
                user_info = request.session['ldap_user_info']
                #we take this info from the user input where
                #they can override the default provided by LDAP
                user_info['django_username'] = username
                user_info['email'] = email
                user = ldap_create_user(user_info, request).user
                user = authenticate(user_id=user.id, method='force')
                del request.session['ldap_user_info']
                login(request, user)
                cleanup_post_register_session(request)
                return HttpResponseRedirect(next_url)

            if askbot_settings.REQUIRE_VALID_EMAIL_FOR == 'nothing':
                user = create_authenticated_user_account(
                            username=username,
                            email=email,
                            user_identifier=user_identifier,
                            login_provider_name=login_provider_name,
                            request=request
                        )
                login(request, user)
                cleanup_post_register_session(request)
                return HttpResponseRedirect(next_url)

            email_verifier = UserEmailVerifier(key=generate_random_key())
            email_verifier.value = {'username': username, 'email': email,
                                    'user_identifier': user_identifier,
                                    'login_provider_name': login_provider_name}
            email_verifier.save()
            send_email_key(email, email_verifier.key,
                           email_type='verify_email_and_register')
            next_jwt = encode_jwt({'next_url': next_url})
            redirect_url = reverse('verify_email_and_register') + '?next=' + next_jwt
            return HttpResponseRedirect(redirect_url)

    providers = {
            'yahoo':'<font color="purple">Yahoo!</font>',
            'flickr':'<font color="#0063dc">flick</font><font color="#ff0084">r</font>&trade;',
            'google':'Google&trade;',
            'aol':'<font color="#31658e">AOL</font>',
            'myopenid':'MyOpenID',
        }
    if login_provider_name not in providers:
        provider_logo = login_provider_name
    else:
        provider_logo = providers[login_provider_name]

    logging.debug('printing authopenid/complete.html output')
    data = {
        'openid_register_form': register_form,
        'account_recovery_form': forms.AccountRecoveryForm(),
        'default_form_action': url_utils.get_login_url(),
        'provider': mark_safe(provider_logo),
        'username': username,
        'email': email,
        'login_type':'openid',
        'gravatar_faq_url':reverse('faq') + '#gravatar',
    }
    return render(request, 'authopenid/complete.html', data)

def signin_failure(request, message):
    """
    falure with openid signin. Go back to signin page.
    """
    request.user.message_set.create(message = message)
    return show_signin_view(request)

@not_authenticated
@csrf.csrf_protect
def verify_email_and_register(request):
    """for POST request - check the validation code,
    and if correct - create an account an log in the user

    for GET - give a field to paste the activation code
    and a button to send another validation email.
    """
    presented_code = request.GET.get('validation_code',request.POST.get('validation_code',None))
    if presented_code:
        try:
            #we get here with post if button is pushed
            #or with "get" if emailed link is clicked
            email_verifier = UserEmailVerifier.objects.get(key=presented_code) #pylint: disable=no-member
            #verifies that the code has not been used already
            assert email_verifier.verified is False
            assert email_verifier.has_expired() is False

            username = email_verifier.value['username']
            email = email_verifier.value['email']
            password = email_verifier.value.get('password', None)
            user_identifier = email_verifier.value.get('user_identifier', None)
            login_provider_name = email_verifier.value.get('login_provider_name', None)

            if password:
                user = create_authenticated_user_account(
                    username=username,
                    email=email,
                    password=password,
                    request=request
                )
            elif user_identifier and login_provider_name:
                user = create_authenticated_user_account(
                    username=username,
                    email=email,
                    user_identifier=user_identifier,
                    login_provider_name=login_provider_name,
                    request=request
                )
            else:
                raise NotImplementedError()

            login(request, user)
            email_verifier.verified = True
            email_verifier.save()
            cleanup_post_register_session(request)

            return HttpResponseRedirect(get_next_url(request))
        except Exception as error: #pylint: disable=broad-except
            logging.critical('Could not verify account: %s', str(error).encode('utf-8'))
            message = _(
                'Sorry, registration failed. '
                'The token can be already used or has expired. Please try again'
            )
            request.user.message_set.create(message=message)
            return HttpResponseRedirect(reverse('index'))
    return render(request, 'authopenid/verify_email.html')

@not_authenticated
@csrf.csrf_protect
def signup_with_password(request):
    """Create a password-protected account
    template: authopenid/signup_with_password.html
    """
    logging.debug(get_request_info(request))
    login_form = forms.LoginForm(initial = {'next': get_next_jwt(request)})
    #this is safe because second decorator cleans this field

    RegisterForm = forms.get_password_registration_form_class() #pylint: disable=invalid-name

    logging.debug('request method was %s', request.method)
    if request.method == 'POST':
        form = RegisterForm(request.POST, request=request)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            email = form.cleaned_data['email']

            if askbot_settings.REQUIRE_VALID_EMAIL_FOR == 'nothing':
                user = create_authenticated_user_account(
                    username=username,
                    email=email,
                    password=password,
                    request=request
                )
                login(request, user)
                cleanup_post_register_session(request)
                return HttpResponseRedirect(get_next_url(request))

            email_verifier = UserEmailVerifier(key=generate_random_key())
            email_verifier.value = {'username': username,
                                    'login_provider_name': 'local',
                                    'email': email, 'password': password}
            email_verifier.save()

            send_email_key(email, email_verifier.key,
                           email_type='verify_email_and_register')
            redirect_url = reverse('verify_email_and_register') + \
                            '?next=' + get_next_jwt(request)
            return HttpResponseRedirect(redirect_url)
    else:
        #todo: here we have duplication of get_password_login_provider...
        form = RegisterForm(initial={'next': get_next_jwt(request)}, request=request)

    major_login_providers = util.get_enabled_major_login_providers()
    minor_login_providers = util.get_enabled_minor_login_providers()

    context_data = {
        'form': form,
        'major_login_providers': list(major_login_providers.values()),
        'minor_login_providers': list(minor_login_providers.values()),
        'login_form': login_form
    }
    return render(request,
                  'authopenid/signup_with_password.html',
                  context_data)

@login_required
def signout(request):
    """
    signout from the website. Remove openid from session and kill it.

    url : /signout/"
    """
    try:
        del request.session['openid']
    except KeyError:
        pass
    logout(request)
    return HttpResponseRedirect(get_next_url(request))

XRDF_TEMPLATE = """<?xml version='1.0' encoding='UTF-8'?>
<xrds:XRDS
   xmlns:xrds='xri://$xrds'
   xmlns:openid='http://openid.net/xmlns/1.0'
   xmlns='xri://$xrd*($v*2.0)'>
 <XRD>
   <Service>
     <Type>http://specs.openid.net/auth/2.0/return_to</Type>
     <URI>%(return_to)s</URI>
   </Service>
 </XRD>
</xrds:XRDS>"""

def xrdf(request):
    url_host = get_url_host(request)
    url_path = reverse('user_complete_openid_signin')
    return_to = f'{url_host}{url_path}'
    return HttpResponse(XRDF_TEMPLATE % {'return_to': return_to})

def set_new_email(user, new_email):
    if new_email != user.email:
        user.email = new_email
        user.email_isvalid = False
        user.save()

def send_email_key(address, key, email_type='user_account_recover'):
    """private function. sends email containing validation key
    to user's email address
    """
    if email_type == 'user_account_recover':
        email_class = AccountRecovery
    elif email_type == 'verify_email_and_register':
        email_class = AccountActivation
    else:
        raise ValueError(f'Unrecognized email_type={email_type}')

    email = email_class({'key': key})
    email.send([address,])

def send_user_new_email_key(user):
    user.email_key = generate_random_key()
    user.save()
    send_email_key(user.email, user.email_key)

def recover_account(request):
    """view similar to send_email_key, except
    it allows user to recover an account by entering
    his/her email address

    this view will both - send the recover link and
    process it

    url name 'user_account_recover'
    """
    if not askbot_settings.ALLOW_ACCOUNT_RECOVERY_BY_EMAIL:
        raise Http404
    if request.method == 'POST' and 'validation_code' not in request.POST:
        form = forms.AccountRecoveryForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            send_user_new_email_key(user)
            return render(request, 'authopenid/verify_email.html')
        return show_signin_view(request, account_recovery_form=form)

    key = get_request_params(request).get('validation_code', None)
    return auth_user_by_token(request, key)

def auth_user_by_token(request, key):
    """Non-view function.
    Try to log in user via account recovery `key`.
    This key is normally sent to the user to help recover account by email.

    In the case of success - logs in
    and shows user the current login methods,
    so that user has a chance to change the password or
    add an authentication method.

    TODO: instead of using sub-branch of the login view
    create a dedicated view.

    In the case of failure - redirects to the authentication page
    """

    if key is None:
        return HttpResponseRedirect(reverse('user_signin'))

    user = authenticate(email_key=key, method='email_key')
    if user:
        if request.user.is_authenticated and user != request.user:
            logout(request)
        login(request, user)
        greet_new_user(user)
        #need to show "sticky" signin view here
        request.session['in_recovery'] = True
        return show_signin_view(request, view_subtype='add_openid', sticky=True)

    data = {
        'account_recovery_form': forms.AccountRecoveryForm(),
        'bad_key': True,
        'message': _('Sorry, this account recovery key has expired or is invalid')
    }
    return render(request, 'authopenid/recover_account.html', data)
