from __future__ import annotations

"""
User Session Flows
"""
import time
from ..types.properties import StatefulProperty
from ..types.user_session import UserSession
from .admin import AZManagementClient
from typing import List, Optional, Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request


class UserSessionFlow(StatefulProperty[UserSession]):
    """
    User Session Flow
    """

    name: Optional[str] = "user_session"
    schema_type = UserSession

    def __init__(
        self, 
        session_key: str
    ):
        super().__init__(cache_key = session_key)


    def fetch(self) -> 'UserSession':
        """
        Returns the Value
        """
        data = self.pdict.get(self.cache_key)
        if data is None or not self.is_valid_type(data) or self.is_expired(data):
            self.delete()
            data = None
        return data
    
    async def afetch(self) -> 'UserSession':
        """
        Returns the Value
        """
        data = await self.pdict.aget(self.cache_key)
        if data is None or not self.is_valid_type(data) or self.is_expired(data):
            await self.adelete()
            data = None
        return data
    

    def is_expired(self, data: UserSession) -> bool:
        """
        Returns True if the Data is Expired
        """
        return data.is_expired

    def get_ttl(self, data: UserSession) -> int:
        """
        Returns the TTL
        """
        return max(data.expiration_ts - int(time.time()), 0)
    
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
    

    @classmethod
    def get(
        cls, 
        request: 'Request',
        *args, 
        **kwargs
    ) -> Optional[UserSession]:
        """
        Get the value
        """
        return cls(*args, **kwargs).fetch()
    
    @classmethod
    async def aget(
        cls, 
        request: 'Request',
        *args, 
        **kwargs
    ) -> Optional[UserSession]:
        """
        Get the value
        """
        return await cls(*args, **kwargs).aget()

    if TYPE_CHECKING:

        @property
        def _obj_(self) -> UserSession:
            """
            Returns the Object
            """
            ...
