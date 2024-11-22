from __future__ import annotations

"""
Google OAuth2 Token
"""

from ...types.token import (
    AccessToken as BaseAccessToken,
    IDToken as BaseIDToken,
    OAuth2Token as BaseOAuth2Token,
    eproperty,
    Field,
    model_validator,
)

from typing import Optional, List, Dict, Any, Union, Type, TYPE_CHECKING


class AccessToken(BaseAccessToken):
    """
    Google Access Token
    """
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    provider: Optional[str] = 'google'


class IDToken(BaseIDToken):
    """
    Google ID Token
    """
    provider: Optional[str] = 'google'


class OAuth2Token(BaseOAuth2Token):
    """
    Google OAuth2 Token
    """
    access_token: Optional[Union[AccessToken, str]] = None
    id_token: Optional[Union[IDToken, str]] = None

    @eproperty
    def id_token_cls(self) -> Type[IDToken]:
        """
        Returns the ID Token Class
        """
        return IDToken
    
    @eproperty
    def access_token_cls(self) -> Type[AccessToken]:
        """
        Returns the Access Token Class
        """
        return AccessToken