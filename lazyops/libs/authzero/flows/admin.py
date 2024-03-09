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

from ..types.errors import InvalidOperationException
from ..types.auth import AuthZeroTokenAuth
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
    
    def hget(self, path: str, **kwargs) -> 'Response':
        """
        Returns the Response
        """
        if not self.use_http_session:
            return niquests.get(urljoin(self.management_api_url, path), auth = self.auth, **kwargs)
        return self.session.get(urljoin(self.management_api_url, path), **kwargs)
    
    async def ahget(self, path: str, **kwargs) -> 'AsyncResponse':
        """
        Returns the Response
        """
        if self.use_http_session:
            return await self.asession.get(urljoin(self.management_api_url, path), **kwargs)
        async with niquests.AsyncSession(auth = self.auth) as s:
            return await s.get(urljoin(self.management_api_url, path), **kwargs)
    
    
    def hpost(self, path: str, **kwargs) -> 'Response':
        """
        Returns the Response
        """
        if not self.use_http_session:
            return niquests.post(urljoin(self.management_api_url, path), auth = self.auth, **kwargs)
        return self.session.post(urljoin(self.management_api_url, path), **kwargs)
    
    async def ahpost(self, path: str, **kwargs) -> 'AsyncResponse':
        """
        Returns the Response
        """
        if self.use_http_session:
            return await self.asession.post(urljoin(self.management_api_url, path), **kwargs)
        async with niquests.AsyncSession(auth = self.auth) as s:
            return await s.post(urljoin(self.management_api_url, path), **kwargs)

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
        # try:
        #     response.raise_for_status()
        # except niquests.HTTPError as e:
        #     if e.response.status_code in {400, 404}:
        #         raise HTTPException(status_code = e.response.status_code, detail = e.response.text) from e
        #     operation_name = f'{self.__class__.__name__}.{inspect.stack()[1].function}'
        #     msg = f'[{response.status_code}] Error doing `{operation_name}`'
        #     if hasattr(self, 'user_id'):
        #         msg += f' on user {self.user_id}'
        #     msg += f': {e.response.text}'
        #     logger.error(msg)
        #     raise InvalidOperationException(detail = msg) from e
        self._validate_response(response)
        if response.content: return response.json()
    
    async def _aprocess_response(self, response: 'AsyncResponse') -> Optional[Union[List, Dict]]:
        # sourcery skip: extract-method
        """
        Processes the Response
        """
        # try:
        #     response.raise_for_status()
        # except niquests.HTTPError as e:
        #     if e.response.status_code in {400, 404}:
        #         raise HTTPException(status_code = e.response.status_code, detail = await e.response.text) from e
        #     operation_name = f'{self.__class__.__name__}.{inspect.stack()[1].function}'
        #     msg = f'[{response.status_code}] Error doing `{operation_name}`'
        #     if hasattr(self, 'user_id'):
        #         msg += f' on user {self.user_id}'
        #     msg += f': {await e.response.text}'
        #     logger.error(msg)
        #     raise InvalidOperationException(detail = msg) from e
        self._validate_response(response)
        if await response.content: return await response.json()
    
    def _404_to_empty_list(self, response: Union['Response', 'AsyncResponse']) -> Optional[List]:
        """
        Handles the Response
        """
        try:
            return self._aprocess_response(response) if hasattr(response, 'raw') else \
                self._process_response(response)
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
                auth = AuthZeroTokenAuth(token_flow=self.token_flow),
                pool_connections = 5,
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
                auth = AuthZeroTokenAuth(token_flow=self.token_flow),
                pool_connections = 5,
                pool_maxsize = 10,
                retries = 5,
            )
        return self._asession
        

AZManagementClient: AZManagementAPI = ProxyObject(
    AZManagementAPI,
    obj_kwargs = {'use_http_session': True},
)