from __future__ import annotations


from lzl.logging import logger
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from .types import errors
from starlette.responses import PlainTextResponse
from starlette.authentication import (
    AuthCredentials,
)
from starlette.requests import HTTPConnection
from lzl.ext.fast.types.responses import PrettyJSONResponse
from typing import Optional, Dict, Any, List, Union, Tuple, Callable, Type, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request, Response
    from .config import OAuth2Config
    from .types.user import OAuth2User, UnauthenticatedUser, TokenT
    from .types.token import OAuth2Token
    from .backend import OAuth2Backend



class OAuth2Middleware:
    """
    The OAuth2 Middleware
    """

    def __init__(
        self,
        app: ASGIApp,
        config: 'OAuth2Config',
        backend_class: Type['OAuth2Backend'],
        on_error: Optional[
            Callable[[HTTPConnection, errors.FastAPIException], Response]
        ] = None,
        **kwargs,
    ):
        """
        The OAuth2 Middleware
        """

        self.app = app
        self.config = config
        self.mtg = self.config.get_manager()
        self.backend_class = backend_class
        self.on_error: Callable[
            [HTTPConnection, errors.FastAPIException], Response
        ] = (on_error if on_error is not None else self.default_on_error)

        excluded_url_paths = [
            '/healthz',
            '/health',
            '/metrics',
            '/openapi.json',
        ]
        if self.config.disabled_paths:
            excluded_url_paths += [
                p for p in self.config.disabled_paths if p not in excluded_url_paths
            ]
        if self.mtg.routes.get('callback'):
            excluded_url_paths.append(self.mtg.routes['callback'])
            excluded_url_paths.extend(
                self.mtg.routes['callback'] + "/" + provider
                for provider in self.mtg.providers
            )
        if self.mtg.routes.get('start'):
            excluded_url_paths.append(self.mtg.routes['start'])
            excluded_url_paths.extend(
                self.mtg.routes['start'] + "/" + provider
                for provider in self.mtg.providers
            )
        self.excluded_url_paths = set(excluded_url_paths)
        self.backend = self.backend_class(self.config)
        self.mtg.oauth2_middleware = self
        if self.mtg.excluded_paths:
            self.excluded_url_paths.update(self.mtg.excluded_paths)

    @property
    def middleware_handlers(self) -> List[Callable[..., Awaitable['Scope']]]:
        """
        Returns the middleware handlers
        """
        return self.mtg.custom_middleware_handlers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        The OAuth2 Middleware
        """
        if scope["type"] not in ["http", "websocket"]:
            await self.app(scope, receive, send)
            return
        if scope['path'] in self.excluded_url_paths:
            await self.app(scope, receive, send)
            return
        conn = HTTPConnection(scope)
        try:
            auth_result = await self.backend.authenticate(conn)
        except errors.OAuth2Exception as exc:
            response = self.on_error(conn, exc)
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1000})
            else:
                await response(scope, receive, send)
            return

        if auth_result is None:
            auth_result = AuthCredentials(), self.mtg.unauth_user_class()
        scope["auth"], scope["user"] = auth_result
        if self.middleware_handlers:
            for handler in self.middleware_handlers:
                scope = await handler(scope)
        await self.app(scope, receive, send)

    
    @staticmethod
    def default_on_error(conn: HTTPConnection, exc: Union[Exception, errors.FastAPIException]) -> PrettyJSONResponse:
        """
        Returns the default error response
        """
        if hasattr(exc, 'json_data'):
            return PrettyJSONResponse(content = exc.json_data(), status_code=exc.status_code, headers = exc.headers)
        return PlainTextResponse(str(exc), status_code=400)
