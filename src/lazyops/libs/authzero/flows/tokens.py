from __future__ import annotations

"""
Client Tokens and App Token Flows
"""

from lazyops.libs import lazyload
from lazyops.libs.abcs.configs.types import AppEnv
from ..types.properties import StatefulProperty
from ..types.tokens import AccessToken
from ..utils.lazy import get_az_settings, logger
from ..utils.helpers import normalize_audience_name
from typing import List, Optional, Any, Dict, Union, TYPE_CHECKING

if lazyload.TYPE_CHECKING:
    import niquests
else:
    niquests = lazyload.LazyLoad("niquests")

class BaseTokenFlow(StatefulProperty[AccessToken]):
    """
    Base Token Flow
    """
    name: Optional[str] = None
    schema_type = AccessToken
    
    def __init__(
        self, 
        audience: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        oauth_url: Optional[str] = None,
        **kwargs,
    ):
        """
        Initializes the Token Flow
        """
        cache_key = kwargs.pop('cache_key', None)
        cache_key = cache_key or self.settings.create_cache_key(audience)
        super().__init__(
            cache_key = cache_key,
            **kwargs,
        )
        self.audience = audience
        self.client_id = client_id or self.settings.client_id
        self.client_secret = client_secret or self.settings.client_secret
        self.oauth_url = oauth_url or self.settings.oauth_url

    
    @property
    def access_token(self) -> AccessToken:
        """
        Returns the Access Token
        """
        return self.resource
    
    @property
    def token(self) -> str:
        """
        Returns the Access Token
        """
        return self.resource.access_token
    
    @property
    async def atoken(self) -> str:
        """
        Returns the Access Token
        """
        return (await self.aresource).access_token
    
    @property
    def auth_headers(self) -> Dict[str, str]:
        """
        Returns the Auth Headers
        """
        return {'Authorization': f'Bearer {self.token}'}
    
    @property
    async def aauth_headers(self) -> Dict[str, str]:
        """
        Returns the Auth Headers
        """
        return {'Authorization': f'Bearer {await self.atoken}'}
    
    
    def load(self) -> AccessToken:
        """
        Retrieves the Access Token from the API
        """
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'audience': self.audience,
            'grant_type': 'client_credentials',
        }
        # logger.info(f'Retrieving Access Token from {self.oauth_url}')
        response = niquests.post(self.oauth_url, data = data)
        response.raise_for_status()
        return AccessToken(**response.json())
    
    async def aload(self) -> AccessToken:
        """
        Retrieves the Access Token from the API
        """
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'audience': self.audience,
            'grant_type': 'client_credentials',
        }
        # logger.info(f'Retrieving Access Token from {self.oauth_url}')
        async with niquests.AsyncSession() as s:
            response = await s.post(self.oauth_url, data = data)
            response.raise_for_status()
            return AccessToken(**response.json())


    def get_ttl(self, data: AccessToken) -> int:
        """
        Returns the TTL
        """
        return data.expires_in - 60
    

    def is_expired(self, data: AccessToken) -> bool:
        """
        Returns True if the Data is Expired
        """
        return data.is_expired


    if TYPE_CHECKING:
        def fetch(self) -> AccessToken:
            """
            Fetches the Access Token
            """
            ...

        async def afetch(self) -> AccessToken:
            """
            Fetches the Access Token
            """
            ...
        

        @classmethod
        def get(
            cls,
            audience: str,
            client_id: Optional[str] = None,
            client_secret: Optional[str] = None,
            oauth_url: Optional[str] = None,
            **kwargs,
        ) -> AccessToken:
            """
            Get the Access Token
            """
            ...
        

        @classmethod
        async def aget(
            cls,
            audience: str,
            client_id: Optional[str] = None,
            client_secret: Optional[str] = None,
            oauth_url: Optional[str] = None,
            **kwargs,
        ) -> AccessToken:
            """
            Get the Access Token
            """
            ...

        @property
        def resource(self) -> AccessToken:
            """
            Returns the Object
            """
            ...

        @property
        async def aresource(self) -> AccessToken:
            """
            Returns the Object Resource
            """
            ...



class ClientCredentialsFlow(BaseTokenFlow):
    """
    Can be used to get a token for any API using Client Credentials flow.
    Specify the API with the `audience` param.
    """
    name: Optional[str] = "client_token"
    schema_type = AccessToken



class APIClientCredentialsFlow(BaseTokenFlow):
    """
    Can be used to get a token for any API using Client Credentials flow.
    Specify the API with the `audience` param.
    """
    name: Optional[str] = "api_token"
    schema_type = AccessToken

    def __init__(
        self, 
        endpoint: str, 
        api_client_id: Optional[str] = None, 
        api_client_env: Optional[Union[str, AppEnv]] = None, 
        audience: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        oauth_url: Optional[str] = None,
        **kwargs,
    ):
        """
        Initializes the API Client Credentials for the Audience
        """
        # key = endpoint.split('://', 1)[-1].replace('/', '_')
        key = normalize_audience_name(endpoint)
        if api_client_id: key += f'.{api_client_id}'
        if api_client_env: 
            if isinstance(api_client_env, AppEnv): api_client_env = api_client_env.name
            key += f'.{api_client_env}'
        if audience: key += f'.{normalize_audience_name(audience)}'
        super().__init__(
            audience = audience or self.settings.management_api_url,
            client_id = client_id or self.settings.client_id,
            client_secret = client_secret or self.settings.client_secret,
            oauth_url = oauth_url or self.settings.oauth_url,
            cache_key = key,
            **kwargs,
        )
        self.endpoint = endpoint

    """
    Might need to rework these later
    """

    def load_data(self) -> Dict[str, Any]:
        """
        Loads the Client Data
        """
        return self.pdict.get(self.data_cache_key, {})

    async def aload_data(self) -> Dict[str, Any]:
        """
        Loads the Client Data
        """
        return await self.pdict.aget(self.data_cache_key, {})
    
    def save_data(self, data: Dict[str, Any], ex: Optional[int] = None):
        """
        Saves the Data
        """
        self.pdict.set(self.data_cache_key, data, ex = ex)

    async def asave_data(self, data: Dict[str, Any], ex: Optional[int] = None):
        """
        Saves the Data
        """
        await self.pdict.aset(self.data_cache_key, data, ex = ex)
    
