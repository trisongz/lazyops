from __future__ import annotations

"""
Kinde OAuth2 Token
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
    Kinde Access Token
    """
    external_org_id: Optional[str] = None
    org_code: Optional[str] = None
    org_name: Optional[str] = None
    permissions: Optional[List[str]] = Field(default_factory=list)
    roles: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    scp: Optional[List[str]] = Field(default_factory=list)
    provider: Optional[str] = 'kinde'
    feature_flags: Optional[Dict[str, Dict[str, Union[str, bool, dict]]]] = Field(default = None)
    organization_properties: Optional[Dict[str, Any]] = Field(default = None)
    user_properties: Optional[Dict[str, Any]] = Field(default = None)


class IDToken(BaseIDToken):
    """
    Kinde ID Token
    """
    auth_time: Optional[int] = None
    org_codes: Optional[List[str]] = Field(default_factory=list)
    organizations: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    rat: Optional[int] = None
    updated_at: Optional[int] = None
    provider: Optional[str] = 'kinde'


class OAuth2Token(BaseOAuth2Token):
    """
    Kinde OAuth2 Token
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