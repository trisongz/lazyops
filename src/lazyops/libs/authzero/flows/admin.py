from __future__ import annotations

"""
Admin / Management API
"""

import inspect
from abc import ABC
from urllib.parse import urljoin
from fastapi import HTTPException
from lazyops.libs import lazyload
from lazyops.libs.proxyobj import ProxyObject
from lazyops.utils.helpers import timed_cache

from ..types.errors import InvalidOperationException
from ..types.auth import AuthZeroTokenAuth
from ..types.clients import AuthZeroClientObject
from ..utils.lazy import get_az_settings, logger
from .tokens import ClientCredentialsFlow

from typing import Optional, List, Dict, Any, Union

if lazyload.TYPE_CHECKING:
    import niquests
    from niquests import Session, AsyncSession, Response, AsyncResponse
else:
    niquests = lazyload.LazyLoad("niquests")


class AZManagementAPI(ABC):
    
    """
    The Auth Zero Management API
    """

    if lazyload.TYPE_CHECKING:
        user_id: Optional[str] = None

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        oauth_url: Optional[str] = None,
        audience: Optional[str] = None,
        management_api_url: Optional[str] = None,
        use_http_session: Optional[bool] = False,
        **kwargs,
    ):
        """
        Initializes the Auth Zero Management API
        """
        self.settings = get_az_settings()
        self.management_api_url = management_api_url or self.settings.management_api_url
        self.token_flow = ClientCredentialsFlow(
            audience = audience or self.management_api_url,
            client_id = client_id,
            client_secret = client_secret,
            oauth_url = oauth_url,
            **kwargs,
        )

        self.auth = AuthZeroTokenAuth(token_flow=self.token_flow)
        self.use_http_session = use_http_session
        self._session: Optional['Session'] = None
        self._asession: Optional['AsyncSession'] = None

    def get_url(self, path: str) -> str:
        """
        Returns the URL
        """
        # if path.startswith('http'): return path
        return urljoin(self.management_api_url, path)
    
    def hget(self, path: str, **kwargs) -> 'Response':
        """
        Returns the Response
        """
        if not self.use_http_session:
            return niquests.get(self.get_url(path), auth = self.auth, **kwargs)
        return self.session.get(self.get_url(path), auth = self.auth, **kwargs)
    
    async def ahget(self, path: str, **kwargs) -> 'AsyncResponse':
        """
        Returns the Response
        """
        if self.use_http_session:
            return await self.asession.get(self.get_url(path), auth = self.auth, **kwargs)
        async with niquests.AsyncSession() as s:
            return await s.get(self.get_url(path), auth = self.auth, **kwargs)
    
    
    def hpost(self, path: str, **kwargs) -> 'Response':
        """
        Returns the Response
        """
        if not self.use_http_session:
            return niquests.post(self.get_url(path), auth = self.auth, **kwargs)
        return self.session.post(self.get_url(path), auth = self.auth, **kwargs)
    
    async def ahpost(self, path: str, **kwargs) -> 'AsyncResponse':
        """
        Returns the Response
        """
        if self.use_http_session:
            return await self.asession.post(self.get_url(path), auth = self.auth, **kwargs)
        async with niquests.AsyncSession() as s:
            return await s.post(self.get_url(path), auth = self.auth, **kwargs)

    def hput(self, path: str, **kwargs) -> 'Response':
        """
        Returns the Response
        """
        if not self.use_http_session:
            return niquests.put(self.get_url(path), auth = self.auth, **kwargs)
        return self.session.put(self.get_url(path), auth = self.auth, **kwargs)
    
    async def ahput(self, path: str, **kwargs) -> 'AsyncResponse':
        """
        Returns the Response
        """
        if self.use_http_session:
            return await self.asession.put(self.get_url(path), auth = self.auth, **kwargs)
        async with niquests.AsyncSession() as s:
            return await s.put(self.get_url(path), auth = self.auth, **kwargs)
        
    
    def hpatch(self, path: str, **kwargs) -> 'Response':
        """
        Returns the Response
        """
        if not self.use_http_session:
            return niquests.patch(self.get_url(path), auth = self.auth, **kwargs)
        return self.session.patch(self.get_url(path), auth = self.auth, **kwargs)
    
    async def ahpatch(self, path: str, **kwargs) -> 'AsyncResponse':
        """
        Returns the Response
        """
        if self.use_http_session:
            return await self.asession.patch(self.get_url(path), auth = self.auth, **kwargs)
        async with niquests.AsyncSession() as s:
            return await s.patch(self.get_url(path), auth = self.auth, **kwargs)

    def _validate_response(self, response: Union['Response', 'AsyncResponse']):
        """
        Validates the Response
        """
        try:
            response.raise_for_status()
        except niquests.HTTPError as e:
            if e.response.status_code in {400, 404}:
                raise HTTPException(status_code = e.response.status_code, detail = e.response.text) from e
            operation_name = f'{self.__class__.__name__}.{inspect.stack()[1].function}'
            msg = f'[{response.status_code}] Error doing `{operation_name}`'
            if hasattr(self, 'user_id'):
                msg += f' on user {self.user_id}'
            msg += f': {e.response.text}'
            logger.error(msg)
            raise InvalidOperationException(detail = msg) from e


    def _process_response(self, response: 'Response') -> Optional[Union[List, Dict]]:
        # sourcery skip: extract-method
        """
        Processes the Response
        """
        self._validate_response(response)
        if response.content: return response.json()
    
    def _404_to_empty_list(self, response: Union['Response', 'AsyncResponse']) -> Optional[List]:
        """
        Handles the Response
        """
        try:
            return self._process_response(response)
        except HTTPException as e:
            if e.status_code == 404: return []
            raise e


    @property
    def session(self) -> 'Session':
        """
        Returns the Session
        """
        if self._session is None:
            self._session = niquests.Session(
                pool_connections = 10,
                pool_maxsize = 10,
                retries = 5,
            )
        return self._session
    
    @property
    def asession(self) -> 'AsyncSession':
        """
        Returns the Async Session
        """
        if self._asession is None:
            self._asession = niquests.AsyncSession(
                pool_connections = 10,
                pool_maxsize = 10,
                retries = 5,
            )
        return self._asession
    

    """
    API Methods
    """

    def get_az_client(
        self,
        client_id: str,
        **kwargs
    ) -> Optional['AuthZeroClientObject']:
        """
        Returns the AuthZero Client
        """
        response = self.hget(f'clients/{client_id}')
        if response.status_code == 200:
            return AuthZeroClientObject.model_validate(response.json())
        logger.warning(f'[{response.status_code}] Error getting client: `{client_id}` {response.text}')
        return None
    

    async def aget_az_client(
        self,
        client_id: str,
        **kwargs
    ) -> Optional['AuthZeroClientObject']:
        """
        Returns the AuthZero Client
        """
        response = await self.ahget(f'clients/{client_id}')
        if response.status_code == 200:
            return AuthZeroClientObject.model_validate(response.json())
        logger.warning(f'[{response.status_code}] Error getting client: `{client_id}` {response.text}')
        return None
    
    @timed_cache(600)
    def get_service_client_name(
        self,
        client_id: str,
    ) -> Optional[str]:
        """
        Returns the Service Client Name
        """
        client = self.get_az_client(client_id = client_id)
        return None if client is None else client.name

    @timed_cache(600)
    async def aget_service_client_name(
        self,
        client_id: str,
    ) -> Optional[str]:
        """
        Returns the Service Client Name
        """
        client = await self.aget_az_client(client_id = client_id)
        return None if client is None else client.name



AZManagementClient: AZManagementAPI = ProxyObject(
    AZManagementAPI,
    obj_kwargs = {'use_http_session': False},
)