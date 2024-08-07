from __future__ import annotations

"""
API Key Data Flows
"""
import time
from ..types.properties import StatefulProperty
from ..types.auth import APIKeyData
from .admin import AZManagementClient, logger
from ..utils.lazy import get_az_flow

from typing import List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types.claims import UserJWTClaims
    from ..types.user_data import AZUserData
    from ..flows.user_data import UserDataFlow

class APIKeyDataFlow(StatefulProperty[APIKeyData]):
    """
    API Key Data Flow
    """
    name: Optional[str] = "api_keys"
    schema_type = APIKeyData

    def __init__(
        self,
        user_id: str,
        **kwargs,
    ):
        cache_key = self.create_hash_key(user_id) if self.settings.session_user_id_hashed else user_id
        super().__init__(
            cache_key = cache_key,
            **kwargs,
        )
        self.user_id = user_id
        self.mtg = AZManagementClient
        self._user_data_flow: 'UserDataFlow' = None

    @property
    def user_data_flow(self) -> 'UserDataFlow':
        """
        Returns the User Data Flow
        """
        if self._user_data_flow is None:
            self._user_data_flow = get_az_flow('user_data', user_id = self.user_id)
        return self._user_data_flow

    def get_ttl(self, data: APIKeyData) -> Optional[int]:
        """
        Returns the TTL
        """
        return None
        # return data.user_data.expiration_ts - int(time.time())
        # ttl = data.user_data.expiration_ts - int(time.time())
        # self.settings.autologger.info(f'Checking if API Key Data is Expired: {self.user_id}: {ttl}')
        # return ttl
        # return 30
        # return None
    
    def is_expired(self, data: APIKeyData) -> bool:
        """
        Returns True if the Data is Expired
        """
        # return data.user_data.is_expired
        return False
    
    async def afetch(self) -> APIKeyData:
        """
        Fetches the API Key Data
        """
        data: Optional['APIKeyData'] = await self.pdict.aget(self.cache_key)
        if data is not None:
            if not self.is_valid_type(data):
                await self.adelete()
                data = None
            elif data.user_data.is_expired:
                logger.info(f'Refreshing User Data: {self.user_id}')
                data.user_data = await self.user_data_flow.afetch()
                await self.asave(data)
        # if data is not None and (not self.is_valid_type(data) or self.is_expired(data)):
        #     await self.adelete()
        #     # logger.warning(f'Expired API Key Data for {self.user_id}')
        #     # logger.warning(f'Invalid API Key Data for {self.user_id}: {(type(data))}')
        #     data = None
        return data
    

    async def aset(
        self,
        user_data: 'AZUserData',
        claims: 'UserJWTClaims',
    ) -> 'APIKeyData':
        """
        Saves the Data / Claims for the User ID
        """
        data = self.schema_type(
            user_data = user_data,
            claims = claims.to_api_key_claims() if hasattr(claims, 'to_api_key_claims') else claims,
        )
        await self.pdict.aset(self.cache_key, data) # , ex = self.get_ttl(data))
        # self.settings.logger.info(f'Saved API Key Data: {self.cache_key}', colored = True, prefix = self.user_id)
        return data



    if TYPE_CHECKING:
        def fetch(self) -> APIKeyData:
            """
            Fetches the API Key Data
            """
            ...

        async def afetch(self) -> APIKeyData:
            """
            Fetches the API Key Data
            """
            ...
        