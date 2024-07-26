from __future__ import annotations

"""
Persistent Dict Based Session Middleware
"""

import sys
import typing
from uuid import uuid4
from pathlib import Path
from starlette.datastructures import MutableHeaders, Secret
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from typing import Any, Dict, List, Optional, Union, Type, TYPE_CHECKING

if sys.version_info >= (3, 8):  # pragma: no cover
    from typing import Literal
else:  # pragma: no cover
    from typing_extensions import Literal

try:
    import xxhash

    def hash_func(data: str) -> str:
        """
        Returns the hash of the data
        """
        return xxhash.xxh64_hexdigest(data)

except ImportError:
    import hashlib

    def hash_func(data: str) -> str:
        """
        Returns the hash of the data
        """
        return hashlib.sha256(data.encode()).hexdigest()

if TYPE_CHECKING:
    from kvdb import PersistentDict
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

def create_session_key(*keys: str) -> str:
    """
    Creates a session key
    """
    joined_keys = ':'.join(keys)
    return hash_func(joined_keys)

def get_pdict(
    base_key: str,
    redis_url: Optional[str] = None,
    serializer: Optional[str] = 'json',
    serializer_kwargs: Optional[Dict[str, Any]] = None,
    expiration: Optional[int] = None,
    allow_local_fallback: bool = True,
    local_cache_file: Optional[Path] = None,
    **kwargs,
) -> 'PersistentDict':
    """
    Returns the Persistent Dict for data
    """
    try:
        from kvdb import KVDBClient
        from lazyops.utils.logs import logger
        sess = KVDBClient.get_session(
            name = 'fastapi.session',
            url = redis_url,
        )
        from lazyops.utils.helpers import fail_after
        try:
            with fail_after(5):
                sess.ping()
        except Exception as e:
            if not allow_local_fallback: raise ValueError(f'KVDB Sesssion is not available and local fallback is not allowed: {e}') from e
            logger.warning(f'KVDB Sesssion is not available and local fallback is not allowed: {e}')
            sess = None
    except ImportError as e:
        if not allow_local_fallback: raise ImportError('Persistent Dict is not available and local fallback is not allowed') from e
    
    if sess is not None:
        return sess.create_persistence(
            base_key = base_key,
            serializer = serializer,
            expiration = expiration,
            serializer_kwargs = serializer_kwargs,
            **kwargs,
        )
    from lazyops.libs.persistence import PersistentDict
    return PersistentDict(
        base_key = base_key,
        serializer = serializer,
        expiration = expiration,
        serializer_kwargs = serializer_kwargs,
        file_path = local_cache_file,
        **kwargs,
    )




class PersistentSessionMiddleware:
    def __init__(
        self,
        app: 'ASGIApp',
        secret_key: typing.Union[str, 'Secret'],
        session_cookie: str = "session",
        max_age: typing.Optional[int] = 14 * 24 * 60 * 60,  # 14 days, in seconds
        path: str = "/",
        same_site: Literal["lax", "strict", "none"] = "lax",
        https_only: bool = False,
        # Persistent Dict
        redis_url: Optional[str] = None,
        base_key: Optional[str] = None,
        serializer: Optional[str] = 'json',
        serializer_kwargs: Optional[Dict[str, Any]] = None,
        allow_local_fallback: bool = True,
        expiration: Optional[int] = None,
        **kwargs,
    ) -> None:
        self.app = app
        self.path = path
        self.secret_key = secret_key
        self.same_site = same_site
        self.https_only = https_only
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.security_flags = f"httponly; samesite={same_site}"
        if https_only:  # Secure flag can be used with HTTPS only
            self.security_flags += "; secure"
        self._pdict: Optional['PersistentDict'] = None
        if base_key is None: base_key = session_cookie
        self._pdict_kwargs: Dict[str, Any] = {
            'serializer': serializer,
            'serializer_kwargs': serializer_kwargs,
            'base_key': base_key,
            'redis_url': redis_url,
            'allow_local_fallback': allow_local_fallback,
            'expiration': expiration or max_age - 10,
            **kwargs,
        }
    
    @property
    def pdict(self) -> 'PersistentDict':
        """
        Returns the Persistent Dict
        """
        if self._pdict is None: self._pdict = get_pdict(**self._pdict_kwargs)
        return self._pdict
        

    async def __call__(self, scope: 'Scope', receive: 'Receive', send: 'Send') -> None:
        
        if scope["type"] not in ("http", "websocket"):  # pragma: no cover
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope)
        initial_session_was_empty = True
        initial_session_key = None
        if self.session_cookie in connection.cookies:
            session_key = connection.cookies[self.session_cookie]
            if await self.pdict.acontains(session_key):
                scope["session"] = await self.pdict.aget(session_key)
                initial_session_was_empty = False
                initial_session_key = session_key
            else: scope["session"] = {}
        else: scope["session"] = {}

        async def send_wrapper(message: 'Message') -> None:
            if message["type"] == "http.response.start":
                session_key = initial_session_key
                if scope['session']:
                    if not session_key:
                        if scope['session'].get('user_id'):
                            session_key = create_session_key(scope['session']['user_id'], self.secret_key)
                        else: session_key = create_session_key(str(uuid4()), self.secret_key)
                    await self.pdict.aset(session_key, scope['session'])
                    headers = MutableHeaders(scope=message)
                    header_value = "{session_cookie}={session_key}; path={path}; {max_age}{security_flags}".format(  # noqa E501
                        session_cookie = self.session_cookie,
                        session_key = session_key,
                        path=self.path,
                        max_age=f"Max-Age={self.max_age}; " if self.max_age else "",
                        security_flags=self.security_flags,
                    )
                    headers.append("Set-Cookie", header_value)
                
                elif not initial_session_was_empty:
                    # The session has been cleared.
                    headers = MutableHeaders(scope=message)
                    header_value = "{session_cookie}={data}; path={path}; {expires}{security_flags}".format(  # noqa E501
                        session_cookie=self.session_cookie,
                        data = "null",
                        path = self.path,
                        expires = "expires=Thu, 01 Jan 1970 00:00:00 GMT; ",
                        security_flags = self.security_flags,
                    )
                    headers.append("Set-Cookie", header_value)
                    if session_key: await self.pdict.adelete(session_key)
            await send(message)
        await self.app(scope, receive, send_wrapper)