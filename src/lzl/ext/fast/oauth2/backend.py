from __future__ import annotations

from starlette.middleware.authentication import AuthenticationBackend
from lzl.logging import logger
from .types import errors
from typing import Optional, Dict, Any, List, Union, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request, Response
    from starlette.requests import HTTPConnection
    from .config import OAuth2Config
    from .types.user import OAuth2User, UnauthenticatedUser, TokenT
    from .types.token import OAuth2Token


class OAuth2Backend(AuthenticationBackend):
    """
    The OAuth2 Backend
    """
    def __init__(
        self,
        config: 'OAuth2Config',
        **kwargs,
    ):
        """
        The OAuth2 Backend
        """
        self.config = config
        self.mtg = config.get_manager()
        self.mtg.oauth2_backend = self
        from lzl.pool import ThreadPool
        self.pool = ThreadPool
        # list(self.mtg.routes.values())

    def get_jwt_token_from_request(self, request: 'Request') -> Optional[str]:
        """
        Gets the JWT Token from the Request
        """
        auth: Optional[str] = None
        if request.headers.get(self.config.header): 
            auth = request.headers.get(self.config.header)
        elif self.config.enable_query_params and request.query_params.get(self.config.auth_query_param):
            return request.query_params.get(self.config.auth_query_param)
            # logger.info(f'Auth Query Param: {auth}')
        if not auth: return None
        if self.config.scheme.lower() not in auth.lower(): return None
        scheme, token = auth.split(' ', 1)
        return None if scheme.lower() != self.config.scheme.lower() else token
    
    def get_api_key_from_request(self, request: 'Request') -> Optional[str]:
        """
        Gets the API Key from the Request
        """
        if self.config.enable_query_params:
            return next(
                (
                    request.headers.get(key)
                    for key in {'x-authz-key', 'x-api-key'}
                    if request.headers.get(key)
                ),
                (
                    request.query_params.get(self.config.api_key_query_param) or 
                    None
                ),
            )

        return next(
            (
                request.headers.get(key)
                for key in {'x-authz-key', 'x-api-key'}
                if request.headers.get(key)
            ),
            None,
        )


    async def has_valid_session(self, request: 'Request') -> bool:
        """
        Checks if the session is valid
        """
        if '_oauth' not in request.session: return False

    def _not_authenticated(self, request: 'Request') -> Tuple[None, 'UnauthenticatedUser']:
        """
        Returns the Unauthenticated User
        """
        return None, self.mtg.unauth_user_class()
    
    def is_optional_path(self, request: 'Request') -> bool:
        """
        Checks if the request is an optional path
        """
        return request.url.path in self.mtg.optional_paths
        # or \
        #     request.url.path in self.mtg.disabled_paths

    async def state_handler(
        self,
        request: 'Request',
        auth: Optional[Tuple['TokenT', 'OAuth2User']] = None,
        **kwargs,
    ):
        """
        Handles the state
        """
        token, user = auth
        if token is None: return auth
        request.state._state.update({
            self.mtg.state_kw_map['token']: token, 
            self.mtg.state_kw_map['user']: user, 
            self.mtg.state_kw_map['apikey']: user.apikey
        })
        return auth

    async def authenticate_oauth2_token(
        self,
        request: 'Request',
        token: str,
        optional: Optional[bool] = None,
        **kwargs,
    ) -> Optional[Tuple['TokenT', 'OAuth2User']]:
        """
        Authenticates the OAuth2 Token
        """
        # logger.info(f'Authenticating OAuth2 Token: {token}')
        provider = await self.mtg.get_provider_for_jwt(token, request)
        oauth_token = await provider.aparse_authorization_token(token, raise_errors = not optional)
        # logger.info(f'Parsed OAuth2 Token: {oauth_token}')
        if oauth_token is None:
            return self._not_authenticated(request)
        if oauth_token.is_expired and not optional:
            raise errors.ExpiredTokenError(f'Expired Token: {token}')
        return oauth_token, await self.mtg.user_class.afrom_authorization(
            token = oauth_token, 
            provider = provider, 
            manager = self.mtg, 
            request = request
        )
    
    async def authenticate_api_key_user(
        self,
        request: Request,
        api_key: str,
        optional: Optional[bool] = None,
        **kwargs,
    ):
        """
        Authenticates the API Key User
        """
        api_key_user = self.mtg.api_key_users[api_key]
        if not api_key_user.has_allowed_env(self.config.app_env.name):
            if not optional: raise errors.InvalidEnvironmentError('Invalid API Key', env = self.config.app_env.name, key_envs = api_key_user.allowed_envs)
            return self._not_authenticated(request)
        
        if not api_key_user.has_allowed_domain(self.mtg.fetch_app_endpoint_from_request(request)):
            if not optional: raise errors.InvalidDomainError('Invalid API Key', key_domains = api_key_user.allowed_domains)
            return self._not_authenticated(request)
        
        return api_key_user, await self.mtg.user_class.afrom_api_key_user(
            api_key_user = api_key_user,
            provider = self.mtg.get_oauth_provider(api_key_user.provider, raise_errors = False) if api_key_user.provider else None,
            manager = self.mtg, 
            request = request,
            apikey = api_key,
        )


    async def authenticate_api_key(
        self,
        request: Request,
        api_key: str,
        optional: Optional[bool] = None,
        **kwargs,
    ) -> Tuple['OAuth2Token', 'OAuth2User']:
        """
        Handles the API Key Authentication
        """
        if api_key in self.mtg.api_key_users:
            return await self.authenticate_api_key_user(request = request, api_key = api_key, optional = optional)

        # Decode the API Key
        decoded_data = self.mtg.decrypt_api_key(api_key)
        if 'provider' not in decoded_data:
            raise errors.InvalidAPIKeyError(f'Invalid API Key: {api_key}')
        provider = self.mtg.get_oauth_provider(decoded_data['provider'])
        oauth_token = await provider.afetch_token_for_identity(decoded_data['identity'], raise_errors = not optional)
        if oauth_token is None:
            request.session.pop(self.mtg.session_oauth2_key, None)
            if not optional: raise errors.InvalidAPIKeyError(f'Invalid API Key: {api_key}')
            return self._not_authenticated(request)
        return oauth_token, await self.mtg.user_class.afrom_api_key(
            token = oauth_token, 
            provider = provider, 
            manager = self.mtg, 
            request = request,
            apikey = api_key,
        )
        


    async def authenticate_from_session(
        self,
        request: Request,
        optional: Optional[bool] = None,
        **kwargs,
    ) -> Tuple['OAuth2Token', 'OAuth2User']:
        """
        Handles the Session Authentication
        """
        oauth_data: Dict[str, Any] = request.session.get(self.mtg.session_oauth2_key)
        provider = self.mtg.get_oauth_provider(oauth_data['provider'])
        oauth_token = await provider.afetch_token_for_identity(oauth_data['identity'], raise_errors=not optional)
        if oauth_token is None:
            request.session.pop(self.mtg.session_oauth2_key, None)
            return self._not_authenticated(request)
        return oauth_token, await self.mtg.user_class.afrom_session(token = oauth_token, provider = provider, manager = self.mtg, request = request)


    async def authenticate_from_state(
        self,
        request: Request,
        optional: Optional[bool] = None,
        **kwargs,
    ) -> Tuple['OAuth2Token', 'OAuth2User']:
        """
        Handles the State Authentication
        """
        token, user, apikey = self.mtg.fetch_auth_from_state(request)
        if token is None or user is None: return self._not_authenticated(request)
        token._refresh_state()
        provider = self.mtg.get_oauth_provider(token.provider)
        user._refresh_from_state(provider, self.mtg, token = token, apikey = apikey)
        return (token, user)
    
    async def authenticate_from_auth_handlers(
        self,
        request: 'Request',
        optional: bool = False,
        **kwargs,
    ) -> Tuple[bool, Optional[Tuple['OAuth2Token', 'OAuth2User']]]:
        """
        Handles the Authentication from Handlers
        """
        valid, auth = False, None
        for handler in self.mtg.custom_auth_handlers:
            valid, set_state, should_continue, auth = await self.pool.asyncish(handler, request = request, optional = optional, **kwargs)
            if valid:
                if set_state: return valid, await self.state_handler(request, auth = auth)
                return valid, auth
            if not should_continue: return valid, auth
        return valid, auth
        
        
    async def authenticate(
        self, 
        request: 'Request'
    ) -> Optional[Tuple["OAuth2Token", "OAuth2User"]]:
        """
        The authenticate method
        """
        # If the state is present, we'll validate it first.
        # If a token is present, we always validate it first.
        # If no token is present, we check if there is a session.
        optional = self.is_optional_path(request)
        if self.mtg.custom_auth_handlers:
            valid, auth = await self.authenticate_from_auth_handlers(request = request, optional = optional)
            if valid: return auth
        
        if request.state and self.mtg.session_state_kw_check in request.state._state:
            return await self.authenticate_from_state(request = request, optional = optional)

        if token := self.get_jwt_token_from_request(request):
            auth = await self.authenticate_oauth2_token(request = request, token = token, optional = optional)
            return await self.state_handler(request, auth = auth)
        
        if self.config.api_keys_enabled and (api_key := self.get_api_key_from_request(request)):
            auth = await self.authenticate_api_key(request = request, api_key = api_key, optional = optional)
            return await self.state_handler(request, auth = auth)
        
        if self.mtg.session_oauth2_key in request.session:
            auth = await self.authenticate_from_session(request = request, optional = optional)
            return await self.state_handler(request, auth = auth)

        if optional: return self._not_authenticated(request)
        raise errors.InvalidAuthorizationError('No Token or API Key was provided')
    
