from __future__ import annotations

from starlette.middleware.authentication import AuthenticationBackend
from lzl.logging import logger
from typing import Optional, Dict, Any, List, Union, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request, Response
    from starlette.requests import HTTPConnection
    from .config import OAuth2Settings
    from .types.user import OAuth2User
    from .types.token import OAuth2Token


class OAuth2Backend(AuthenticationBackend):
    """
    The OAuth2 Backend
    """
    def __init__(
        self,
        settings: 'OAuth2Settings',
        **kwargs,
    ):
        """
        The OAuth2 Backend
        """
        self.settings = settings
        self.manager = settings.get_manager()

    def get_jwt_token_from_request(self, request: 'Request') -> Optional[str]:
        """
        Gets the JWT Token from the Request
        """
        if not request.headers.get(self.settings.header): return None
        auth = request.headers.get(self.settings.header)
        scheme, token = auth.split(' ', 1)
        return None if scheme.lower() != self.settings.scheme.lower() else token

    async def has_valid_session(self, request: 'Request') -> bool:
        """
        Checks if the session is valid
        """
        if '_oauth' not in request.session: return False


    async def authenticate(
        self, 
        request: 'Request'
    ) -> Optional[Tuple["OAuth2Token", "OAuth2User"]]:
        """
        The authenticate method
        """
        # If a token is present, we always validate it first.
        # If no token is present, we check if there is a session.

        token = self.get_jwt_token_from_request(request)
        from_session = False
        if not token and '_oauth' in request.session:
            token = request.session['_oauth']
            from_session = True
            # logger.info(f'Authenticating Token from Session: {token}')
        if not token: return None, self.manager.user_class(None, None)
        return await self.manager.authenticate_oauth_token(token, request, from_session = from_session)
        
        # provider = await self.manager.get_provider_for_jwt(token, request)
        # logger.info(f'Authenticating Provider: {provider.name}')
        # token_payload = provider.parse_authorization_token(token, verify_exp=False)
        # # logger.info(f'Token Payload: {token_payload}')
        # oauth_token = self.manager.parse_token_payload(token_payload, provider)
        # if oauth_token.is_expired:
        # logger.info(oauth_token)
        # return oauth_token, self.manager.user_class(oauth_token, provider)



