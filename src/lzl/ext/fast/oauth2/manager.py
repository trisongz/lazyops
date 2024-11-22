from __future__ import annotations

"""
FastAPI Extensions: OAuth2 Manager
"""

import abc
from lzl.types import eproperty
from lzl.logging import logger, null_logger, Logger
from lzl import load
from lzo.utils.helpers.base import create_unique_secret_key
from starlette.authentication import AuthenticationError
from lzl.ext.fast.types.security import Authorization, APIKey, AuthzKey
from urllib.parse import urljoin
from .types import errors
from .types.user import AuthMethod
# from .types.security import HTTPBase, HTTPAuthorizationCredentials, Authorization
from typing import Optional, Dict, Any, List, Set, Union, Type, Tuple, Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from .config import OAuth2Config
    from .providers import ProviderClientT
    from .types import Request
    from .types.user import OAuth2User, UnauthenticatedUser, APIKeyUser
    from .types.token import OAuth2Token
    from .types.security import HTTPBase, HTTPAuthorizationCredentials
    from .middleware import OAuth2Middleware
    from .backend import OAuth2Backend
    from starlette.types import Scope
else:
    from fastapi import Request

if load.TYPE_CHECKING:
    import jwt
else:
    jwt = load.LazyLoad("jwt", install_missing=True, install_options={'package': 'pyjwt'})

_DefaultRoutes: Dict[str, Any] = {
    'login': '/login',
    'start': '/start',
    'callback': '/callback',
    'logout': '/logout',
    'apikey': '/apikey',
    'validate': '/auth/validate',
    'user_info': '/userinfo',
    'default_redirect': '/docs',
}

class OAuth2Manager(abc.ABC):
    """
    The OAuth2 Manager
    """
    _extra: Dict[str, Any] = {}

    def __init__(
        self,
        config: 'OAuth2Config',
        **kwargs,
    ) -> None:
        """
        Initializes the OAuth2 Manager
        """
        self.config = config
        self.providers: Dict[str, 'ProviderClientT'] = {}
        self.jwt_issuers: Dict[str, str] = {} # A proxy for jwt_issuer_url and provider name
        self.default_provider: Optional[str] = None
        self.routes: Dict[str, Any] = _DefaultRoutes.copy()
        self.custom_auth_handlers: List[Callable[..., Awaitable[Tuple[bool, bool, bool, Tuple[Any, Any, Any]]]]] = []
        self.custom_middleware_handlers: List[Callable[..., Awaitable['Scope']]] = []
        self.optional_paths: Set[str] = {
            path for route, path in self.routes.items() if route != 'user_info'
        }
        self.excluded_paths: Set[str] = set()
        self.post_init(**kwargs)
    
    def post_init(self, **kwargs):
        """
        Post Init
        """
        pass

    def add_optional_path(self, path: Union[str, List[str]]):
        """
        Adds an optional path
        """
        if isinstance(path, str): path = [path]
        self.optional_paths.update(path)

    def add_excluded_path(self, path: Union[str, List[str]]):
        """
        Adds an excluded path
        """
        if isinstance(path, str): path = [path]
        self.excluded_paths.update(path)
        if self.oauth2_middleware is not None:
            self.oauth2_middleware.excluded_url_paths.update(path)

    def optional(self, path: str) -> str:
        """
        Adds an optional path
        """    
        self.add_optional_path(path)
        return path

    def exclude(self, path: str) -> str:
        """
        Adds an excluded path
        """    
        self.add_excluded_path(path)
        return path
    
    def add_auth_handler(self, handler: Callable[..., Awaitable[Tuple[bool, bool, bool, Tuple[Any, Any, Any]]]]):
        """
        Adds an auth handler

        The handler should be a function that takes the following arguments:
        - request: The request object
        - optional: Whether the auth is optional
        - kwargs: Any additional kwargs

        It should return a tuple of tuple (valid, set_state, should_continue, ((token, user, apikey) or None))
        """
        self.custom_auth_handlers.append(handler)

    def add_middleware_handler(self, handler: Callable[..., Awaitable['Scope']]):
        """
        Adds a middleware handler
        """
        self.custom_middleware_handlers.append(handler)
    
    @property
    def user_class(self) -> Type['OAuth2User']:
        """
        Returns the User Class
        """
        if 'user_class' not in self._extra:
            from .types.user import OAuth2User
            self._extra['user_class'] = OAuth2User
        return self._extra['user_class']
    
    @user_class.setter
    def user_class(self, value: Union[Type['OAuth2User'], str]) -> None:
        """
        Sets the User Class
        """
        if isinstance(value, str): value = load.lazy_import(value)
        self._extra['user_class'] = value

    @property
    def unauth_user_class(self) -> Type['UnauthenticatedUser']:
        """
        Returns the Unauthenticated User Class
        """
        if 'unauth_user_class' not in self._extra:
            from .types.user import UnauthenticatedUser
            self._extra['unauth_user_class'] = UnauthenticatedUser
        return self._extra['unauth_user_class']
    
    @unauth_user_class.setter
    def unauth_user_class(self, value: Union[Type['UnauthenticatedUser'], str]) -> None:
        """
        Sets the Unauthenticated User Class
        """
        if isinstance(value, str): value = load.lazy_import(value)
        self._extra['unauth_user_class'] = value

    @property
    def provider_pattern(self) -> str:
        """
        Returns the provider pattern

        '^(google|kinde|auth0)$'
        """
        # base_pattern = '|'.join(list(self.providers.keys()))
        # logger.info(f'Provider Pattern: {base_pattern}')
        # return f'^({base_pattern})$'
        if 'provider_pattern' not in self._extra:
            base_pattern = '|'.join(list(self.providers.keys()))
            self._extra['provider_pattern'] = f'^({base_pattern})$'
        return self._extra['provider_pattern']

    @property
    def app(self) -> 'FastAPI':
        """
        Returns the app
        """
        return self.config.app
    
    @eproperty
    def oauth2_middleware(self) -> 'OAuth2Middleware':
        """
        Returns the OAuth2 Middleware
        """
        return self._extra.get('oauth2_middleware')
    
    @eproperty
    def oauth2_backend(self) -> 'OAuth2Backend':
        """
        Returns the OAuth2 Backend
        """
        return self._extra.get('oauth2_backend')
    
    @property
    def state_kw_map(self) -> Dict[str, str]:
        """
        Returns the state keyword map
        """
        return self.config.session_state_kws
    
    @eproperty
    def session_state_kw_check(self) -> str:
        """
        Returns the first key in the state keyword map to validate
        whether there is a state present in the session
        """
        return list(self.config.session_state_kws.values())[0]
    
    def fetch_auth_from_state(self, request: 'Request') -> Tuple['OAuth2Token', 'OAuth2User', Optional[str]]:
        """
        Fetches the auth from the state
        """
        token = request.state._state.get(self.state_kw_map['token'])
        user = request.state._state.get(self.state_kw_map['user'])
        apikey = request.state._state.get(self.state_kw_map['apikey'])
        return (token, user, apikey)
    
    @eproperty
    def session_oauth2_key(self) -> str:
        """
        Returns the session oauth2 key
        """
        return self.config.session_oauth2_key
    
    @property
    def domains(self) -> List[str]:
        """
        Returns the domains
        """
        return self.config.domains
    
    @property
    def disabled_paths(self) -> List[str]:
        """
        Returns the disabled paths
        """
        return self.config.disabled_paths
    
    @property
    def api_key_users(self) -> Dict[str, 'APIKeyUser']:
        """
        Returns the API Key Users
        """
        return self.config.api_key_users
    
    @property
    def autologger(self) -> 'Logger':
        """
        Returns the autologger
        """
        return logger if self.config.debug_enabled else null_logger

    def update_routes(self, routes: Dict[str, Union[str, Dict[str, Any]]]) -> None:
        """
        Updates the routes
        """
        for name, route in routes.items():
            if isinstance(route, str): self.routes[name] = route
            elif isinstance(route, dict): 
                if route.get('disabled') is True: 
                    if name in self.routes: del self.routes[name]
                    continue
                self.routes[name] = route.get('path', name)

    def load_providers(
        self, 
        providers: List[Dict[str, Any]], 
    ) -> None:
        """
        Loads the providers
        """
        from .providers import get_provider_classes
        for config in providers:
            provider = config['name']
            enabled = config.pop('enabled', True)
            if not enabled: continue
            is_default = config.pop('default', False)
            _config_cls, _client_cls = get_provider_classes(
                provider,
                config_class = config.pop('config_class', None),
                client_class = config.pop('client_class', None),
            )
            _config = _config_cls(**config)
            self.providers[provider] = _client_cls(
                manager = self,
                config = _config,
            )
            if _config.jwt_issuer_url: self.jwt_issuers[_config.jwt_issuer_url] = provider
            if is_default: self.default_provider = provider
        if not self.default_provider: self.default_provider = list(self.providers.keys())[0]
        if not self.config.temp_data.has_logged('providers_loaded'):
            logger.info(f'Loaded |g|{len(self.providers)}|e| OAuth2 Providers: |y|{list(self.providers.keys())}|e| - Default Provider: |g|{self.default_provider}|e|', colored = True)

    def get_oauth_provider(self, provider: str, raise_errors: Optional[bool] = True) -> 'ProviderClientT':
        """
        Returns the OAuth2 provider
        """
        if provider not in self.providers:
            if raise_errors: raise errors.InvalidProviderError(detail=f'Invalid Provider: {provider}')
            return None
        return self.providers[provider]


    # def get_auth_method_from_request(self, request: 'Request') -> Optional[AuthMethod]:

    async def get_provider_for_jwt(
        self,
        token: str,
        request: 'Request',
    ) -> 'ProviderClientT':
        """
        Resolves the provider for the jwt
        """
        # Special Case for Google
        if token.startswith('ya29.') and 'google' in self.providers:
            return self.providers['google']
        decoded: Dict[str, Union[str, List[str]]] = jwt.decode(
            token,
            algorithms = ['RS256'],
            options={'verify_signature': False}
        )
        if decoded.get('iss') not in self.jwt_issuers:
            raise errors.InvalidProviderError(provider = decoded.get('iss'))
        return self.providers[self.jwt_issuers[decoded.get('iss')]]
    
    def decrypt_api_key(self, key: str) -> Dict[str, Any]:
        """
        Decrypts the API Key
        """
        return self.config.decrypt_api_key_data(key)
    
    def encrypt_api_key(self, data: Dict[str, Any]) -> str:
        """
        Encrypts the API Key
        """
        return self.config.encrypt_api_key_data(data)


    """
    FastAPI Handler Methods
    """


    """
    FastAPI Routes
    """

    def fetch_app_endpoint_from_request(self, request: Request) -> str:
        """
        Fetches the app endpoint from the request
        """
        if request.session.get('app_endpoint'):
            return request.session['app_endpoint']
        headers = dict(request.headers.items())
        if headers.get(':authority:'):
            return headers[':scheme:'] + '://' + headers[':authority:']
        if headers.get('x-forwarded-host'):
            if headers.get('x-forwaded-scheme'):
                return headers['x-forwaded-scheme'] + '://' + headers['x-forwarded-host']
            if self.config.in_k8s:
                return 'https://' + headers['x-forwarded-host']
            forwaded_port = headers['x-forwarded-port']
            if '443' in forwaded_port: return 'https://' + headers['x-forwarded-host']
            return 'http://' + headers['x-forwarded-host']
        if headers.get('host'):
            scheme = 'https' if self.config.in_k8s else 'http'
            return f'{scheme}://' + headers['host']
        raise ValueError('Unable to determine app endpoint')


    def mount_components(
        self,
        app: Optional['FastAPI'] = None,
        include_in_schema: Optional[bool] = None,
        disable_middleware: Optional[bool] = None,
        disable_session: Optional[bool] = None,
        disable_routes: Optional[bool] = None,
        **kwargs,
    ):
        """
        Mounts all the components
        """
        if app is not None: self.config.app = app
        elif self.config.app is not None: app = self.config.app
        else: raise ValueError('app must be provided')

        # add the middlewares
        if not disable_middleware:
            # logger.info(f'Adding OAuth2 Middleware: {self.config.middleware_class}')
            app.add_middleware(
                self.config.middleware_class,
                config = self.config,
                backend_class = self.config.backend_class,
            )

        disable_session = disable_session or self.config.session_disabled
        if not disable_session:
            # logger.info(f'Adding OAuth2 Session Middleware: {self.config}')
            state_kws = list(self.config.session_state_kws.values())
            app.add_middleware(
                self.config.session_class,
                config = self.config,
                oauth2_enabled = True,
                state_kws = state_kws,
                **self.config.session_config,
            )
        
        if not disable_routes:
            self.mount_oauth_routes(
                app = app,
                include_in_schema = include_in_schema,
                **kwargs,
            )


    def mount_oauth_routes(
        self,
        app: 'FastAPI',
        include_in_schema: Optional[bool] = None,
        **kwargs,
    ):
        """
        Mounts the OAuth2 Routes
        """
        from fastapi import APIRouter,  Path, Query
        from fastapi.responses import RedirectResponse
        from lzl.ext.fast.types.responses import PrettyJSONResponse
        router = APIRouter(
            include_in_schema = include_in_schema, 
            default_response_class = PrettyJSONResponse
        )

        if 'login' in self.routes:
            if self.config.api_keys_enabled:
                @router.get(self.routes['login'])
                async def login(
                    request: Request,
                    auth: Authorization,
                    apikey: APIKey,
                    authzkey: AuthzKey,
                    redirect: str = Query(None, description='Redirect URL'),
                ):
                    """
                    Login Endpoint
                    """
                    headers = {}
                    if request.user.is_authenticated: 
                        headers[self.config.header] = f'{self.config.scheme} {request.auth.value}'
                        if redirect: return RedirectResponse(url = redirect, headers = headers)
                        if redirect := request.session.pop('oauth2_redirect', None):
                            return RedirectResponse(url = redirect, headers = headers)
                        if self.routes.get('default_redirect'):
                            return RedirectResponse(url = self.routes['default_redirect'], headers = headers)
                        return {'login': 'success'}
                    provider_url = self.routes['start'] + "/" + self.default_provider
                    return RedirectResponse(url = provider_url)

            else:
                @router.get(self.routes['login'])
                async def login(
                    request: Request,
                    auth: Authorization,
                    redirect: str = Query(None, description='Redirect URL'),
                ):
                    """
                    Login Endpoint
                    """
                    headers = {}
                    if request.user.is_authenticated: 
                        headers[self.config.header] = f'{self.config.scheme} {request.auth.value}'
                        if redirect: return RedirectResponse(url = redirect, headers = headers)
                        if redirect := request.session.pop('oauth2_redirect', None):
                            return RedirectResponse(url = redirect, headers = headers)
                        if self.routes.get('default_redirect'):
                            return RedirectResponse(url = self.routes['default_redirect'], headers = headers)
                        return {'login': 'success'}
                    provider_url = self.routes['start'] + "/" + self.default_provider
                    return RedirectResponse(url = provider_url)

        if 'start' in self.routes:
            @router.get(self.routes['start'] + "/{provider}")
            async def start_with_provider(
                request: Request,
                provider: str = Path(..., description='OAuth2 Provider', pattern = self.provider_pattern),
                redirect: str = Query(None, description='Redirect URL'),
                scope: str = Query(None, description='Scope'),
            ):
                """
                Authorize Endpoint with an OAuth2 Provider
                """
                if redirect: request.session['oauth2_redirect'] = redirect
                state_id = create_unique_secret_key()
                request.session['state_id'] = state_id
                client = self.get_oauth_provider(provider)
                provider_cb_path = self.routes['callback'] + "/" + provider
                provider_redirect_url = urljoin(self.fetch_app_endpoint_from_request(request), provider_cb_path)
                auth_redirect_url = client.get_auth_url(
                    redirect_url = provider_redirect_url,
                    scope = scope,
                    state = state_id,
                )
                return RedirectResponse(auth_redirect_url)
        
        if 'callback' in self.routes:
            @router.get(self.routes['callback'] + "/{provider}")
            async def callback_with_provider(
                request: Request,
                provider: str = Path(..., description='OAuth2 Provider', pattern = self.provider_pattern),
                code: str = Query(..., description='Authorization Code'),
                state: str = Query(None, description='State'),
            ):
                """
                The Provider Callback Endpoint
                """
                client = self.get_oauth_provider(provider)
                provider_cb_path = self.routes['callback'] + "/" + provider
                provider_redirect_url = urljoin(self.fetch_app_endpoint_from_request(request), provider_cb_path)
                try:
                    token = await client.afetch_token(
                        code = code,
                        redirect_url = provider_redirect_url,
                        request = request,
                    )
                except Exception as e:
                    logger.error(f'Error fetching token: {e}')
                    raise errors.InvalidAuthorizationError(error = e) from e
                self.autologger.info(f'Fetched Token: |g|{token}|e|', colored = True, prefix = provider)
                oauth_token = await client.aparse_token_from_callback(token)
                self.autologger.info(f'Fetched Token: |g|{oauth_token}|e|', colored = True, prefix = provider)
                request.session[self.session_oauth2_key] = {
                    'provider': provider,
                    'identity': oauth_token.identity,
                }
                redirect = request.session.get('oauth2_redirect')
                if not redirect and self.routes.get('default_redirect'): redirect = self.routes['default_redirect']
                headers = {
                    self.config.header: f'{self.config.scheme} {oauth_token.value}'
                }
                if redirect: response = RedirectResponse(url = redirect, headers = headers)
                else: response = PrettyJSONResponse({'login': 'success'}, headers = headers)
                return response

        if 'logout' in self.routes:
            @router.get(self.routes['logout'])
            async def logout(
                request: Request,
                redirect: str = Query(None, description='Redirect URL'),
            ):
                """
                Logout Endpoint
                """
                if request.user.is_authenticated:
                    await request.user.alogout()
                if not redirect: redirect = request.session.get('oauth2_redirect')
                request.session.clear()
                request.state._state.clear()
                if redirect: return RedirectResponse(url = redirect)
                if self.routes.get('default_redirect'):
                    return RedirectResponse(url = self.routes['default_redirect'])
                return {'logout': 'success'}
        
        if 'user_info' in self.routes:
            if self.config.api_keys_enabled:
                @router.get(self.routes['user_info'])
                async def user_info(
                    request: Request,
                    auth: Authorization,
                    apikey: APIKey,
                    authzkey: AuthzKey,
                ):
                    """
                    User Info Endpoint
                    """
                    if not request.user.is_authenticated: return {'user_info': 'not_authenticated'}
                    return PrettyJSONResponse(
                        content = {
                            'authenticated': True,
                            **request.user.get_user_info()
                        }
                    )
            else:
                @router.get(self.routes['user_info'])
                async def user_info(
                    request: Request,
                    auth: Authorization,
                ):
                    """
                    User Info Endpoint
                    """
                    if not request.user.is_authenticated: return {'user_info': 'not_authenticated'}
                    return PrettyJSONResponse(
                        content = {
                            'authenticated': True,
                            **request.user.get_user_info()
                        }
                    )
        
        if 'apikey' in self.routes:
            @router.get(self.routes['apikey'], include_in_schema = include_in_schema)
            async def get_apikey(
                request: Request,
                redirect: str = Query(None, description='Redirect URL'),
            ):
                """
                API Key Endpoint
                """
                if not request.user.is_authenticated: 
                    raise errors.InvalidAuthorizationError('No Authorization')
                headers = {'x-authz-key': request.user.apikey}
                if redirect: return RedirectResponse(url = redirect, headers = headers)
                return PrettyJSONResponse(
                    content = {
                        'apikey': request.user.apikey,
                    },
                    headers = headers,
                )

        # Clean these up later
        if 'validate' in self.routes:
            if self.config.api_keys_enabled:
                @router.get(self.routes['validate'], include_in_schema = include_in_schema)
                async def validate_auth(
                    request: Request,
                    auth: Authorization,
                    apikey: APIKey,
                    authzkey: AuthzKey,
                    redirect: str = Query(None, description='Redirect URL'),
                ):
                    """
                    Validate Endpoint
                    """
                    if not request.user.is_authenticated: 
                        raise errors.InvalidAuthorizationError('No Authorization')
                    headers = {'x-authz-key': request.user.apikey}
                    if redirect: return RedirectResponse(url = redirect, headers = headers)
                    return PrettyJSONResponse(
                        content = {
                            'authenticated': True,
                        },
                        headers = headers,
                    )
            else:
                @router.get(self.routes['validate'], include_in_schema = include_in_schema)
                async def validate_auth(
                    request: Request,
                    auth: Authorization,
                    redirect: str = Query(None, description='Redirect URL'),
                ):
                    """
                    Validate Endpoint
                    """
                    if not request.user.is_authenticated: 
                        raise errors.InvalidAuthorizationError('No Authorization')
                    headers = {'x-authz-key': request.user.apikey}
                    if redirect: return RedirectResponse(url = redirect, headers = headers)
                    return PrettyJSONResponse(
                        content = {
                            'authenticated': True,
                        },
                        headers = headers,
                    )

        app.include_router(router, tags = ['OAuth2'])

    @classmethod
    def load(
        cls, 
        app: Optional['FastAPI'] = None, 
        config: Optional['OAuth2Config'] = None,
        **kwargs
    ) -> 'OAuth2Manager':
        """
        Loads the OAuth2 Manager
        """
        if config is None:
            from .config import OAuth2Config
            config = OAuth2Config(manager_class = cls)

        if app is not None: config.app = app
        if kwargs: config.update_config(**kwargs)
        return config.get_manager()
