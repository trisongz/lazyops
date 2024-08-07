from __future__ import annotations

"""
API Client that utilizes the AuthZero API
"""

import socket
import contextlib
from abc import ABC
from urllib.parse import urljoin
from lazyops.libs import lazyload
from lazyops.utils.helpers import timed_cache
from lazyops.libs.abcs.configs.types import AppEnv

from ..utils.lazy import get_az_settings, logger, get_az_flow, get_az_resource
from typing import Optional, List, Dict, Any, Union

if lazyload.TYPE_CHECKING:
    import aiohttpx
    import niquests
    import tldextract
    from aiohttpx import Client
    from niquests import Session, AsyncSession, Response, AsyncResponse
    from ..configs import AuthZeroSettings
    from ..flows.tokens import APIClientCredentialsFlow
    from ..flows.admin import AZManagementAPI
    from ..types.auth import AuthZeroTokenAuth
else:
    niquests = lazyload.LazyLoad("niquests")
    tldextract = lazyload.LazyLoad("tldextract")
    aiohttpx = lazyload.LazyLoad("aiohttpx")
    from ..types.tokens import AccessToken


def resolve_endpoint(
    endpoints: List[str],
) -> str:
    """
    Resolves the endpoint
    """
    for endpoint in endpoints:
        ep = tldextract.extract(endpoint)
        with contextlib.suppress(Exception):
            if ep.registered_domain:
                socket.gethostbyname(ep.registered_domain)
            else:
                socket.gethostbyaddr(ep.ipv4)
            return endpoint
    raise ValueError(f"Could not resolve endpoint: {endpoints}")


class AuthZeroAPIClient(ABC):

    """
    Generic Auth0 API Client that can be used to access other APIs that require Auth0 Authentication
    """

    name: Optional[str] = None
    api_key: Optional[str] = None
    api_client_id: Optional[str] = None
    api_client_env: Optional[Union[str, AppEnv]] = None

    oauth_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    endpoint: Optional[str] = None
    audience: Optional[str] = None
    session_enabled: Optional[bool] = True
    default_timeout: Optional[float] = 600.0
    default_retries: Optional[int] = 3
    use_httpx: Optional[bool] = False

    def __init__(
        self, 
        endpoint: Optional[Union[str, List[str]]] = None, 
        api_key: Optional[str] = None,
        api_client_id: Optional[str] = None, 
        api_client_env: Optional[str] = None, 

        audience: Optional[str] = None,
        oauth_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        session_enabled: Optional[bool] = None,
        verbose: Optional[bool] = False,
        use_httpx: Optional[bool] = None,
        **kwargs,
    ):
        if endpoint is not None: 
            if isinstance(endpoint, list):
                endpoint = resolve_endpoint(endpoint)
            self.endpoint = endpoint
        if api_key is not None: self.api_key = api_key
        if api_client_id is not None: self.api_client_id = api_client_id
        if api_client_env is not None: self.api_client_env = api_client_env
        
        if oauth_url is not None: self.oauth_url = oauth_url
        if client_id is not None: self.client_id = client_id
        if client_secret is not None: self.client_secret = client_secret
        
        if audience is not None: self.audience = audience
        if session_enabled is not None: self.session_enabled = session_enabled
        assert self.audience is not None, "Audience must be set"
        self.verbose = verbose
        if use_httpx is not None: self.use_httpx = use_httpx

        
        self._kwargs = kwargs
        self._settings: Optional['AuthZeroSettings'] = None
        self._token_flow: Optional['APIClientCredentialsFlow'] = None
        self._auth: Optional['AuthZeroTokenAuth'] = None
        self._identity: Optional[str] = None

        self._client: Optional['Client'] = None

        self._session: Optional['Session'] = None
        self._asession: Optional['AsyncSession'] = None

        self._data: Optional[Dict[str, Any]] = None
        self._authorized: Optional[bool] = None

    """
    Lazily Initialized Properties
    """
        
    @property
    def settings(self) -> 'AuthZeroSettings':
        """
        Returns the settings
        """
        if self._settings is None: self._settings = get_az_settings()
        return self._settings
    
    @property
    def token_flow(self) -> 'APIClientCredentialsFlow':
        """
        Token Flow
        """
        if self._token_flow is None:
            self._token_flow = get_az_flow(
                name = 'api_client_credentials',
                endpoint = self.endpoint,
                api_client_id = self.api_client_id,
                api_client_env = self.api_client_env,
                audience = self.audience,
                client_id = self.client_id,
                client_secret = self.client_secret,
                oauth_url = self.oauth_url,
            )
        return self._token_flow
    
    @property
    def auth(self) -> 'AuthZeroTokenAuth':
        """
        Auth Object
        """
        if self._auth is None:
            self._auth = get_az_resource(
                'auth_zero_token_auth',
                token_flow = self.token_flow,
            )
            self._auth.headers['accept'] = 'application/json'
            self._auth.headers['content-type'] = 'application/json'
            if self.api_key:
                self._auth.x_api_key = self.api_key
            if self.api_client_id:
                self._auth.headers[self.settings.api_client_id_header_key] = self.api_client_id
            if self.api_client_env:
                self._auth.headers[self.settings.api_client_env_header_key] = self.api_client_env
            if self._kwargs.get('headers'):
                self._auth.headers.update(self._kwargs.get('headers'))
        return self._auth
    
    @property
    def data(self) -> Dict[str, Any]:
        """
        Returns the data
        """
        if self._data is None: self._data = self.token_flow.load_data()
        return self._data


    def get_url(self, path: str) -> str:
        """
        Returns the URL
        """
        return urljoin(self.endpoint, path)
    
    def get_session_kwargs(self, is_async: Optional[bool] = None, **kwargs) -> Dict[str, Any]:
        """
        Returns the session kwargs
        """
        # resolvers: List[str] = kwargs.pop('resolver', [])
        # if not resolvers:
        #     resolvers = []
        #     if self.settings.in_k8s and 'cluster.local' in self.endpoint:
        #         from lazyops.utils.system import fetch_resolver_nameserver
        #         if resolver := fetch_resolver_nameserver():
        #             resolvers.append(f'dou://{resolver}')
        #     resolvers.extend(
        #         [
        #             'doh+cloudflare://',
        #             'doh+google://',
        #         ]
        #     )
        # if resolvers and is_async:
        #     resolvers = resolvers[0]
        # resolvers = resolvers or None
        # logger.info(f'Resolvers: {resolvers}')
        return {
            'pool_connections': self._kwargs.get('pool_connections', 10),
            'pool_maxsize': self._kwargs.get('pool_maxsize', 10),
            'retries': self._kwargs.get('retries', self.default_retries),
            # 'resolver': resolvers,
            **kwargs,
        }

    @property
    def session(self) -> 'Session':
        """
        Returns the Session
        """
        if self._session is None:
            self._session = niquests.Session(**self.get_session_kwargs())
        return self._session
    
    @property
    def asession(self) -> 'AsyncSession':
        """
        Returns the Async Session
        """
        if self._asession is None:
            self._asession = niquests.AsyncSession(**self.get_session_kwargs(is_async=True))
        return self._asession
    
    
    def reset_session(self):
        """
        Resets the session
        """
        if self._session is not None: self._session.close()
        self._session = None
    
    async def areset_session(self):
        """
        Resets the async session
        """
        if self._asession is not None: await self._asession.close()
        self._asession = None
        if self._session is not None:  self._session.close()
        self._session = None

    """
    Implement HTTPX Client
    """

    def get_client_kwargs(self, **kwargs) -> Dict[str, Any]:
        """
        Returns the client kwargs
        """
        return {
            'base_url': self.endpoint,
            'auth': self.auth,
            'timeout': self._kwargs.get('timeout', self.default_timeout),
            'limits': aiohttpx.Limits(
                max_connections = self._kwargs.get('max_connections', 100),
                max_keepalive_connections = self._kwargs.get('max_keepalive_connections', 20),
                keepalive_expiry = self._kwargs.get('keepalive_expiry', 60),
            ),    
            **kwargs,
        }

    @property
    def client(self) -> 'Client':
        """
        Returns the Client
        """
        if self._client is None:
            self._client = aiohttpx.Client(**self.get_client_kwargs())
        return self._client

    def reset_client(self):
        """
        Resets the client
        """
        if self._client is not None: self._client.close()
        self._client = None
    
    async def areset_client(self):
        """
        Resets the async client
        """
        if self._client is not None: await self._client.aclose()
        self._client = None

    
    def reset(self):
        """
        Resets the client
        """
        return self.reset_client() if self.use_httpx else self.reset_session()

    async def areset(self):
        """
        Resets the async client
        """
        return await self.areset_client() if self.use_httpx else await self.areset_session()
    
    @timed_cache(600, cache_if_result = True)
    def check_available(self) -> bool:
        """
        Checks if the API is available
        """
        response = None
        try:
            response = niquests.get(self.get_url('/healthz'), timeout = 1.5, retries = 3)
            response.raise_for_status()
            return True
        except Exception as e:
            if self.verbose: logger.warning(f'[{response.status_code} - {self.name}] Error checking API availability: {e}')
            return False
    
        
    @property
    def available(self) -> bool:
        """
        Returns True if the API is available
        """
        return self.check_available()
    
    @property
    def identity(self) -> str:
        """
        Returns the Identity
        """
        if self._identity is None:
            try:
                resp = niquests.get(self.get_url('/healthz'), timeout = 0.5, retries = 3)
                resp.raise_for_status()
                self._identity = resp.text
            except Exception as e:
                if self.verbose: logger.error(f'Error Checking Identity: {e}')
                self._identity = None
        return self._identity


    def check_authorization(self):
        """
        Checks authorization
        """
        if self._authorized: return
        try:
            if self.use_httpx:
                response = self.client.get('/authorize', timeout = 2.5)
            else:
                response = self.session.get(self.get_url('/authorize'), timeout = 2.5, auth = self.auth)
            response.raise_for_status()
        except (niquests.HTTPError, aiohttpx.HTTPError) as e:
            logger.error(f'Error Authorizing Client: {e}')
            return
        
        data: Dict[str, Any] = response.json()
        if api_key := data.get('api_key', data.get('api-key')):
            self._api_key = api_key
            self.data['api_key'] = api_key
            self.auth.x_api_key = api_key
        if api_env := data.get('environment'): self.data['environment'] = api_env
        if identity := data.get('identity'): self.data['identity'] = identity
        self._authorized = True
        self.token_flow.save_data(self.data)

    async def acheck_authorization(self):
        """
        Checks authorization
        """
        if self._authorized: return
        try:
            if self.use_httpx:
                response = await self.client.async_get('/authorize', timeout = 2.5)
            else:
                response = await self.asession.get(self.get_url('/authorize'), timeout = 2.5, auth = self.auth)
            response.raise_for_status()
        except (niquests.HTTPError, aiohttpx.HTTPError) as e:
            logger.error(f'Error Authorizing Client: {e}')
            return
        
        data: Dict[str, Any] = response.json()
        if api_key := data.get('api_key', data.get('api-key')):
            self._api_key = api_key
            self.data['api_key'] = api_key
            self.auth.x_api_key = api_key
        if api_env := data.get('environment'): self.data['environment'] = api_env
        if identity := data.get('identity'): self.data['identity'] = identity
        self._authorized = True
        await self.token_flow.asave_data(self.data)
    
    def preflight_check(self):
        """
        Conducts a pre-flight check
        """
        if not self.available:
            raise ValueError(f"API is not available: {self.endpoint}")
        self.check_authorization()
    
    async def apreflight_check(self):
        """
        Conducts a pre-flight check
        """
        if not self.available:
            raise ValueError(f"API is not available: {self.endpoint}")
        await self.acheck_authorization()
    
    def get_request_kwargs(self, timeout: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        """
        Returns the request kwargs
        """
        if self.use_httpx:
            if timeout is not None: kwargs['timeout'] = timeout
            return kwargs
        auth = kwargs.get('auth', self.auth)
        return {
            'timeout': timeout if timeout is not None else self.default_timeout,
            'auth': auth,
            **kwargs,
        }

    async def aget(self, url: str, *args, timeout: Optional[float] = None, **kwargs) -> 'AsyncResponse':
        """
        Async GET
        """
        await self.apreflight_check()
        kwargs = self.get_request_kwargs(timeout = timeout, **kwargs)
        if self.use_httpx: return await self.client.async_get(url, *args, **kwargs)
        return await self.asession.get(self.get_url(url), *args, **kwargs)

    async def aput(self, url: str, *args, timeout: Optional[float] = None, **kwargs) -> 'AsyncResponse':
        """
        Async PUT
        """
        await self.apreflight_check()
        kwargs = self.get_request_kwargs(timeout = timeout, **kwargs)
        if self.use_httpx: return await self.client.async_put(url, *args, **kwargs)
        return await self.asession.put(self.get_url(url), *args, **kwargs)
    
    async def apost(self, url: str, *args, timeout: Optional[float] = None, **kwargs) -> 'AsyncResponse':
        """
        Async POST
        """
        await self.apreflight_check()
        kwargs = self.get_request_kwargs(timeout = timeout, **kwargs)
        if self.use_httpx: return await self.client.async_post(url, *args, **kwargs)
        return await self.asession.post(self.get_url(url), *args, **kwargs)
    
    async def adelete(self, url: str, *args, timeout: Optional[float] = None, **kwargs) -> 'AsyncResponse':
        """
        Async DELETE
        """
        await self.apreflight_check()
        kwargs = self.get_request_kwargs(timeout = timeout, **kwargs)
        if self.use_httpx: return await self.client.async_delete(url, *args, **kwargs)
        return await self.asession.delete(self.get_url(url), *args, **kwargs)
    
    async def apatch(self, url: str, *args, timeout: Optional[float] = None, **kwargs) -> 'AsyncResponse':
        """
        Async PATCH
        """
        await self.apreflight_check()
        kwargs = self.get_request_kwargs(timeout = timeout, **kwargs)
        if self.use_httpx: return await self.client.async_patch(url, *args, **kwargs)
        return await self.asession.patch(self.get_url(url), *args, **kwargs)
    
    def get(self, url: str, *args, timeout: Optional[float] = None,  **kwargs) -> 'Response':
        """
        GET
        """
        self.preflight_check()
        kwargs = self.get_request_kwargs(timeout = timeout, **kwargs)
        if self.use_httpx: return self.client.get(url, *args, **kwargs)
        return self.session.get(self.get_url(url), *args, **kwargs)
    
    def put(self, url: str, *args, timeout: Optional[float] = None,  **kwargs) -> 'Response':
        """
        PUT
        """
        self.preflight_check()
        kwargs = self.get_request_kwargs(timeout = timeout, **kwargs)
        if self.use_httpx: return self.client.put(url, *args, **kwargs)
        return self.session.put(self.get_url(url), *args, **kwargs)
    
    def post(self, url: str, *args, timeout: Optional[float] = None, **kwargs) -> 'Response':
        """
        POST
        """
        self.preflight_check()
        kwargs = self.get_request_kwargs(timeout = timeout, **kwargs)
        if self.use_httpx: return self.client.post(url, *args, **kwargs)
        return self.session.post(self.get_url(url), *args, **kwargs)
    
    def delete(self, url: str, *args, timeout: Optional[float] = None, **kwargs) -> 'Response':
        """
        DELETE
        """
        self.preflight_check()
        kwargs = self.get_request_kwargs(timeout = timeout, **kwargs)
        if self.use_httpx: return self.client.delete(url, *args, **kwargs)
        return self.session.delete(self.get_url(url), *args, **kwargs)
    
    def patch(self, url: str, *args, timeout: Optional[float] = None, **kwargs) -> 'Response':
        """
        PATCH
        """
        self.preflight_check()
        kwargs = self.get_request_kwargs(timeout = timeout, **kwargs)
        if self.use_httpx: return self.client.patch(url, *args, **kwargs)
        return self.session.patch(self.get_url(url), *args, **kwargs)
    