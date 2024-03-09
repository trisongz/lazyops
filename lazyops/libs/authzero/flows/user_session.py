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
    from ..types.current_user import CurrentUser

class UserSessionFlow(StatefulProperty[UserSession]):
    """
    User Session Flow
    """

    name: Optional[str] = "user_session"
    schema_type = UserSession

    def __init__(
        self, 
        user_id: str,
    ):
        cache_key = self.create_hash_key(user_id) if self.settings.session_user_id_hashed else user_id
        super().__init__(cache_key = cache_key)
        self.user_id = user_id

    @property
    def session(self) -> UserSession:
        """
        Returns the Session
        """
        return self.resource
    
    @property
    async def asession(self) -> UserSession:
        """
        Returns the Session
        """
        return await self.aresource
    
    @property
    def session_data(self) -> Dict[str, Any]:
        """
        Returns the Session User Data
        """
        return self.load_data()
    
    @property
    async def asession_data(self) -> Dict[str, Any]:
        """
        Returns the User Data
        """
        return await self.aload_data()

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
        return data.ttl
    
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
        user: 'CurrentUser',
        request: 'Request',
        **kwargs
    ) -> Optional[UserSession]:
        """
        Get the value
        """
        if user.settings.session_cookie_key not in request.cookies:
            return None
        session_key = request.cookies[user.settings.session_cookie_key]
        return cls(session_key).fetch()
    
    @classmethod
    async def aget(
        cls, 
        user: 'CurrentUser',
        request: 'Request',
        **kwargs
    ) -> Optional[UserSession]:
        """
        Get the value
        """
        if user.settings.session_cookie_key not in request.cookies:
            return None
        session_key = request.cookies[user.settings.session_cookie_key]
        return await cls(session_key).aget()

    if TYPE_CHECKING:

        @property
        def resource(self) -> UserSession:
            """
            Returns the Object
            """
            ...

        @property
        async def aresource(self) -> UserSession:
            """
            Returns the Object Resource
            """
            ...
        