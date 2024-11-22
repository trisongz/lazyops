from __future__ import annotations

"""
Kinde OAuth2 Client
"""

from ..types.config import BaseOAuth2Config, eproperty
from ..types.client import BaseOAuth2Client
from typing import Any, Dict, Optional, Union, Tuple, TYPE_CHECKING, List, Type, Annotated
from pydantic import Field
from lzo.utils import create_unique_id

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


class KindeOAuth2Client(BaseOAuth2Client):
    """
    Kinde OAuth2 Client
    """
    name: Optional[str] = 'kinde'

    if TYPE_CHECKING:
        config: KindeOAuth2Config

    @eproperty
    def config_class(self) -> Type['KindeOAuth2Config']:
        """
        Returns the Config Class
        """
        return KindeOAuth2Config


    async def app_retrieve_existing_callbacks(
        self,
        **kwargs,
    ) -> Optional[List[str]]:
        """
        Retrieves the existing app callbacks
        """
        response = await self.m2m_client.async_get(
            f'/api/v1/applications/{self.config.client_id}/auth_redirect_urls',
            headers = {
                'Accept': 'application/json',
            }
        )
        response.raise_for_status()
        data: Dict[str, List[str]] = response.json()
        # logger.info(data)
        return data.get('redirect_urls', [])


    async def app_add_authorized_callbacks(
        self,
        callback_urls: List[str],
        **kwargs,
    ) -> None:
        """
        Adds the authorized callbacks
        """
        response = await self.m2m_client.async_post(
            f'/api/v1/applications/{self.config.client_id}/auth_redirect_urls',
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json; charset=utf-8',
            },
            json = {
                'urls': callback_urls,
            }
        )
        response.raise_for_status()
        data = response.json()
        data['urls'] = callback_urls
        self.logger.info(data, colored = True, prefix = f'{self.name} - Added {len(callback_urls)} Authorized Callbacks')
        
    
    async def app_retrieve_existing_logouts(
        self,
        **kwargs,
    ) -> Optional[List[str]]:
        """
        Retrieves the existing app logout urls
        """
        response = await self.m2m_client.async_get(
            f'/api/v1/applications/{self.config.client_id}/auth_logout_urls',
            headers = {
                'Accept': 'application/json',
            }
        )
        response.raise_for_status()
        data: Dict[str, List[str]] = response.json()
        return data.get('logout_urls', [])

    async def app_add_authorized_logouts(
        self,
        logout_urls: List[str],
        **kwargs,
    ) -> None:
        """
        Adds the authorized logouts
        """
        response = await self.m2m_client.async_post(
            f'/api/v1/applications/{self.config.client_id}/auth_logout_urls',
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json; charset=utf-8',
            },
            json = {
                'urls': logout_urls,
            }
        )
        response.raise_for_status()
        data = response.json()
        data['urls'] = logout_urls
        self.logger.info(data, colored = True, prefix = f'{self.name} - Added {len(logout_urls)} Authorized Logouts')
    

    async def afetch_user_info(
        self,
        token: str,
        token_payload: Dict[str, Any],
        **kwargs,
    ):
        """
        Fetches the user info
        """
        identity = token_payload.get('sub')
        if not identity: return
        response = await self.m2m_client.async_get(
            f'/api/v1/user?id={identity}',
            headers = {
                'Accept': 'application/json',
            }
        )
        response.raise_for_status()
        return response.json()

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
        # The token should generally already be an access token
        if token_payload.get('at_hash'):
            return {
                'id_token': {
                    'value': token,
                    **self.parse_jwt_token(token, kind = 'id_token')
                }
            }
        return {
            'access_token': {
                'value': token,
                **self.parse_jwt_token(token, kind = 'access_token')
            }
        }


        