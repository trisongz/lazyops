from __future__ import annotations

"""
Google OAuth2 Config
"""

from ...types.config import BaseOAuth2Config, eproperty
from typing import Any, Dict, Optional, Union, Tuple, TYPE_CHECKING, List, Type, Annotated
from pydantic import Field
from lzo.utils import create_unique_id
from .token import AccessToken, IDToken, OAuth2Token

_default_scopes = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
]

class GoogleOAuth2Config(BaseOAuth2Config):
    """
    Google OAuth2 Config
    """
    name: Optional[str] = 'google'
    issuer_url: Optional[str] = None
    jwt_issuer_url: Optional[str] = 'https://accounts.google.com'
    scopes: Optional[List[str]] = Field(default = _default_scopes)
    jwt_url: Optional[str] = 'https://www.googleapis.com/oauth2/v3/certs'

    authorize_disabled: Optional[bool] = True
    user_info_retrieve_disabled: Optional[bool] = True # Disable for now
    
    class Config(BaseOAuth2Config.Config):
        env_prefix = "GOOGLE_"


    @classmethod
    def get_default_token_cls(cls, name: str) -> Union[Type[AccessToken], Type[IDToken], Type[OAuth2Token]]:
        """
        Returns the default token class
        """
        if name == 'access_token':
            return AccessToken
        return IDToken if name == 'id_token' else OAuth2Token


    @eproperty
    def authorization_endpoint(self) -> str:
        """
        Returns the authorization endpoint
        """
        return 'https://accounts.google.com/o/oauth2/v2/auth'
    
    @eproperty
    def token_endpoint(self) -> str:
        """
        Returns the token endpoint
        """
        return 'https://oauth2.googleapis.com/token'
    
    @eproperty
    def token_info_endpoint(self) -> str:
        """
        Returns the token info endpoint
        """
        return 'https://oauth2.googleapis.com/tokeninfo'
    
    @eproperty
    def user_info_endpoint(self) -> str:
        """
        Returns the user info endpoint
        """
        return 'https://openidconnect.googleapis.com/v1/userinfo'

    def get_scopes(
        self,
        scopes: Optional[List[str]] = None,
        sep: Optional[str] = ' ',
    ) -> str:
        """
        Returns the scopes
        """
        if not scopes: return self.scope
        for n, scope in enumerate(scopes):
            if scope == 'openid': continue
            # This deals with `userinfo.email` and `userinfo.profile`
            if not scope.startswith('https://'):
                scopes[n] = f'https://www.googleapis.com/auth/{scope}'
        return sep.join(scopes)

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
            'redirect_uri': redirect_url,
            'client_id': self.client_id,
            'scope': scope,
            'access_type': 'offline',
            'prompt': 'consent',
            'response_type': 'code',
            'state': state,
            'include_granted_scopes': 'true',
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

