"""Module to hold supported Authentication protocols"""
def get_protocol(provider_name):
    """Returns authentication protocol object"""
    from askbot.deps.django_authopenid.util import get_enabled_login_providers
    from askbot.deps.django_authopenid.protocols.oidc.protocol import OidcProtocol
    providers = get_enabled_login_providers()
    params = providers[provider_name]

    protocol_type = params['type']
    if protocol_type == 'oidc':
        return OidcProtocol(audience=params['oidc_audience'],
                            client_id=params['oidc_client_id'],
                            client_secret=params['oidc_client_secret'],
                            provider_url=params['oidc_provider_url'],
                            authorization_function=params['oidc_authorization_function'],
                            trust_email=params['trust_email'])

    raise NotImplementedError(f'Not implemented for  protocol {protocol_type}')
