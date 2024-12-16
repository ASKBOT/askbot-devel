"""Views for the OpenID Connect - OIDC protocol"""
import logging
from django.conf import settings as django_settings
from django.contrib.auth import authenticate
from django.http import HttpResponseBadRequest
from django.utils import timezone
from django.urls import reverse
from askbot.deps.django_authopenid import util
from askbot.deps.django_authopenid.models import UserAssociation
from askbot.deps.django_authopenid.views import finalize_generic_signin
from askbot.deps.django_authopenid.protocols import get_protocol
from askbot.utils.html import site_url

LOG = logging.getLogger()

def complete_oidc_signin(request): #pylint: disable=too-many-return-statements
    """Callback for the OIDC authentication"""
    try:
        provider_name = request.session.pop('provider_name')
    except KeyError:
        provider_name = django_settings.OIDC_LOGIN_PROVIDER_NAME

    try:
        oidc = get_protocol(provider_name)
    except Exception as error: # pylint: disable=broad-except
        return HttpResponseBadRequest(
            f'Could not initialize authentication for {provider_name} {error}'
        )

    if oidc.protocol_type != 'oidc':
        return HttpResponseBadRequest('Incorrect protocol type')

    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("The code was not returned or is not accessible")

    token_info = oidc.execute_token_exchange(code, site_url(reverse('user_complete_oidc_signin')))

    # Get tokens and validate
    if not token_info.get("token_type"):
        return HttpResponseBadRequest("Unsupported token type. Should be 'Bearer'.")

    id_token = token_info["id_token"]

    #if not oidc.is_access_token_valid(access_token):
    #    return HttpResponseBadRequest("Access token is invalid")

    auth_csrf_token = request.session.pop('auth_csrf_token')
    if not oidc.is_id_token_valid(id_token, auth_csrf_token):
        return HttpResponseBadRequest("ID token is invalid")

    access_token = token_info["access_token"]
    if not oidc.is_user_authorized(access_token):
        return HttpResponseBadRequest("You do not have access to this resource")

    user_id = oidc.get_user_id(id_token)

    email = oidc.get_email(id_token)

    user = authenticate(user_identifier=user_id,
                        provider_name=provider_name,
                        method='identifier')

    if not user:
        LOG.critical('OIDC LOGIN: user with user_identifier=%s not found, need to authenticate by email %s', user_id, email)

    if not user and email and oidc.trust_email:
        LOG.critical('OIDC LOGIN: trying to authenticate user email %s', email)
        user = authenticate(method='email', email=email)
        if user:
            LOG.critical('OIDC LOGIN: user id=%s found by email %s', user.id, email)
            UserAssociation(
                user=user,
                provider_name=provider_name,
                openid_url=user_id,
                last_used_timestamp=timezone.now()
            ).save()
        else:
            LOG.critical('OIDC LOGIN: user with email=%s not found, inviting to register', email)

    request.session['email'] = email
    request.session['username'] = oidc.get_username(id_token)

    return finalize_generic_signin(request=request,
                                   user=user,
                                   user_identifier=user_id,
                                   login_provider_name=provider_name,
                                   redirect_url=util.get_next_url_from_session(request.session))
