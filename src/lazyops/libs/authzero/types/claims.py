
"""
JWT Claims
"""
import time
from pydantic import BaseModel, Field
from typing import Optional, Union, List, Dict


class BaseClaims(BaseModel):
    """
    Base JWT Claims
    """
    aud: Union[str, List[str]]  # API identifier, e.g. "https://app-backend.gex"
    azp: str  # Client app's client_id
    iss: str  # Issuer of the token, always "https://domain.us.auth0.com/"
    scope: str = ''  # scopes requested separated with space, e.g. "models"
    sub: str  # User ID string, e.g. "google-oauth2|..." or "auth0|...."
    cust_user_id_perf_test: Optional[str] = None
    user_roles: Optional[List[str]] = Field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        """
        Returns True if the Token is Expired
        """
        return False
    
    @property
    def scopes(self) -> List[str]:
        """
        Returns the Scopes
        """
        return self.scope.split(' ')


class APIKeyJWTClaims(BaseClaims):
    """
    API Key JWT Claims
    """

    model_config = {'extra': 'ignore', 'arbitrary_types_allowed': True}


class UserJWTClaims(BaseClaims):
    """
    User JWT Claims
    """
    exp: int  # "expires at" time
    iat: int  # "issued at" time
    
    @property
    def is_expired(self) -> bool:
        """
        Returns True if the Token is Expired
        """
        return self.exp < (int(time.time()) - 45)

    def to_api_key_claims(self) -> 'APIKeyJWTClaims':
        """
        Converts the User JWT Claims to an API Key JWT Claims
        """
        return APIKeyJWTClaims.model_validate(self, from_attributes=True)
