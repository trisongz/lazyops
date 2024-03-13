from __future__ import annotations

"""
User Data Flows
"""
import time
from ..types.properties import StatefulProperty
from ..types.user_data import AZUserData
from .admin import AZManagementClient
from typing import List, Optional, Any, TYPE_CHECKING

class UserDataFlow(StatefulProperty[AZUserData]):
    """
    User Data Flow
    """
    name: Optional[str] = "user_data"
    schema_type = AZUserData

    cache_key_prefix: Optional[str] = None

    def __init__(
        self, 
        user_id: str,
        **kwargs,
    ):
        self.is_client_id: Optional[bool] = False
        if '@clients' in user_id: 
            user_id = user_id.split('@clients')[0]
            self.is_client_id = True
        cache_key = self.settings.create_cache_key(
            prefix = self.cache_key_prefix,
            suffix = user_id,
            include_client_id = True,
            # kind = 'user_data',
        )
        super().__init__(
            cache_key = cache_key,
            **kwargs,
        )
        self.user_id = user_id
        self.mtg = AZManagementClient

    def load(self) -> AZUserData:
        """
        Retrieves the User Data
        """
        if self.is_client_id:
            return AZUserData(user_id = self.user_id, user_metadata = {}, app_metadata = {})
        response = self.mtg.hget(f'users/{self.user_id}')
        result = self.mtg._process_response(response)
        return AZUserData(**result)

    async def aload(self) -> AZUserData:
        """
        Loads the User Data
        """
        if self.is_client_id:
            return AZUserData(user_id = self.user_id, user_metadata = {}, app_metadata = {})
        response = await self.mtg.ahget(f'users/{self.user_id}')
        result = self.mtg._process_response(response)
        return AZUserData(**result)
    
    def get_ttl(self, data: AZUserData) -> int:
        """
        Returns the TTL
        """
        return None if self.is_client_id else self.settings.user_data_expiration or 60
        # return data.expiration_ts - int(time.time())

    def is_expired(self, data: AZUserData) -> bool:
        """
        Returns True if the Data is Expired
        """
        # self.settings.autologger.info(f'Checking if User Data is Expired: {self.user_id}: {data.is_expired}')
        return False if self.is_client_id else data.is_expired
    
    @property
    def user_data(self) -> AZUserData:
        """
        Returns the User Data
        """
        return self.resource
    
    @property
    async def auser_data(self) -> AZUserData:
        """
        Returns the User Data
        """
        return await self.aresource

    if TYPE_CHECKING:
        
        @classmethod
        def get(cls, user_id: str) -> AZUserData:
            """
            Get the User Data
            """
            ...
        
        @classmethod
        async def aget(cls, user_id: str) -> AZUserData:
            """
            Get the User Data
            """
            ...

        def fetch(self) -> AZUserData:
            """
            Fetches the User Data
            """
            ...

        async def afetch(self) -> AZUserData:
            """
            Fetches the User Data
            """
            ...

        @property
        def resource(self) -> AZUserData:
            """
            Returns the Object
            """
            ...

        @property
        async def aresource(self) -> AZUserData:
            """
            Returns the Object Resource
            """
            ...

