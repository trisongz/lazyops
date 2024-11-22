from __future__ import annotations

"""
OAuth2 Providers
"""

from .google import GoogleOAuth2Config, GoogleOAuth2Client
from .kinde import KindeOAuth2Config, KindeOAuth2Client
from typing import Dict, Union, Type, Optional, Tuple
from lzl.load import lazy_import

ProviderConfigT = Union[
    GoogleOAuth2Config,
    KindeOAuth2Config,
]

ProviderClientT = Union[
    GoogleOAuth2Client,
    KindeOAuth2Client,
]

ProviderClasses: Dict[str , Tuple[Type[ProviderConfigT], Type[ProviderClientT]]] = {
    'google': (GoogleOAuth2Config, GoogleOAuth2Client),
    'kinde': (KindeOAuth2Config, KindeOAuth2Client),
}


def get_provider_classes(
    name: str,
    config_class: Optional[str] = None,
    client_class: Optional[str] = None,
) -> Tuple[Type[ProviderConfigT], Type[ProviderClientT]]:
    """
    Returns the provider classes
    """
    if config_class is not None:
        if config_class in locals(): config_class = locals()[config_class]
        else: config_class = lazy_import(config_class)
    
    if client_class is not None:
        if client_class in locals(): client_class = locals()[client_class]
        else: client_class = lazy_import(client_class)
    
    if config_class and client_class:
        return config_class, client_class
    
    if name in ProviderClasses:
        return ProviderClasses[name][0], ProviderClasses[name][1]
    
    if 'google' in name:
        return ProviderClasses['google'][0], ProviderClasses['google'][1]
    
    if 'kinde' in name:
        return ProviderClasses['kinde'][0], ProviderClasses['kinde'][1]
    
    # if 'auth0' in name:
    #     return ProviderClasses['auth0'][0], ProviderClasses['auth0'][1]
    raise ValueError(f'Invalid Provider: {name}')