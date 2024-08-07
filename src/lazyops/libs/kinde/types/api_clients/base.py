from __future__ import annotations

"""
Kinde API Clients
"""

import abc
import jwt
from jwt import PyJWKClient
from urllib.parse import urljoin
from lazyops.libs import lazyload
from typing import Optional, List, Dict, Any, Union, Type, Tuple, Callable, overload, TYPE_CHECKING

if lazyload.TYPE_CHECKING:
    import niquests
    from niquests import Session, AsyncSession, Response, AsyncResponse
    from niquests.models import Headers, Request as HTTPRequest
    from lazyops.libs.kinde.v2.config import KindeSettings
else:
    niquests = lazyload.LazyLoad("niquests")


class BaseAPIRoute(abc.ABC):
    """
    The Base API Route
    """
    def __init__(
        self,
        client: 'BaseAPIClient',
        **kwargs,
    ):
        """
        Initializes the API Route
        """
        self.c = client
    

class BaseClientAuth(abc.ABC):
    """
    The Base Client Auth
    """
    def __init__(
        self,
        headers: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initializes the Client Auth
        """
        self.headers = headers or {}
        self.post_init(**kwargs)
    
    def post_init(self, **kwargs):
        """
        Post Initialization
        """
        pass

    def inject_auth(self, r: 'HTTPRequest') -> 'HTTPRequest':
        """
        Injects the auth
        """
        return r

    def __call__(self, r: 'HTTPRequest') -> 'HTTPRequest':
        """
        Implements the HTTP Credential Injection
        """
        r = self.inject_auth(r)
        if self.headers: 
            for key, value in self.headers.items():
                if key not in r.headers: r.headers[key] = value
        return r
    



class BaseAPIClient(abc.ABC):
    """
    The Base API Client
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        settings: Optional['KindeSettings'] = None,
        session_disabled: Optional[bool] = None,
        **kwargs,
    ):
        """
        Initializes the API Client
        """
        self.base_url = base_url
        if settings is None:
            from lazyops.libs.kinde.v2.utils import get_kinde_settings
            settings = get_kinde_settings()
        self.settings = settings
        self._session_disabled = session_disabled
        self._session: Optional['Session'] = None
        self._asession: Optional['AsyncSession'] = None
        self._session_kwargs: Dict[str, Any] = {}
        self._extra: Dict[str, Any] = {}
        self._routes: Dict[str, 'BaseAPIRoute'] = {}
        self._auth: Optional['BaseClientAuth'] = None
        kwargs = self.configure_session_kwargs(**kwargs)
        kwargs = self.configure_auth(**kwargs)
        self.post_init(**kwargs)
        

    def post_init(self, **kwargs):
        """
        Post Initialization
        """
        pass

    def configure_auth(self, **kwargs) -> Dict[str, Any]:
        """
        Configures the auth
        """
        return kwargs

    def configure_session_kwargs(
        self,
        pool_connections: Optional[int] = 10,
        pool_maxsize: Optional[int] = 10,
        retries: Optional[int] = 5,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Configures the session kwargs
        """
        self._session_kwargs = {
            'pool_connections': pool_connections,
            'pool_maxsize': pool_maxsize,
            'retries': retries,
        }
        return kwargs

    @property
    def session(self) -> 'Session':
        """
        Returns the Session
        """
        if self._session is None:
            self._session = niquests.Session(**self._session_kwargs)
        return self._session
    
    @property
    def asession(self) -> 'AsyncSession':
        """
        Returns the Async Session
        """
        if self._asession is None:
            self._asession = niquests.AsyncSession(**self._session_kwargs)
        return self._asession
    

    def get_url(self, path: str) -> str:
        """
        Returns the URL
        """
        return urljoin(self.base_url, path) if self.base_url else path
    

    def hget(self, path: str, **kwargs) -> 'Response':
        """
        Returns the Response
        """
        if self._session_disabled:
            return niquests.get(self.get_url(path), auth = self.auth, **kwargs)
        return self.session.get(self.get_url(path), auth = self.auth, **kwargs)
    
    async def ahget(self, path: str, **kwargs) -> 'AsyncResponse':
        """
        Returns the Response
        """
        if not self._session_disabled:
            return await self.asession.get(self.get_url(path), auth = self.auth, **kwargs)
        async with niquests.AsyncSession() as s:
            return await s.get(self.get_url(path), auth = self.auth, **kwargs)
    
    def hpost(self, path: str, **kwargs) -> 'Response':
        """
        Returns the Response
        """
        if self._session_disabled:
            return niquests.post(self.get_url(path), auth = self.auth, **kwargs)
        return self.session.post(self.get_url(path), auth = self.auth, **kwargs)
    
    async def ahpost(self, path: str, **kwargs) -> 'AsyncResponse':
        """
        Returns the Response
        """
        if not self._session_disabled:
            return await self.asession.post(self.get_url(path), auth = self.auth, **kwargs)
        async with niquests.AsyncSession() as s:
            return await s.post(self.get_url(path), auth = self.auth, **kwargs)

    def hput(self, path: str, **kwargs) -> 'Response':
        """
        Returns the Response
        """
        if self._session_disabled:
            return niquests.put(self.get_url(path), auth = self.auth, **kwargs)
        return self.session.put(self.get_url(path), auth = self.auth, **kwargs)
    
    async def ahput(self, path: str, **kwargs) -> 'AsyncResponse':
        """
        Returns the Response
        """
        if not self._session_disabled:
            return await self.asession.put(self.get_url(path), auth = self.auth, **kwargs)
        async with niquests.AsyncSession() as s:
            return await s.put(self.get_url(path), auth = self.auth, **kwargs)
        
    
    def hpatch(self, path: str, **kwargs) -> 'Response':
        """
        Returns the Response
        """
        if self._session_disabled:
            return niquests.patch(self.get_url(path), auth = self.auth, **kwargs)
        return self.session.patch(self.get_url(path), auth = self.auth, **kwargs)
    
    async def ahpatch(self, path: str, **kwargs) -> 'AsyncResponse':
        """
        Returns the Response
        """
        if not self._session_disabled:
            return await self.asession.patch(self.get_url(path), auth = self.auth, **kwargs)
        async with niquests.AsyncSession() as s:
            return await s.patch(self.get_url(path), auth = self.auth, **kwargs)