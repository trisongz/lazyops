from __future__ import annotations

"""
The Base Config for the Oauth2 Provider
"""

import base64
import hashlib
from lzl.logging import logger
from lzl.types import BaseSettings, eproperty
from pydantic import PrivateAttr, model_validator, field_validator, Field
from urllib.parse import urlparse, urlunparse, urljoin, parse_qsl, urlencode, quote
from typing import Any, Dict, Optional, Union, Tuple, TYPE_CHECKING, List, Type, Annotated, Generator


class BaseOAuth2Config(BaseSettings):
    """
    The Base Config for the Oauth2 Provider
    """

    name: Optional[str] = None
    issuer_url: Optional[str] = None
    jwt_url: Optional[str] = '/.well-known/jwks.json'
    jwt_issuer_url: Optional[str] = None

    client_id: Optional[str] = None
    client_secret: Optional[str] = None

    m2m_client_id: Optional[str] = None
    m2m_client_secret: Optional[str] = None

    code_verifier: Optional[str] = None
    code_challenge_method: Optional[str] = 'S256'
    scopes: Optional[List[str]] = None

    cache_base_key: Optional[str] = None
    cache_expiration: Optional[int] = 60 * 60 * 24 * 7 * 4 * 3 # 3 months
    authorize_disabled: Optional[bool] = None
    domains: Optional[List[str]] = None


    @eproperty
    def m2m_enabled(self) -> bool:
        """
        Returns whether m2m is enabled
        """
        return bool(self.m2m_client_id and self.m2m_client_secret)
    
    @eproperty
    def m2m_audience(self) -> str:
        """
        Returns the m2m audience
        """
        return self.issuer_url

    @eproperty
    def scope(self) -> Optional[str]:
        """
        Returns the scope
        """
        return ' '.join(self.scopes) if self.scopes else None

    @eproperty
    def authorization_endpoint(self) -> str:
        """
        Returns the authorization endpoint
        """
        return urljoin(self.issuer_url, '/oauth2/auth')
    

    @eproperty
    def token_endpoint(self) -> str:
        """
        Returns the token endpoint
        """
        return urljoin(self.issuer_url, '/oauth2/token')
    

    @eproperty
    def logout_endpoint(self) -> str:
        """
        Returns the logout endpoint
        """
        return urljoin(self.issuer_url, '/logout')


    @model_validator(mode = 'after')
    def validate_provider_config(self):
        """
        Validates the provider config
        """
        if self.jwt_url and 'https://' not in self.jwt_url:
            self.jwt_url = urljoin(self.issuer_url, self.jwt_url)
        if not self.jwt_issuer_url and self.issuer_url:
            self.jwt_issuer_url = self.issuer_url
        return self


    def get_scopes(
        self,
        scopes: Optional[List[str]] = None,
        sep: Optional[str] = ' ',
    ) -> str:
        """
        Returns the scopes
        """
        return sep.join(scopes) if scopes else self.scope


    @staticmethod
    def create_code_challenge(secret_key: str) -> str:
        """
        Creates a code challenge
        """
        return base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode()).digest()).decode().rstrip('=')

    @staticmethod
    def to_native(x: Union[str, bytes], encoding='ascii'):
        return x if isinstance(x, str) else x.decode(encoding)
    
    @staticmethod
    def to_bytes(x: Union[str, bytes, int, float], charset='utf-8', errors='strict'):
        if x is None: return None
        if isinstance(x, bytes): return x
        if isinstance(x, str): return x.encode(charset, errors)
        if isinstance(x, (int, float)): return str(x).encode(charset, errors)
        return bytes(x)

    @classmethod
    def encode_client_secret_basic(cls, client_id: str, client_secret: str) -> str:
        """
        Encodes the client secret basic
        """
        text = f'{quote(client_id)}:{quote(client_secret)}'
        return cls.to_native(base64.b64encode(cls.to_bytes(text, 'latin1')))


    def get_headers(
        self,
        endpoint_type: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the headers
        """
        return {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        }
    

    def get_auth_params(
        self,
        redirect_url: str,
        scope: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the auth params
        """
        scope = scope or self.get_scopes(self.scopes)
        return {
            'redirect_uri': redirect_url,
            'client_id': self.client_id,
            'scope': scope,
            'access_type': 'offline',
            'prompt': 'consent',
            'response_type': 'code',
            **kwargs,
        }
    
    def get_fetch_token_params(
        self,
        code: str,
        redirect_url: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the fetch token params
        """
        return {
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': redirect_url,
            'grant_type': 'authorization_code',
        }
    
    def get_refresh_token_params(
        self,
        refresh_token: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the refresh token params
        """
        return {
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
        }
    


    def get_m2m_token_params(
        self,
        audience: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the m2m token params
        """
        audience = audience or self.m2m_audience
        return {
            'grant_type': 'client_credentials',
            'client_id': self.m2m_client_id,
            'client_secret': self.m2m_client_secret,
            'audience': audience,
        }
    