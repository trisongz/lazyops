from __future__ import annotations

"""
Persistent Dict Based Session Middleware
"""

import os
import typing
from uuid import uuid4
from starlette.datastructures import MutableHeaders, Secret
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from typing import Any, Dict, List, Optional, Union, Type, TYPE_CHECKING, Callable, Awaitable, Tuple
from lzl.logging import logger, null_logger
from lzl.types import Literal
from .utils import get_pdict, create_session_key

if TYPE_CHECKING:
    from lzl.io import PersistentDict
    from lzl.pool import ThreadPool

class PersistentMiddleware:

    """
    Persistent Middleware
    """

    prehooks: List[Callable[..., Awaitable[None]]] = []
    presend_hooks: List[Callable[..., Awaitable[None]]] = []
    posthooks: List[Callable[..., Awaitable[None]]] = []

    state_prehooks: List[Callable[..., Awaitable[None]]] = []
    state_presend_hooks: List[Callable[..., Awaitable[None]]] = []
    state_posthooks: List[Callable[..., Awaitable[None]]] = []

    def __init__(
        self,
        app: 'ASGIApp',
        secret_key: typing.Union[str, 'Secret'],
        session_cookie: str = "session",
        max_age: typing.Optional[int] = 14 * 24 * 60 * 60,  # 14 days, in seconds
        path: str = "/",
        same_site: Literal["lax", "strict", "none"] = "lax",

        http_only: bool = True,
        https_only: bool = False,

        # Persistent Dict
        redis_url: Optional[str] = None,
        base_key: Optional[str] = None,
        serializer: Optional[str] = 'json',
        serializer_kwargs: Optional[Dict[str, Any]] = None,
        allow_local_fallback: bool = True,
        expiration: Optional[int] = None,
        
        # Extra Configuration
        excluded_session_url_paths: Optional[List[str]] = None,
        inject_app_endpoint: Optional[bool] = True,
        oauth2_enabled: Optional[bool] = False,

        # State Configuration
        state_enabled: Optional[bool] = True,
        state_cookie: Optional[str] = "state",
        state_expiration: Optional[int] = 60 * 5,
        state_kws: Optional[List[str]] = None,

        # Hooks
        prehooks: Optional[List[Callable[..., Awaitable[None]]]] = None,
        presend_hooks: Optional[List[Callable[..., Awaitable[None]]]] = None,
        posthooks: Optional[List[Callable[..., Awaitable[None]]]] = None,

        debug_enabled: Optional[bool] = False,

        **kwargs,
    ) -> None:
        self.app = app
        self.path = path
        self.secret_key = secret_key
        self.same_site = same_site
        self.https_only = https_only
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.security_flags = f"SameSite={same_site}"
        if http_only: self.security_flags += "; HttpOnly"
        if https_only:  # Secure flag can be used with HTTPS only
            self.security_flags += "; Secure"
        self._pdict: Optional['PersistentDict'] = None
        self.oauth2_enabled = oauth2_enabled
        if base_key is None: base_key = session_cookie
        if excluded_session_url_paths is None: excluded_session_url_paths = [
            '/healthz',
            '/health',
            '/metrics',
        ]
        self.excluded_session_url_paths = set(excluded_session_url_paths)
        self.state_cookie = state_cookie
        self.state_enabled = state_enabled
        self.state_expiration = state_expiration
        self.state_kws = state_kws or [
            '_token',
            '_user',
            '_apikey',
        ] if oauth2_enabled else []
        self._app_endpoint_enabled = inject_app_endpoint
        self._pdict_kwargs: Dict[str, Any] = {
            'serializer': serializer,
            'serializer_kwargs': serializer_kwargs,
            'base_key': base_key,
            'redis_url': redis_url or os.getenv('SESSION_REDIS_URL'),
            'allow_local_fallback': allow_local_fallback,
            'expiration': expiration or max_age - 10,
            **kwargs,
        }
        if prehooks: self.prehooks.extend(prehooks)
        if presend_hooks: self.presend_hooks.extend(presend_hooks)
        if posthooks: self.posthooks.extend(posthooks)
        self.logger = logger if debug_enabled else null_logger
        self._extra: Dict[str, Any] = {}
    
    @property
    def pdict(self) -> 'PersistentDict[str, Dict[str, Any]]':
        """
        Returns the Persistent Dict
        """
        if self._pdict is None: self._pdict = get_pdict(**self._pdict_kwargs)
        return self._pdict
    
    @property
    def state_pdict(self) -> 'PersistentDict[str, Dict[str, Any]]':
        """
        Returns the Persistent Dict for State
        """
        if 'state_pdict' not in self._extra:
            self._extra['state_pdict'] = self.pdict.get_child('states', expiration = self.state_expiration)
        return self._extra['state_pdict']
    
    @property
    def state_id_pdict(self) -> 'PersistentDict[str, str]':
        """
        Returns the Persistent Dict for State IDs
        """
        if 'state_id_pdict' not in self._extra:
            self._extra['state_id_pdict'] = self.pdict.get_child('state_id', expiration = 60 * 5)
        return self._extra['state_id_pdict']
    
    @property
    def in_k8s(self) -> bool:
        """
        Returns whether we are in k8s
        """
        if 'in_k8s' not in self._extra: 
            from lzo.utils.system import is_in_kubernetes
            self._extra['in_k8s'] = is_in_kubernetes()
        return self._extra['in_k8s']
    
    @property
    def pooler(self) -> 'ThreadPool':
        """
        Returns the ThreadPool
        """
        if 'pooler' not in self._extra:
            from lzl.pool import ThreadPool
            self._extra['pooler'] = ThreadPool
        return self._extra['pooler']

    def get_app_domain_from_scope(self, scope: 'Scope') -> Optional[str]:
        """
        Returns the domain from the scope
        """
        headers: Dict[str, str] = {
            v[0].decode('utf-8'): v[1].decode('utf-8')
            for v in scope['headers']
        }
        if headers.get(':authority:'):
            return headers[':scheme:'] + '://' + headers[':authority:']
        if headers.get('x-forwarded-host'):
            if headers.get('x-forwaded-scheme'):
                return headers['x-forwaded-scheme'] + '://' + headers['x-forwarded-host']
            if self.in_k8s:
                return 'https://' + headers['x-forwarded-host']
            forwaded_port = headers['x-forwarded-port']
            if '443' in forwaded_port: return 'https://' + headers['x-forwarded-host']
            return 'http://' + headers['x-forwarded-host']
        if headers.get('host'):
            scheme = 'https' if self.in_k8s else 'http'
            return f'{scheme}://' + headers['host']
        return None


    async def get_cookie_header_value(
        self,
        scope: 'Scope',
        session_key: Optional[str] = None, # If no session key is provided, it assumes the session should be deleted
        state_key: Optional[str] = None, # If no session key is provided, it assumes the session should be deleted
        kind: Optional[Literal['session', 'state']] = 'session',
        **kwargs,
    ) -> str:  # sourcery skip: assign-if-exp, reintroduce-else, switch
        """
        Returns the cookie header value
        """
        if kind == 'session':
            if not session_key:
                return "{session_cookie}={data}; path={path}; {expires}{security_flags}".format(  # noqa E501
                    session_cookie=self.session_cookie,
                    data = "null",
                    path = self.path,
                    expires = "expires=Thu, 01 Jan 1970 00:00:00 GMT; ",
                    security_flags = self.security_flags,
                )
            return "{session_cookie}={session_key}; path={path}; {max_age}{security_flags}".format(  # noqa E501
                session_cookie = self.session_cookie,
                session_key = session_key,
                path = self.path,
                max_age=f"Max-Age={self.max_age}; " if self.max_age else "",
                security_flags=self.security_flags,
            )
        elif kind == 'state':
            if not state_key:
                return "{state_cookie}={data}; path={path}; {expires}{security_flags}".format(  # noqa E501
                    state_cookie=self.state_cookie,
                    data = "null",
                    path = self.path,
                    expires = "expires=Thu, 01 Jan 1970 00:00:00 GMT; ",
                    security_flags = self.security_flags,
                )
            return "{state_cookie}={state_key}; path={path}; {max_age}{security_flags}".format(  # noqa E501
                state_cookie = self.state_cookie,
                state_key = state_key,
                path = self.path,
                max_age=f"Max-Age={self.max_age}; " if self.max_age else "",
                security_flags=self.security_flags,
            )
        raise ValueError(f'Invalid Kind: {kind}')

    async def run_prehooks(self, scope: 'Scope', connection: 'HTTPConnection', receive: 'Receive', send: 'Send'):
        """
        Runs the prehooks
        """
        if not self.prehooks: return
        for prehook in self.prehooks:
            await self.pooler.asyncish(prehook, self, scope = scope, connection = connection, receive = receive, send = send)
    
    async def run_presend_hooks(self, scope: 'Scope', message: 'Message'):
        """
        Runs the presend hooks
        """
        if not self.presend_hooks: return
        for presend_hook in self.presend_hooks:
            await self.pooler.asyncish(presend_hook, self, scope = scope, message = message)
    
    async def run_posthooks(self, scope: 'Scope', message: 'Message'):
        """
        Runs the posthooks
        """
        if not self.posthooks: return
        for posthook in self.posthooks:
            await self.pooler.asyncish(posthook, self, scope = scope, message = message)
    

    async def run_state_prehooks(self, scope: 'Scope', connection: 'HTTPConnection', receive: 'Receive', send: 'Send'):
        """
        Runs the state prehooks
        """
        if not self.state_prehooks: return
        for prehook in self.state_prehooks:
            await self.pooler.asyncish(prehook, self, scope = scope, connection = connection, receive = receive, send = send)
    
    async def run_state_presend_hooks(self, scope: 'Scope', message: 'Message'):
        """
        Runs the state presend hooks
        """
        if not self.state_presend_hooks: return
        for presend_hook in self.state_presend_hooks:
            await self.pooler.asyncish(presend_hook, self, scope = scope, message = message)
    
    async def run_state_posthooks(self, scope: 'Scope', message: 'Message'):
        """
        Runs the state posthooks
        """
        if not self.state_posthooks: return
        for posthook in self.state_posthooks:
            await self.pooler.asyncish(posthook, self, scope = scope, message = message)

    async def run_mw_hooks(self, stage: Literal['pre', 'presend', 'post'], scope: 'Scope', connection: 'HTTPConnection', receive: 'Receive', send: 'Send'):
        """
        Runs the class middleware hooks.

        This can be used to customize the behavior of a subclassed middleware.
        """
        pass

    async def modify_headers(self, headers: MutableHeaders, scope: 'Scope', **kwargs):
        """
        A hook that can be used to modify the headers
        """
        pass

    async def configure_session(
        self,
        connection: 'HTTPConnection',
        scope: 'Scope',
        **kwargs,
    ) -> Tuple[bool, Optional[str]]:
        """
        Configures the session
        """
        initial_session_was_empty = True
        initial_session_key = None
        if self.oauth2_enabled and (state_id := connection.query_params.get('state')):
            self.logger.info(f'State ID: {state_id}')
            if await self.state_id_pdict.acontains(state_id):
                session_key = await self.state_id_pdict.aget(state_id)
                scope["session"] = await self.pdict.aget(session_key)
                initial_session_was_empty = False
                initial_session_key = session_key
                self.logger.info(f'Found Session Key: {session_key}')
            else: scope["session"] = {}
        elif self.session_cookie in connection.cookies:
            session_key = connection.cookies[self.session_cookie]
            if await self.pdict.acontains(session_key):
                scope["session"] = await self.pdict.aget(session_key)
                initial_session_was_empty = False
                initial_session_key = session_key
            else: scope["session"] = {}
        else: scope["session"] = {}
        return initial_session_was_empty, initial_session_key

    async def save_session(
        self,
        scope: 'Scope',
        message: 'Message',
        session_key: Optional[str],
        initial_session_was_empty: Optional[bool],
        **kwargs,
    ) -> 'MutableHeaders':
        """
        Saves the session
        """
        if scope['session']:
            if scope['session'].get('session_id'):
                if session_key and session_key != scope['session']['session_id']:
                    await self.pdict.aexpire(session_key, 60)
                session_key = scope['session']['session_id']
            
            if not session_key:
                if scope['session'].get('user_id'):
                    session_key = create_session_key(scope['session']['user_id'], self.secret_key)
                else: session_key = create_session_key(str(uuid4()), self.secret_key)
            
            if self.oauth2_enabled and scope['session'].get('state_id'):
                self.logger.info(f'Setting State ID: {scope["session"]["state_id"]} -> Session Key: {session_key}')
                await self.state_id_pdict.aset(scope['session']['state_id'], session_key)
            
            await self.pdict.aset(session_key, scope['session'])
            headers = MutableHeaders(scope=message)
            header_value = await self.get_cookie_header_value(scope, session_key = session_key, kind = 'session')
            headers.append("Set-Cookie", header_value)
        
        elif not initial_session_was_empty:
            # The session has been cleared.
            headers = MutableHeaders(scope=message)
            header_value = await self.get_cookie_header_value(scope, kind = 'session')
            headers.append("Set-Cookie", header_value)
            if session_key: await self.pdict.adelete(session_key)
        return headers

    async def configure_state(
        self,
        connection: 'HTTPConnection',
        scope: 'Scope',
        **kwargs,
    ) -> Tuple[bool, Optional[str]]:  # sourcery skip: use-assigned-variable
        """
        Configures the state
        """
        initial_state_was_empty = True
        initial_state_key = None
        if not self.state_enabled: return initial_state_was_empty, initial_state_key
        if self.oauth2_enabled and (state_id := connection.query_params.get('state')):
            self.logger.info(f'State ID: {state_id}')
            if await self.state_id_pdict.acontains(state_id):
                state_key = await self.state_id_pdict.aget(state_id)
                scope["state"] = await self.state_pdict.aget(state_key)
                initial_state_was_empty = False
                initial_state_key = state_key
                self.logger.info(f'Found State Key: {state_key}')
            else: scope["state"] = {}
        elif self.state_cookie in connection.cookies:
            state_key = connection.cookies[self.state_cookie]
            if await self.state_pdict.acontains(state_key):
                scope["state"] = await self.state_pdict.aget(state_key)
                initial_state_was_empty = False
                initial_state_key = state_key
                self.logger.info(f'Loaded State: {state_key}')
            else: scope["state"] = {}
        else: scope["state"] = {}
        return initial_state_was_empty, initial_state_key

    async def save_state(
        self,
        scope: 'Scope',
        headers: 'MutableHeaders',
        state_key: Optional[str],
        initial_state_was_empty: Optional[bool],
        **kwargs,
    ) -> 'MutableHeaders':
        """
        Saves the State
        """
        if not self.state_enabled: return headers
        if scope['state']:
            if scope['state'].get('state_id'):
                if state_key and state_key != scope['state']['state_id']:
                    await self.state_pdict.aexpire(state_key, 60)
                state_key = scope['state']['state_id']
            if not state_key:
                if scope['state'].get('user_id'):
                    state_key = create_session_key(scope['state']['user_id'], self.secret_key)
                else: state_key = create_session_key(str(uuid4()), self.secret_key)
            
            if self.oauth2_enabled and scope['state'].get('state_id'):
                logger.info(f'Setting State ID: {scope["state"]["state_id"]} -> State Key: {state_key}')
                await self.state_id_pdict.aset(scope['state']['state_id'], state_key)
            
            state = {k:v for k,v in scope['state'].items() if k in self.state_kws}
            self.logger.info(f'Saving State: {state}', prefix = state_key, colored = True)
            await self.state_pdict.aset(state_key, state)
            # await self.state_pdict.aset(state_key, scope['state'])
            header_value = await self.get_cookie_header_value(scope, state_key = state_key, kind = 'state')
            headers.append("Set-Cookie", header_value)
        
        elif not initial_state_was_empty:
            # The state has been cleared.
            header_value = await self.get_cookie_header_value(scope, kind = 'state')
            headers.append("Set-Cookie", header_value)
            if state_key: await self.state_pdict.adelete(state_key)
        return headers
        

    async def __call__(self, scope: 'Scope', receive: 'Receive', send: 'Send') -> None:
        
        if scope["type"] not in ("http", "websocket"):  # pragma: no cover
            await self.app(scope, receive, send)
            return
        
        if scope['path'] in self.excluded_session_url_paths:
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope)
        initial_session_was_empty, initial_session_key = await self.configure_session(
            connection, 
            scope
        )
        initial_state_was_empty, initial_state_key = await self.configure_state(
            connection, 
            scope
        )
        if self._app_endpoint_enabled:
            scope["session"]["app_endpoint"] = self.get_app_domain_from_scope(scope)
        
        await self.run_prehooks(scope, connection, receive, send)
        await self.run_state_prehooks(scope, connection, receive, send)
        await self.run_mw_hooks('pre', scope, connection, receive, send)

        async def send_wrapper(message: 'Message') -> None:
            if message["type"] == "http.response.start":
                await self.run_presend_hooks(scope, message)
                await self.run_state_presend_hooks(scope, message)
                await self.run_mw_hooks('presend', scope, connection, receive, send)
                session_key = initial_session_key
                headers = await self.save_session(
                    scope, 
                    message, 
                    session_key, 
                    initial_session_was_empty
                )
                state_key = initial_state_key
                headers = await self.save_state(
                    scope, 
                    headers, 
                    state_key, 
                    initial_state_was_empty
                )
                await self.modify_headers(headers, scope, session_key = session_key)
            await self.run_posthooks(scope, message)
            await self.run_state_posthooks(scope, message)
            await self.run_mw_hooks('post', scope, connection, receive, send)
            await send(message)
        
        await self.app(scope, receive, send_wrapper)


    @classmethod
    def register_prehook(
        cls,
        prehook: Union[Callable[..., Awaitable[None]], List[Callable[..., Awaitable[None]]]],
        kind: Optional[Literal['session', 'state']] = 'session',
    ):
        """
        Registers a prehook
        """
        if kind == 'state':
            if isinstance(prehook, list): cls.state_prehooks.extend(prehook)
            else: cls.state_prehooks.append(prehook)
        elif kind == 'session':
            if isinstance(prehook, list): cls.prehooks.extend(prehook)
            else: cls.prehooks.append(prehook)

    @classmethod
    def register_presend_hook(
        cls,
        prehook: Union[Callable[..., Awaitable[None]], List[Callable[..., Awaitable[None]]]],
        kind: Optional[Literal['session', 'state']] = 'session',
    ):
        """
        Registers a presend hook
        """
        if kind == 'state':
            if isinstance(prehook, list): cls.state_presend_hooks.extend(prehook)
            else: cls.state_presend_hooks.append(prehook)
        elif kind == 'session':
            if isinstance(prehook, list): cls.prehooks.extend(prehook)
            else: cls.prehooks.append(prehook)


    @classmethod
    def register_posthook(
        cls,
        posthook: Union[Callable[..., Awaitable[None]], List[Callable[..., Awaitable[None]]]],
        kind: Optional[Literal['session', 'state']] = 'session',
    ):
        """
        Registers a posthook
        """
        if kind == 'state':
            if isinstance(posthook, list): cls.state_posthooks.extend(posthook)
            else: cls.state_posthooks.append(posthook)
        elif kind == 'session':
            if isinstance(posthook, list): cls.posthooks.extend(posthook)
            else: cls.posthooks.append(posthook)
        