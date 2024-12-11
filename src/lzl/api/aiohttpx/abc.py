from __future__ import annotations

"""
This Class Provides a Client that handles custom logic
that should be subclassed
"""

from abc import ABC
from .client import Client
from httpx._models import Response, Request
from typing import Optional

class ApiClient(ABC):

    _api: Optional[Client] = None

    def __init__(self, **kwargs):
        """
        Custom Initialization Logic
        """
        self.pre_init(**kwargs)
        self.post_init(**kwargs)

    def pre_init(self, **kwargs):
        """
        Custom Pre Initialization Logic
        """
        pass

    def post_init(self, **kwargs):
        """
        Custom Post Initialization Logic
        """
        pass

    def init_client(self, **kwargs):
        """
        Initializes the Client
        """
        self._api = Client(**kwargs)

    async def ainit_client(self, **kwargs):
        """
        Initializes the Client
        """
        self._api = Client(**kwargs)

    @property
    def api(self) -> Client:
        """
        Returns the API
        """
        if self._api is None:
            self.init_client()
        return self._api


    async def aget(self, *args, **kwargs) -> Response:
        """
        Async GET
        """
        return await self.api.async_get(*args, **kwargs)

    async def aput(self, *args, **kwargs) -> Response:
        """
        Async PUT
        """
        return await self.api.async_put(*args, **kwargs)
    
    async def apost(self, *args, **kwargs) -> Response:
        """
        Async POST
        """
        return await self.api.async_post(*args, **kwargs)
    
    async def adelete(self, *args, **kwargs) -> Response:
        """
        Async DELETE
        """
        return await self.api.async_delete(*args, **kwargs)
    
    async def apatch(self, *args, **kwargs) -> Response:
        """
        Async PATCH
        """
        return await self.api.async_patch(*args, **kwargs)
    
    async def arequest(self, *args, **kwargs) -> Response:
        """
        Async Request
        """
        return await self.api.async_request(*args, **kwargs)
    
    async def astream(self, *args, **kwargs) -> Response:
        """
        Async Stream
        """
        return await self.api.async_stream(*args, **kwargs)
    
    async def _abuild_request(self, *args, **kwargs) -> Request:
        """
        Async Build Request
        """
        return await self.api.async_build_request(*args, **kwargs)
    
    def get(self, *args, **kwargs) -> Response:
        """
        GET
        """
        return self.api.get(*args, **kwargs)
    
    def put(self, *args, **kwargs) -> Response:
        """
        PUT
        """
        return self.api.put(*args, **kwargs)
    
    def post(self, *args, **kwargs) -> Response:
        """
        POST
        """
        return self.api.post(*args, **kwargs)
    
    def delete(self, *args, **kwargs) -> Response:
        """
        DELETE
        """
        return self.api.delete(*args, **kwargs)
    
    def patch(self, *args, **kwargs) -> Response:
        """
        PATCH
        """
        return self.api.patch(*args, **kwargs)
    
    def request(self, *args, **kwargs) -> Response:
        """
        Request
        """
        return self.api.request(*args, **kwargs)
    
    def stream(self, *args, **kwargs) -> Response:
        """
        Stream
        """
        return self.api.stream(*args, **kwargs)
    
    def _build_request(self, *args, **kwargs) -> Request:
        """
        Build Request
        """
        return self.api.build_request(*args, **kwargs)
    

    

    


    


