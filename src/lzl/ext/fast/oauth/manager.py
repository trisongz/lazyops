from __future__ import annotations

"""
FastAPI Extensions: OAuth2 Manager
"""

import abc
from lzl.types import eproperty
from lzl.logging import logger
from lzl import load
from lzo.utils.helpers.base import create_unique_secret_key
from starlette.authentication import AuthenticationError
from lzl.ext.fast.types.security import Authorization
from urllib.parse import urljoin
from . import errors
# from .types.security import HTTPBase, HTTPAuthorizationCredentials, Authorization
from typing import Optional, Dict, Any, List, Union, Type, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from .config import OAuth2Settings
    from .providers import ProviderClientT
    from .types import Request
    from .types.user import OAuth2User
    from .types.token import OAuth2Token
    from .types.security import HTTPBase, HTTPAuthorizationCredentials
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
        settings: 'OAuth2Settings',
        **kwargs,
    ) -> None:
        """
        Initializes the OAuth2 Manager
        """
        self.settings = settings
        self.providers: Dict[str, 'ProviderClientT'] = {}
        self.jwt_issuers: Dict[str, str] = {} # A proxy for jwt_issuer_url and provider name
        self.default_provider: Optional[str] = None
        self.routes: Dict[str, Any] = _DefaultRoutes.copy()
    
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
    def token_class(self) -> Type['OAuth2Token']:
        """
        Returns the Token Class
        """
        if 'token_class' not in self._extra:
            from .types.token import OAuth2Token
            self._extra['token_class'] = OAuth2Token
        return self._extra['token_class']
    
    @token_class.setter
    def token_class(self, value: Union[Type['OAuth2Token'], str]) -> None:
        """
        Sets the Token Class
        """
        if isinstance(value, str): value = load.lazy_import(value)
        self._extra['token_class'] = value
        # TODO set the downstream classes


    @property
    def provider_pattern(self) -> str:
        """
        Returns the provider pattern

        '^(google|kinde|auth0)$'
        """
        if 'provider_pattern' not in self._extra:
            base_pattern = '|'.join(list(self.providers.keys()))
            self._extra['provider_pattern'] = f'^({base_pattern})$'
        return self._extra['provider_pattern']

    @property
    def app(self) -> 'FastAPI':
        """
        Returns the app
        """
        return self.settings.app
    
    def load_providers(
        self, 
        providers: List[Dict[str, Any]], 
        domains: Optional[List[str]] = None
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
            _config = _config_cls(domains = domains, **config)
            self.providers[provider] = _client_cls(
                config = _config,
            )
            if _config.jwt_issuer_url: self.jwt_issuers[_config.jwt_issuer_url] = provider
            if is_default: self.default_provider = provider
        if not self.default_provider: self.default_provider = list(self.providers.keys())[0]
        if not self.settings.temp_data.has_logged('providers_loaded'):
            logger.info(f'Loaded |g|{len(self.providers)}|e| OAuth2 Providers: |y|{list(self.providers.keys())}|e| - Default Provider: |g|{self.default_provider}|e|', colored = True)

    def get_oauth_provider(self, provider: str) -> 'ProviderClientT':
        """
        Returns the OAuth2 provider
        """
        if provider not in self.providers:
            raise errors.InvalidProviderError(detail=f'Invalid Provider: {provider}')
        return self.providers[provider]

    def get_jwt_token_from_request(self, request: 'Request') -> Optional[str]:
        """
        Gets the JWT Token from the Request
        """
        if not request.headers.get(self.settings.header): return None
        auth = request.headers.get(self.settings.header)
        scheme, token = auth.split(' ', 1)
        return None if scheme.lower() != self.settings.scheme.lower() else token

    async def get_provider_for_jwt(
        self,
        token: str,
        request: 'Request',
    ) -> 'ProviderClientT':
        """
        Resolves the provider for the jwt
        """
        decoded: Dict[str, Union[str, List[str]]] = jwt.decode(
            token,
            algorithms = ['RS256'],
            options={
                'verify_signature': False,
            }
        )
        if decoded.get('iss') not in self.jwt_issuers:
            raise AuthenticationError(detail=f'Invalid Provider: {decoded.get("iss")}')
        return self.providers[self.jwt_issuers[decoded.get('iss')]]
    

    def parse_token_payload(
        self,
        token: Dict[str, Any],
        provider: 'ProviderClientT',
    ) -> Optional['OAuth2Token']:
        """
        Parses the token payload
        """
        auth_token = self.token_class(**token, provider = provider.name)
        if auth_token.access_token:
            if decoded := provider.parse_jwt_token(auth_token.access_token, kind = 'access_token'):
                auth_token.set_access_token(decoded)
        if auth_token.id_token:
            if decoded := provider.parse_jwt_token(auth_token.id_token, kind = 'id_token'):
                auth_token.set_id_token(decoded)
        if auth_token.refresh_token and auth_token.identity:
            provider.refresh_data[auth_token.identity] = auth_token.refresh_token
        return auth_token
    
    async def arefresh_oauth_token(
        self,
        oauth_token: 'OAuth2Token',
        provider: 'ProviderClientT',
        refresh_token: Optional[str] = None,
        **kwargs,
    ) -> Optional['OAuth2Token']:
        """
        Refreshes the oauth token
        """
        if not refresh_token:
            refresh_token = oauth_token.refresh_token or \
                await provider.refresh_data.aget(oauth_token.identity)
        try:
            refreshed_token = await provider.arefresh_token(refresh_token = refresh_token, **kwargs)
            logger.info(f'Refreshed OAuth Token for |g|{oauth_token.identity}|e|', colored = True, prefix = provider.name)
        
        except Exception as e:
            logger.warning(f'Error refreshing token: {e} - Deleting {oauth_token.identity}', prefix = provider.name)
            await provider.data.adelete(oauth_token.identity)
            await provider.refresh_data.adelete(oauth_token.identity)
            return None
        
        refreshed_token = self.parse_token_payload(refreshed_token, provider)
        if not refreshed_token.refresh_token: refreshed_token.refresh_token = refresh_token
        await provider.data.aset(refreshed_token.identity, refreshed_token)
        return refreshed_token
    
    async def aretrieve_token_from_token_payload(
        self,
        token: str,
        token_payload: Dict[str, Any],
        provider: 'ProviderClientT',
        **kwargs,
    ) -> Optional['OAuth2Token']:
        """
        Retrieves the stored token from the token payload
        """
        if not token_payload.get('sub'): 
            logger.info(f'No Subject (sub) in Token: {token_payload}', colored = True, prefix = provider.name)
            raise errors.InvalidTokenError(detail = 'No Subject (sub) in Token')
        
        identity = token_payload.get('sub')
        if await provider.data.acontains(identity):
            # This is likely a token that was issued by this API
            stored_token = await provider.data.aget(identity)
            stored_token.merge(token_payload)
            return stored_token

        # This is likely a token that was issued by another API
        # and thus it isn't stored in the provider's data
        built_token_payload = await provider.abuild_oauth_token(token, token_payload)
        if built_token_payload is None: return None
        built_token = self.token_class(**built_token_payload)
        await provider.data.aset(identity, built_token)
        return built_token

    
    async def authenticate_oauth_token(
        self,
        token: str,
        request: 'Request',
        from_session: Optional[bool] = None,
    ) -> Tuple['OAuth2User', Optional['OAuth2Token']]:
        """
        Authenticates the OAuth2 Token
        """
        provider = await self.get_provider_for_jwt(token, request)
        token_payload = provider.parse_authorization_token(token, verify_exp = False)
        oauth_token = await self.aretrieve_token_from_token_payload(token, token_payload, provider = provider)
        if oauth_token is None:
            return None, self.user_class(None, None, self)
        if oauth_token.is_expired:
            logger.info(f'Refreshing Token: {oauth_token}')
            # Try to refresh the token
            refreshed_token = await self.arefresh_oauth_token(oauth_token, provider = provider)
            if refreshed_token is None: 
                # TODO: handle refresh failure
                if from_session: 
                    _ = request.session.pop('_oauth', None)
                    return None
                raise errors.InvalidSignatureError('Expired Token - Unable to Retrieve Refresh Token')
            oauth_token = refreshed_token
            request.session['_oauth'] = oauth_token.value
        return oauth_token, self.user_class(oauth_token, provider, self)

    

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
            if self.settings.in_k8s:
                return 'https://' + headers['x-forwarded-host']
            forwaded_port = headers['x-forwarded-port']
            if '443' in forwaded_port: return 'https://' + headers['x-forwarded-host']
            return 'http://' + headers['x-forwarded-host']
        if headers.get('host'):
            scheme = 'https' if self.settings.in_k8s else 'http'
            return f'{scheme}://' + headers['host']
        raise ValueError('Unable to determine app endpoint')

    def mount_oauth_routes(
        self,
        app: Optional['FastAPI'] = None,
        include_in_schema: Optional[bool] = None,
        **kwargs,
    ):
        """
        Mounts the OAuth2 Routes
        """
        if app is not None: self.settings.app = app
        elif self.settings.app is not None: app = self.settings.app
        else: raise ValueError('app must be provided')

        from fastapi import APIRouter,  Path, Query
        from fastapi.responses import RedirectResponse
        from lzl.ext.fast.types.responses import PrettyJSONResponse
        
        router = APIRouter(
            include_in_schema = include_in_schema, 
            default_response_class = PrettyJSONResponse
        )

        @router.get(self.routes['login'])
        async def login(
            request: Request,
            auth: Authorization,
            redirect: Optional[str] = Query(None, description='Redirect URL'),
        ):
            """
            Login Endpoint
            """
            headers = {}
            if request.user.is_authenticated: 
                headers[self.settings.header] = f'{self.settings.scheme} {request.auth.value}'
                if redirect: return RedirectResponse(url = redirect, headers = headers)
                if redirect := request.session.pop('oauth2_redirect', None):
                    return RedirectResponse(url = redirect, headers = headers)
                if self.routes.get('default_redirect'):
                    return RedirectResponse(url = self.routes['default_redirect'], headers = headers)
                return {'login': 'success'}
            provider_url = self.routes['start'] + "/" + self.default_provider
            return RedirectResponse(url = provider_url)


        @router.get(self.routes['start'] + "/{provider}")
        async def start_with_provider(
            request: Request,
            provider: str = Path(..., description='OAuth2 Provider', pattern = self.provider_pattern),
            redirect: Optional[str] = Query(None, description='Redirect URL'),
            scope: Optional[str] = Query(None, description='Scope'),
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
        
        @router.get(self.routes['callback'] + "/{provider}")
        async def callback_with_provider(
            request: Request,
            provider: str = Path(..., description='OAuth2 Provider', pattern = self.provider_pattern),
            code: str = Query(..., description='Authorization Code'),
            state: Optional[str] = Query(None, description='State'),
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
            logger.info(f'Fetched Token: |g|{token}|e|', colored = True, prefix = provider)
            oauth_token = self.parse_token_payload(token, client)
            logger.info(f'Fetched Token: |g|{oauth_token}|e|', colored = True, prefix = provider)
            await client.data.aset(oauth_token.identity, oauth_token)
            request.session['_oauth'] = oauth_token.value
            redirect = request.session.get('oauth2_redirect')
            if not redirect and self.routes.get('default_redirect'): redirect = self.routes['default_redirect']
            headers = {
                self.settings.header: f'{self.settings.scheme} {oauth_token.value}'
            }
            if redirect: response = RedirectResponse(url = redirect, headers = headers)
            else: response = PrettyJSONResponse({'login': 'success'}, headers = headers)
            return response


        @router.get(self.routes['logout'])
        async def logout(
            request: Request,
            redirect: Optional[str] = Query(None, description='Redirect URL'),
        ):
            """
            Logout Endpoint
            """
            if request.user.is_authenticated:
                await request.user.alogout()
            if not redirect: redirect = request.session.get('oauth2_redirect')
            request.session.clear()
            if redirect: return RedirectResponse(url = redirect)
            if self.routes.get('default_redirect'):
                return RedirectResponse(url = self.routes['default_redirect'])
            return {'logout': 'success'}
            
        @router.get(self.routes['user_info'])
        async def user_info(
            request: Request,
        ):
            """
            User Info Endpoint
            """
            if not request.user.is_authenticated: return {'user_info': 'not_authenticated'}
            return PrettyJSONResponse(
                content = {
                    'authenticated': True,
                    'authorization': request.auth.value,
                    'user': {
                        'id': request.user.identity,
                        'display_name': request.user.display_name,
                        'email': request.user.email,
                        'roles': request.auth.roles,
                        'scopes': request.auth.scopes,
                        'provider': request.auth.provider,
                    }
                }
            )


        app.include_router(router, tags = ['OAuth2'])

    @classmethod
    def load(
        cls, 
        app: Optional['FastAPI'] = None, 
        **kwargs
    ) -> 'OAuth2Manager':
        """
        Loads the OAuth2 Manager
        """
        from .config import OAuth2Settings
        settings = OAuth2Settings()
        if app is not None: settings.app = app
        if kwargs: settings.update_config(**kwargs)
        return cls(settings = settings)
