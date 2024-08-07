from __future__ import annotations

"""
Session Middleware
"""

import sys
import json
import typing
import xxhash
from base64 import b64decode, b64encode
from starlette.datastructures import MutableHeaders, Secret
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from typing import Any, Dict, List, Optional, Union, Type, TYPE_CHECKING

if sys.version_info >= (3, 8):  # pragma: no cover
    from typing import Literal
else:  # pragma: no cover
    from typing_extensions import Literal

if TYPE_CHECKING:
    from ..config import KindeSettings
    from ..client import KindeClient

def create_session_key(user_id: str) -> str:
    """
    Creates a session key
    """
    return xxhash.xxh64_hexdigest(user_id)

class KindeSessionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        client: 'KindeClient',
        path: str = "/",
        same_site: Literal["lax", "strict", "none"] = "lax",
        https_only: bool = False,
    ) -> None:
        self.app = app
        self.client = client
        self.path = path
        self.same_site = same_site
        self.https_only = https_only
        self.security_flags = f"httponly; samesite={same_site}"
        if https_only:  # Secure flag can be used with HTTPS only
            self.security_flags += "; secure"
        
        self.settings = client.settings

    @property
    def session_cookie(self) -> str:
        """
        Returns the session cookie
        """
        return self.settings.session_cookie_key
    
    @property
    def max_age(self) -> int:
        """
        Returns the max age
        """
        return self.settings.user_session_expiration
    

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        
        if scope["type"] not in ("http", "websocket"):  # pragma: no cover
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope)
        initial_session_was_empty = True
        initial_session_key = None
        if self.session_cookie in connection.cookies:
            session_key = connection.cookies[self.session_cookie]
            if await self.client.session_data.acontains(session_key):
                scope["session"] = await self.client.session_data.aget(session_key)
                initial_session_was_empty = False
                initial_session_key = session_key
            else:
                scope["session"] = {}
        else:
            scope["session"] = {}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                if scope['session'] and scope['session'].get('user_id'):
                    session_key = create_session_key(scope['session']['user_id'])
                    await self.client.session_data.aset(session_key, scope['session'])
                    headers = MutableHeaders(scope=message)
                    header_value = "{session_cookie}={session_key}; path={path}; {max_age}{security_flags}".format(  # noqa E501
                        session_cookie = self.settings.session_cookie_key,
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
                    if initial_session_key:
                        await self.client.session_data.adelete(initial_session_key)
            await send(message)

        await self.app(scope, receive, send_wrapper)