from __future__ import annotations

from ..types.config import BaseOAuth2Config, eproperty
from ..types.client import BaseOAuth2Client, jwt
from typing import Any, Dict, Optional, Union, Tuple, TYPE_CHECKING, List, Type, Annotated
from pydantic import Field
from lzo.utils import create_unique_id

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
    
    class Config(BaseOAuth2Config.Config):
        env_prefix = "GOOGLE_"

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


class GoogleOAuth2Client(BaseOAuth2Client):
    """
    Google Auth Client
    """
    name: Optional[str] = 'google'

    if TYPE_CHECKING:
        config: GoogleOAuth2Config
        
    
    def parse_jwt_token(
        self,
        jwt_token: str,
        kind: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Parses the jwt token
        """
        # Posssible bug with the jwt?
        if kind == 'access_token': return None
        return jwt.decode(
            jwt_token,
            "",
            # signing_key.key, 
            algorithms=['RS256'],
            issuer = self.config.issuer_url,
            options = {
                'verify_signature': False,
                'verify_exp': True,
                'verify_aud': False,
            }
        )
        # return super().parse_jwt_token(jwt_token, kind = kind)

    
    def parse_authorization_token(
        self,
        authorization: str,
        audiences: Optional[List[str]] = None,
        verify_exp: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Parses the authorization token
        """
        # Posssible bug with the jwt?
        return jwt.decode(
            authorization, 
            "", 
            algorithms = ['RS256'],
            audience = audiences,
            issuer = self.config.jwt_issuer_url,
            options={
                'verify_signature': False,
                'verify_exp': verify_exp,
                'verify_aud': bool(audiences),
            }
        )
    
    @eproperty
    def config_class(self) -> Type['GoogleOAuth2Config']:
        """
        Returns the Config Class
        """
        return GoogleOAuth2Config
    

    async def afetch_user_info(
        self,
        token: str,
        token_payload: Dict[str, Any],
        **kwargs,
    ):
        """
        Fetches the user info
        """

    async def afetch_access_token_info(
        self,
        token: str,
        token_payload: Dict[str, Any],
        **kwargs,
    ):
        """
        Fetches the access token info
        """
        pass


    async def abuild_oauth_token(
        self,
        token: str,
        token_payload: Dict[str, Any],
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Builds the oauth token
        """
        # we'll try to determine the token type based on the prefix
        token_data = {}
        if token.startswith('ya29.'):
            token_data['access_token'] = {**(await self.afetch_access_token_info(token, token_payload)), 'value': token}
        else:
            token_data['id_token'] = {**self.parse_jwt_token(token, kind = 'id_token'), 'value': token}
        return token_data





        