from __future__ import annotations

"""
Kinde OAuth2 Config
"""

from ...types.config import BaseOAuth2Config, eproperty
from typing import Any, Dict, Optional, Union, Tuple, TYPE_CHECKING, List, Type, Annotated
from pydantic import Field
from lzo.utils import create_unique_id
from .token import AccessToken, IDToken, OAuth2Token

_default_scopes = [
    'openid',
    'profile',
    'email',
    'offline',
]

class KindeOAuth2Config(BaseOAuth2Config):
    """
    Kinde Auth Settings
    """
    name: Optional[str] = 'kinde'
    scopes: Optional[List[str]] = Field(default = _default_scopes)

    class Config(BaseOAuth2Config.Config):
        env_prefix = "KINDE_"

    @eproperty
    def m2m_audience(self) -> str:
        """
        Returns the m2m audience
        """
        return f'{self.issuer_url}/api'
    

    @classmethod
    def get_default_token_cls(cls, name: str) -> Union[Type[AccessToken], Type[IDToken], Type[OAuth2Token]]:
        """
        Returns the default token class
        """
        if name == 'access_token':
            return AccessToken
        return IDToken if name == 'id_token' else OAuth2Token


    def get_auth_params(
        self,
        redirect_url: str,
        scope: Optional[str] = None,
        state: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the auth params
        """
        scope = scope or self.get_scopes()
        state = state or create_unique_id(alph_only=True)
        return {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': redirect_url,
            'scope': scope,
            'state': state,
            'code_challenge': self.create_code_challenge(self.code_verifier),
            'code_challenge_method': self.code_challenge_method,
        }
    
    def get_fetch_token_params(
        self,
        code: str,
        redirect_url: str,
        state: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the fetch token params
        """
        return {
            'code': code,
            'code_verifier': self.code_verifier,
            'state': state,
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

    def get_headers(
        self,
        endpoint_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns the headers
        """
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        }
        if endpoint_type == 'token':
            headers['Authorization'] = f'Basic {self.encode_client_secret_basic(self.client_id, self.client_secret)}'
        return headers

