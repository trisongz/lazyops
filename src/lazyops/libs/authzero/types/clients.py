from __future__ import annotations

"""
AuthZero Clients
"""
from .base import BaseModel
from pydantic import Field, PrivateAttr
from ..utils.lazy import logger
from typing import Optional, Dict, Any, Union, List, TYPE_CHECKING

class AuthZeroClientObject(BaseModel):
    """
    The Auth Zero Client Object
    """
    
    client_id: str
    tenant: str
    name: str
    client_secret: str
    description: Optional[str] = None
    is_global: bool = Field(False, description = 'If True, the client is global', validation_alias = 'global')
    app_type: Optional[str] = None
    logo_uri: Optional[str] = None
    is_first_party: bool = Field(False, description = 'If True, the client is a first party client')
    oidc_conformant: bool = Field(False, description = 'If True, the client is an OIDC conformant client')
    callbacks: Optional[List[str]] = Field(default_factory = list, description = 'The callbacks')
    allowed_origins: Optional[List[str]] = Field(default_factory = list, description = 'The allowed origins')
    web_origins: Optional[List[str]] = Field(default_factory = list, description = 'The web origins')
    client_aliases: Optional[List[str]] = None
    allowed_clients: Optional[List[str]] = None
    allowed_logout_urls: Optional[List[str]] = Field(default_factory = list, description = 'The allowed logout urls')
    oidc_logout: Optional[Dict[str, Any]] = None
    grant_types: Optional[List[str]] = None
    jwt_configuration: Optional[Dict[str, Any]] = None
    signing_keys: Optional[List[Dict[str, Any]]] = None
    encryption_key: Optional[Dict[str, Any]] = None
    sso: Optional[bool] = None
    sso_disabled: Optional[bool] = None
    cross_origin_authentification: Optional[bool] = None
    cross_origin_loc: Optional[str] = None
    custom_login_page_on: Optional[bool] = None
    custom_login_page: Optional[str] = None
    cuustom_login_page_preview: Optional[str] = None
    form_template: Optional[str] = None
    addons: Optional[Dict[str, Any]] = None
    token_endpoint_auth_method: Optional[str] = None
    client_metadata: Optional[Dict[str, Any]] = None
    mobile: Optional[Dict[str, Any]] = None
    initiate_login_uri: Optional[str] = None
    native_social_login: Optional[Dict[str, Any]] = None
    refresh_token: Optional[Dict[str, Any]] = None
    organization_usage: Optional[str] = None
    organization_require_behavior: Optional[str] = None
    client_authentication_methods: Optional[Dict[str, Any]] = None
    require_pushed_authorization_requests: Optional[bool] = None
    access_token: Optional[Dict[str, Any]] = None
    signed_request_object: Optional[Dict[str, Any]] = None
    compliance_level: Optional[str] = None

    model_config = {'arbitrary_types_allowed': True, 'extra': 'allow'}

    # Extra Private Attributes
    _needs_update: Optional[bool] = PrivateAttr(False)

    def get_app_update_counts(self) -> Dict[str, int]:
        """
        Returns the update counts
        """
        return {
            'allowed_origins': len(self.allowed_origins),
            'callbacks': len(self.callbacks),
            'web_origins': len(self.web_origins),
            'allowed_logout_urls': len(self.allowed_logout_urls),
        }
    
    def get_app_patch_data(self) -> Dict[str, List[str]]:
        """
        Returns the patch data
        """
        return {
            'allowed_origins': self.allowed_origins,
            'callbacks': self.callbacks,
            'web_origins': self.web_origins,
            'allowed_logout_urls': self.allowed_logout_urls,
        }

    def add_app_url(
        self,
        allowed_origin: Optional[str] = None,
        callback: Optional[str] = None,
        web_origin: Optional[str] = None,
        allowed_logout_url: Optional[str] = None,
        verbose: Optional[bool] = None,
    ):
        """
        Adds to app urls
        """

        if allowed_origin is not None and allowed_origin not in self.allowed_origins:
            self.allowed_origins.append(allowed_origin)
            self._needs_update = True
            if verbose: logger.info(f'Added allowed origin: {allowed_origin}')
        if callback is not None and callback not in self.callbacks:
            self.callbacks.append(callback)
            self._needs_update = True
            if verbose: logger.info(f'Added callback: {callback}')
        if web_origin is not None and web_origin not in self.web_origins:
            self.web_origins.append(web_origin)
            self._needs_update = True
            if verbose: logger.info(f'Added web origin: {web_origin}')
        if allowed_logout_url is not None and allowed_logout_url not in self.allowed_logout_urls:
            self.allowed_logout_urls.append(allowed_logout_url)
            self._needs_update = True
            if verbose: logger.info(f'Added allowed logout url: {allowed_logout_url}')
    
