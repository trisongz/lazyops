from __future__ import annotations

"""
App Oauth Client
"""
import json
import contextlib
from abc import ABC
from urllib.parse import urljoin
from lazyops.libs import lazyload
from fastapi import Request
from fastapi.background import BackgroundTasks
from ..utils.lazy import get_az_settings, get_az_mtg_api, get_az_resource_schema, logger
from ..utils.helpers import get_hashed_key, create_code_challenge, parse_scopes, encode_params_to_url


from typing import Optional, List, Dict, Any, Union, Type, Tuple

if lazyload.TYPE_CHECKING:
    import niquests
    from fastapi import FastAPI
    from fastapi.background import BackgroundTasks
    from starlette.datastructures import URLPath
    from ..configs import AuthZeroSettings
    from ..flows.admin import AZManagementAPI
    from ..types.clients import AuthZeroClientObject
    from ..types.current_user import CurrentUser
    
else:
    niquests = lazyload.LazyLoad("niquests")


class AuthZeroOAuthClient(ABC):
    """
    The Auth Zero OAuth Client
    """

    _settings: Optional['AuthZeroSettings'] = None
    _mtg_api: Optional['AZManagementAPI'] = None

    def __init__(
        self,
        app: 'FastAPI',
        client_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        app_ingress: Optional[str] = None,
        callback_path: Optional[str] = '/auth/callback',
        logout_path: Optional[str] = None,
        include_wildcard_origin: Optional[bool] = True,
        user_class: Optional[Type['CurrentUser']] = None,
        **kwargs,
    ):
        """
        Initializes the Auth Zero OAuth Client
        """
        self.app = app
        self.client_id = client_id or self.settings.app_client_id or self.settings.client_id
        if app_ingress: self.settings.configure(app_ingress = app_ingress)
        self.secret_key = secret_key or get_hashed_key(self.settings.app_domain + self.settings.client_id)[:64]
        self.code_challenge = create_code_challenge(self.secret_key)
        self.callback_path = callback_path
        self.logout_path = logout_path
        self.include_wildcard_origin = include_wildcard_origin
        self.redirect_uri = urljoin(self.settings.app_ingress, self.callback_path)
        self.user_class = user_class or get_az_resource_schema('current_user')

        # Extra Properties
        self.docs_schema_index: Dict[str, str] = {}
        self.source_openapi_schema: Dict[str, Any] = None


    """
    Primary Methods
    """

    async def authorize_app_in_authzero(
        self,
        ingress_url: Optional[str] = None,
        include_wildcard_origin: Optional[bool] = None,
        verbose: Optional[bool] = True,
        **kwargs,
    ) -> 'AuthZeroClientObject':  # sourcery skip: low-code-quality
        """
        Authorizes the app in Auth0

        - Ensures that the app's ingress, callback path, and logout path are configured
        """
        az_client = await self.mtg_api.aget_az_client(self.client_id)
        source_counts = az_client.get_app_update_counts()

        if ingress_url is None: ingress_url = self.settings.app_ingress
        if include_wildcard_origin is None: include_wildcard_origin = self.include_wildcard_origin
        if include_wildcard_origin: include_wildcard_origin = ('localhost' not in ingress_url and '0.0.0' not in ingress_url)
        if include_wildcard_origin:
            wildcard_origin = ingress_url.replace('://', '://*.', 1)
            az_client.add_app_url(allowed_origin=wildcard_origin, verbose=verbose)

        elif 'localhost' not in ingress_url:
            az_client.add_app_url(allowed_origin=ingress_url, verbose=verbose)
        
        callback_url = (
            self.callback_path
            if self.callback_path.startswith('http')
            else urljoin(ingress_url, self.callback_path)
        )
        
        logout_url = (
            self.logout_path
            if self.logout_path.startswith('http')
            else urljoin(ingress_url, self.logout_path)
        ) if self.logout_path else ingress_url
        
        az_client.add_app_url(callback = callback_url, allowed_logout_url = logout_url, web_origin = ingress_url, verbose = verbose)
        
        if not az_client._needs_update:
            if verbose: logger.info(f'Client: `{az_client.name}` is already authorized with `{ingress_url}`', colored = True, prefix = f'|g|{az_client.client_id}|e|')
            return az_client

        response = await self.mtg_api.ahpatch(f'clients/{az_client.client_id}', json = az_client.get_app_patch_data())
        if response.status_code > 299:
            logger.warning(f'[{response.status_code}] Error updating app: {response.text} for {az_client.client_id}')
            return az_client
        
        resp = response.json()
        if verbose: 
            logger.info(f'Updated Client: `{az_client.name}`\n\n{resp}', colored = True, prefix = f'|g|{az_client.client_id}|e|')
            new_counts = az_client.get_app_update_counts()
            for key, value in new_counts.items():
                if value > source_counts[key]:
                    logger.info(f'{key}: {value} -> {source_counts[key]} (+{value - source_counts[key]})', colored = True, prefix = f'|g|{az_client.client_id}|e|')
    
        return az_client
            
    
    def get_authorization_redirect_url(
        self,
        scope: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        audience: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Returns the Authorization Redirect URL
        """
        scopes = parse_scopes(scope = scope, scopes = scopes)
        assert scopes, 'At least one scope must be provided'
        scope = ' '.join(scopes)
        if audience is None: audience = self.settings.audience
        assert audience, 'Audience must be provided'
        params = {
            'response_type': 'code',
            'code_challenge': self.code_challenge,
            'code_challenge_method': 'S256',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': scope,
            'audience': audience
        }
        if kwargs: 
            for k, v in kwargs.items():
                if k in params and v: params[k] = v
        return encode_params_to_url(params, self.authorize_url)
    

    async def authorize_app_user(
        self,
        request: 'Request',
        code: str,
        scope: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        background_tasks: Optional['BackgroundTasks'] = None,
        user_class: Optional[Type[CurrentUser]] = None,
        **kwargs,
    ) -> 'CurrentUser':
        """
        Authorizes the App User
        """
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'code_verifier': self.secret_key,
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        response = await self.mtg_api.ahpost(self.settings.oauth_url, data = data)
        try:
            response.raise_for_status()
        except Exception as e:
            logger.error(f'Error Authorizing User: {e}')
            from ..types.errors import AuthorizationException
            raise AuthorizationException(detail = response.text, status_code = response.status_code) from e
        
        user_data = response.json()
        if user_class is None: user_class = self.user_class
        current_user = user_class()
        try:
            await current_user.from_access_token(
                access_token = user_data['access_token'],
                request = request,
                scope = scope,
                scopes = scopes,
                background_tasks = background_tasks,
                **kwargs,
            )
        except Exception as e:
            logger.error(f'Error Authorizing User: {e}')
            raise e
        
        return current_user
    
    """
    Helper Methods
    """

    def get_app_redirection(
        self,
        redirect: str
    ) -> Union[str, 'URLPath']:
        """
        Gets the app redirection
        """
        if redirect.startswith('http'): return redirect
        if 'docs=' in redirect:
            base_url = str(self.app.url_path_for('docs').make_absolute_url(self.app_ingress)) + '#/operations'
            redirect = redirect.replace('docs=', '')
            if redirect in self.docs_schema_index:
                return f'{base_url}/{self.docs_schema_index[redirect]}'
        return self.app.url_path_for(redirect).make_absolute_url(self.app_ingress)


    def create_docs_index(self, schema: Dict[str, Any]):
        """
        Creates the docs index
        """
        for path in schema.get('paths', {}):
            for method in schema['paths'][path]:
                if 'operationId' in schema['paths'][path][method]:
                    doc_name = schema['paths'][path][method]['summary'].replace(' ', '').lower()
                    self.docs_schema_index[doc_name] = schema['paths'][path][method]['operationId']


    def create_openapi_source_spec(self, spec: Dict[str, Any], spec_map: Optional[Dict[str, Union[str, Tuple[str, int]]]] = None,):
        """
        Creates the Source Spec

        - Handles some custom logic for the OpenAPI Spec
            Namely:
            - AppResponse-Input -> AppResponse
            - AppResponse-Output -> AppResponse
        """
        if not spec_map: return
        _spec = json.dumps(spec)
        for key, value in spec_map.items():
            if isinstance(value, tuple):
                _spec = _spec.replace(key, value[0], value[1])
            else:
                _spec = _spec.replace(key, value)
        self.source_openapi_schema = json.loads(_spec)


    def mount_oauth_components(
        self, 
        login_path: Optional[str] = '/login',
        logout_path: Optional[str] = '/logout',

        server_identity: Optional[str] = None,
        server_identity_path: Optional[str] = '/_identity',

        enable_authorize: Optional[bool] = True,
        authorize_path: Optional[str] = '/authorize',

        enable_whoami: Optional[bool] = None,

        include_in_schema: Optional[bool] = None,
        user_class: Optional[Type['CurrentUser']] = None,
    ):
        """
        Mounts the OAuth Components
        """
        from fastapi import APIRouter, Depends, Query
        from fastapi.responses import RedirectResponse, JSONResponse, PlainTextResponse
        from .dependencies import get_current_user, CurrentUser as _CurrentUser

        router = APIRouter()

        @router.get(login_path, include_in_schema = include_in_schema)
        async def login(
            current_user: Optional[CurrentUser] = Depends(get_current_user(required = False, user_class = user_class)),
            redirect: Optional[str] = Query(None, description="The redirect page to use after login"),
        ):
            """
            Login Endpoint
            """
            if current_user is not None and current_user.is_valid:
                if redirect is not None: return RedirectResponse(self.get_app_redirection(redirect))
                return {'login': 'success', 'x-api-key': current_user.api_key}
            
            redirect_url = self.get_authorization_redirect_url(
                audience = self.settings.audience,
                scopes = self.settings.app_scopes,
            )
            response = RedirectResponse(redirect_url)
            if redirect: response.set_cookie(
                key = 'x-auth-redirect', value = redirect, max_age = 60, httponly = True,
            )
            return response
        
        @router.get(self.callback_path, include_in_schema = include_in_schema)
        async def auth_callback(
            request: Request,
            code: Optional[str] = Query(None),
            background_tasks: BackgroundTasks = BackgroundTasks,
        ):
            """
            Callback Endpoint
            """
            current_user = await self.authorize_app_user(
                request = request,
                code = code,
                scopes = self.settings.app_scopes,
                background_tasks = background_tasks,
            )
            if self.settings.is_development_env:
                logger.info(f'User {current_user.user_id} logged in')

            if redir_value := request.cookies.get('x-auth-redirect'):
                redirect = self.get_app_redirection(redir_value)
                if self.settings.is_development_env:
                    logger.info(f'Found redirect cookie: {redir_value} - Redirecting to {redirect}')
                response = RedirectResponse(redirect)
                response.delete_cookie('x-auth-redirect')
            else:
                response = JSONResponse({'login': 'success', 'x-api-key': current_user.api_key})
            response.set_cookie(**current_user.get_session_cookie_kwargs())
            return response

        @router.get(logout_path, include_in_schema = include_in_schema)
        async def logout(
            current_user: Optional[_CurrentUser] = Depends(get_current_user(required = False, user_class = user_class)),
        ):
            """
            Logout Endpoint
            """
            if current_user is None: return {'logout': 'no_user_found'}
            response = JSONResponse({'logout': 'success'})
            response.delete_cookie(**current_user.get_session_cookie_kwargs(is_delete = True))
            return response
        
        @router.get(self.callback_path, include_in_schema = include_in_schema)
        async def get_api_key(
            current_user: Optional[_CurrentUser] = Depends(get_current_user(required = False, user_class = user_class)),
            plaintext: Optional[bool] = Query(None, description="If True, will return the api key in plaintext"),
        ):
            """
            Get the API Key
            """
            if current_user is None or not current_user.is_valid: 
                return 'null' if plaintext else {'api_key': 'no_user_found'}
            response = PlainTextResponse(content = current_user.api_key) if plaintext else JSONResponse(content = {'api_key': current_user.api_key})
            response.set_cookie(**current_user.get_session_cookie_kwargs())
            return response
        
        if server_identity:
            @router.get(server_identity_path, include_in_schema = include_in_schema)
            async def get_server_identity(
                request: Request,
            ):
                """
                Get the Server Identity
                """
                return PlainTextResponse(content = server_identity)
        
        if enable_authorize:
            @router.get(authorize_path, include_in_schema = include_in_schema)
            async def authorize_user(
                current_user: _CurrentUser = Depends(get_current_user(user_class = user_class)),
            ):
                """
                Authorize the User or Client API by configuring the Cookies
                """
                if not current_user.is_valid: return {'authorize': 'invalid_user'}
                response = JSONResponse(content = {'authorized': True, 'identity': server_identity or self.settings.app_name, 'environment': self.settings.app_env.value, 'api-key': current_user.api_key})
                response.set_cookie(**current_user.get_session_cookie_kwargs())
                return response

        if enable_whoami or self.settings.is_local_env:
            @router.get('/whoami')
            async def get_whoami_for_user(
                current_user: Optional[_CurrentUser] = Depends(get_current_user(required = False, user_class = user_class)),
                pretty: Optional[bool] = Query(None, description="If True, will return the user in a pretty format"),
            ):
                """
                Get the Whoami Data for the User
                """
                if current_user is None: return {'whoami': 'no_user_found'}
                data = current_user.get_whoami_data()
                if pretty: 
                    import yaml
                    data = yaml.dump(data, default_flow_style = False, indent = 2)
                    return PlainTextResponse(content = data)
                return data

        self.app.include_router(router, tags = ['oauth'])
        

        # @contextlib.asynccontextmanager
        # async def oauth_lifespan(app: 'APIRouter'):


        # @router.on_event("")


    """
    Properties
    """

    @property
    def settings(self) -> 'AuthZeroSettings':
        """
        Returns the settings
        """
        if self._settings is None: self._settings = get_az_settings()
        return self._settings

    @property
    def mtg_api(self) -> 'AZManagementAPI':
        """
        Returns the AZ Management API
        """
        if self._mtg_api is None: self._mtg_api = get_az_mtg_api()
        return self._mtg_api
    
    @property
    def app_ingress(self) -> str:
        """
        Returns the App Ingress
        """
        return self.settings.app_ingress
    
    @property
    def authorize_url(self) -> str:
        """
        Returns the Authorize URL
        """
        return self.settings.authorize_url
