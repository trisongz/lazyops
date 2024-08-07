from __future__ import annotations

"""
Kinde Client Handler Wrapper
"""

import jwt
import json
from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from authlib.oauth2.rfc6749 import OAuth2Token
from authlib.integrations.base_client.errors import OAuthError
from .base import kinde_api_import_paths
from .handlers import BaseKindeHandler, KindeRouter
from .types.session import KindeSessionMiddleware
from .types.security import APIKey, Authorization
from .types.attributes import Organization, Role, Permission, JSONProperty, JSONOrgProperty, serializer
from .api import KindeApiClient
from lazyops.utils.lazy import lazy_import
from lazyops.utils.helpers import timed_cache
from lazyops.libs.abcs.types.roles import UserRole
from typing import Optional, List, Dict, Any, Callable, Union, Awaitable, overload, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.datastructures import URLPath
    from .config import KindeSettings


"""
TODO: 
- Add support for application client api-keys and authorization
"""

class KindeClient(BaseKindeHandler):
    """
    The Kinde Client
    """

    if TYPE_CHECKING:
        def __init__(
            self,
            settings: Optional['KindeSettings'] = None,
            app: Optional['FastAPI'] = None,
            **kwargs,
        ):
            ...

    def post_init(self, app: Optional['FastAPI'] = None, **kwargs):
        """
        Handles the post initialization
        """
        self.app = app
        self.app.add_middleware(KindeSessionMiddleware, client = self)

        self.router_handler = KindeRouter(settings = self.settings, client = self)
        self._roles: Dict[str, Dict[str, str]] = {}
        self._permissions: Dict[str, Dict[str, str]] = {}
    
        # Extra Properties
        self.docs_schema_index: Dict[str, str] = {}
        self.source_openapi_schema: Dict[str, Any] = None

    def create_api_client(
        self,
        request: Optional[Request] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> 'KindeApiClient':
        """
        Creates a Kinde Api Client
        """
        client = KindeApiClient(
            **self.settings.get_kinde_client_config(**kwargs),
        )
        client._app_api = self
        if request and request.session.get('user_id'):
            client.user_id = request.session['user_id']
        elif user_id: client.user_id = user_id
        return client
    
    """
    MTG API Methods
    """

    def fetch_roles(self):
        """
        Fetches the roles
        """
        if not self.settings.is_mtg_enabled: return
        response = self.role_api.get_roles(
            query_params={"page_size": 200},
            accept_content_types = ('application/json',),
        )
        if response.body and response.body.get('roles'):
            for role in response.body['roles']:
                self._roles[role['id']] = role
    
    @timed_cache(60 * 10, cache_if_type = list)
    def fetch_role_permissions(self, role_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetches the role permissions
        """
        if not self.settings.is_mtg_enabled: return []
        self.logger.info(f'Fetching Role Permissions for {role_id}')
        response = self.role_api.get_role_permission(
            query_params= { "page_size": 100},
            path_params = {"role_id": role_id},
            skip_deserialization=True,
            # accept_content_types = tuple(['application/json']),
            # accept_content_types = ('application/json'),
        )
        response_data: Dict[str, Union[str, List[Dict[str, str]]]] = serializer.loads(response.response.data.decode())
        # self.logger.info(response.response.data.decode())
        if response_data and response_data.get('permissions'):
            return response_data['permissions']
        return []

    def fetch_permissions(self):
        """
        Fetches the permissions
        """
        if not self.settings.is_mtg_enabled: return
        response = self.permission_api.get_permissions(
            query_params={"page_size": 200},
            accept_content_types = ('application/json',),
        )
        if response.body and response.body.get('permissions'):
            for permission in response.body['permissions']:
                self._permissions[permission['id']] = permission
    

    def fetch_refresh_claims_token(self, user_id: str) -> Optional[str]:
        """
        Fetches the refresh claims token
        """
        if not self.settings.is_mtg_enabled: return None
        response = self.user_api.refresh_user_claims(
            path_params={"user_id": user_id},
            accept_content_types = ('application/json',),
        )
        if response.body and response.body.get('code'):
            return response.body['code']
        return None

    def update_roles_with_permissions(
        self,
        roles: List['Role'],
    ) -> List['Role']:
        """
        Updates the roles with permissions
        """
        for role in roles:
            perms = self.fetch_role_permissions(role_id = role.id)
            perms = [Permission(**p) for p in perms]
            role.permissions = perms
        return roles


    """
    Management Properties
    """

    @property
    def roles(self) -> Dict[str, Dict[str, str]]:
        """
        Returns the roles
        """
        if not self.settings.is_mtg_enabled: return {}
        if not self._roles: self.fetch_roles()
        return self._roles
    
    @property
    def permissions(self) -> Dict[str, Dict[str, str]]:
        """
        Returns the permissions
        """
        if not self.settings.is_mtg_enabled: return {}
        if not self._permissions: self.fetch_permissions()
        return self._permissions


    """
    Application Methods
    """    

    async def authorize_application(
        self,
        app_endpoint: Optional[str] = None,
        verbose: Optional[bool] = True,
        **kwargs,
    ):
        """
        Authorizes the application
        
        We need to handle:
        - Callback URLs
        - Logout URLs
        """
        callback_urls, logout_urls = set(), set()

        if app_endpoint is None: app_endpoint = self.settings.app_endpoint
        elif app_endpoint != self.settings.app_endpoint: self.settings.app_endpoint = app_endpoint
        
        callback_urls.add(app_endpoint)
        callback_urls.add(self.settings.callback_url)
        logout_urls.add(self.settings.logout_url)
        logout_urls.add(self.settings.logout_redirect_url)

        # Fetch and retrieve existing callback urls
        response = self.callback_api.get_callback_urls(
            path_params={"app_id": self.settings.client_id}
        )
        existing_callback_urls = response.body['redirect_urls']
        for callback_url in existing_callback_urls:
            if callback_url in callback_urls: 
                callback_urls.remove(callback_url)
                continue
        
        # Fetch and retrieve existing logout urls
        response = self.callback_api.get_logout_urls(
            path_params={"app_id": self.settings.client_id}
        )
        # self.logger.info(response)
        existing_logout_urls = response.body['logout_urls']
        for logout_url in existing_logout_urls:
            if logout_url in logout_urls: 
                logout_urls.remove(logout_url)
                continue

        if callback_urls:
            if verbose: self.logger.info(f'Adding Callback Redirect URLs: {callback_urls}')
            self.callback_api.add_redirect_callback_urls(
                path_params={"app_id": self.settings.client_id},
                accept_content_types = ('application/json',),
                body = {
                    "urls": list(callback_urls),
                },
            )
        
        if logout_urls:
            if verbose: self.logger.info(f'Adding Logout Redirect URLs: {logout_urls}')
            self.callback_api.add_logout_redirect_urls(
                path_params={"app_id": self.settings.client_id},
                accept_content_types = ('application/json', 'charset=utf-8'),
                body = {
                    "urls": list(logout_urls),
                },
            )



    """
    Authentication Dependencies
    """

    async def get_kinde_client_for_user_id(
        self,
        request: Request,
        user_id: str,
        optional: Optional[bool] = False,
        **kwargs,
    ) -> Optional['KindeApiClient']:
        """
        Fetches the Kinde Client for the User ID
        """
        token = request.session.get("access_token", await self.token_data.aget(user_id))
        if token is not None:
            client = self.create_api_client(request = request, user_id = user_id)
            client.access_token_obj = token
            if not client.is_authenticated() and not optional:
                _ = request.session.pop('user_id', None)
                raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not Authenticated")
            return client
        elif not optional:
            _ = request.session.pop('user_id', None)
            raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not Authorized")
            # raise ValueError(f'No token found for user id: {user_id}')
        return None
        
    async def get_kinde_client_for_api_key(
        self,
        request: Request,
        api_key: str,
        optional: Optional[bool] = False,
        **kwargs,
    ) -> Optional['KindeApiClient']:
        """
        Fetches the Kinde Client for the API Key
        """
        user_id = await self.settings.adecrypt_api_key(api_key)
        client = await self.get_kinde_client_for_user_id(request, user_id, optional = optional)
        if client is None: return None
        request.session['user_id'] = user_id
        request.session["x_api_key"] = api_key
        request.session["access_token"] = client.access_token_obj
        return client


    async def get_kinde_client_for_authorization(
        self,
        request: Request,
        authorization: str,
        optional: Optional[bool] = False,
        **kwargs,
    ) -> Optional['KindeApiClient']:
        """
        Fetches the Kinde Client for the Authorization
        """

        # Since the authorization is a JWT, we need to 
        # retrieve the user_id from the JWT
        # in order to fetch the underlying access_token_object
        client = self.create_api_client(request = request)
        signing_key = client.jwks_client.get_signing_key_from_jwt(authorization)
        try:
            jwt_claim = jwt.decode(
                jwt = authorization,
                key = signing_key.key,
                algorithms = ["RS256"],
                options = {
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": False
                }
            )
            user_id = jwt_claim['sub']
            token = request.session.get("access_token", await self.token_data.aget(user_id))
            if not token and not optional: 
                raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not Authorized: No Token Found")
            client.access_token_obj = token
            if not client.is_authenticated() and not optional:
                raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not Authorized")
            request.session['user_id'] = user_id
            x_api_key = await self.settings.acreate_api_key(user_id) 
            request.session["x_api_key"] = x_api_key
            request.session["access_token"] = client.access_token_obj
            return client
        
        except jwt.exceptions.ExpiredSignatureError as e:
            self.autologger.warning(f'Expired JWT Token: {e}')
            _ = request.session.pop('user_id', None)
            if not optional: raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not Authorized: Expired JWT Token") from e
            return None

        except Exception as e:
            self.autologger.error(f'Error Decoding JWT: {e}')
            _ = request.session.pop('user_id', None)
            if not optional: raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not Authorized: Unable to decode JWT Token") from e
            return None

    async def run_post_callback_auth_hooks(
        self,
        request: Request,
        client: Optional['KindeApiClient'] = None,
        **kwargs,
    ):
        """
        Runs the post callback auth hooks

        - This runs the first time a new session is created for a user from the callback step
        """
        await self.settings.ctx.run_post_validate_auth_hooks(request, client)
        if client is None: return

    async def run_post_configure_user_hook(
        self,
        request: Request,
        client: Optional['KindeApiClient'] = None,
        **kwargs,
    ):
        """
        Runs the post configure user hook
        """
        if client is None: return
        _ = request.session.pop('is_anon', None)
        
        # Configure some of the session parameters
        if client.user_email:
            if not request.session.get('user_email') or request.session['user_email'] != client.user_email:
                request.session['user_email'] = client.user_email
            if self.settings.admin_emails and client.user_email in self.settings.admin_emails:
                request.session['is_admin'] = True
                request.session['user_role'] = UserRole.ADMIN
                client.user_role = UserRole.ADMIN
        
        if client.email_domain:
            if not request.session.get('email_domain') or request.session['email_domain'] != client.email_domain:
                request.session['email_domain'] = client.email_domain
            if not client.user_role and self.settings.staff_email_domains and client.email_domain in self.settings.staff_email_domains:
                request.session['is_staff'] = True
                request.session['user_role'] = UserRole.STAFF
                client.user_role = UserRole.STAFF
        
        if not client.user_role:
            request.session['user_role'] = UserRole.USER


    async def run_post_validate_auth_hooks(
        self,
        request: Request,
        client: Optional['KindeApiClient'] = None,
        **kwargs,
    ):
        """
        Runs the post validation auth hooks

        - This runs every single time a user is authenticated
        """
        if client is None: return

        # Save the refreshed token to the user data if it has been refreshed
        if client._has_refreshed_token:
            await self.token_data.aset(client.user_id, client.access_token_obj)
            client._has_refreshed_token = False

        await self.run_post_configure_user_hook(request, client)

        # client._app_api = self
        # Try to get the user_id - which will detect whether the id_token is expired
        # try:
        #     _ = client.user_id        
        # except OAuthError as e:
        #     self.autologger.error(f'Error Getting User ID: {e}')
        #     if not request.session.get('user_id'):
        #         self.logger.error('No User ID Found in Session. Clearing Session')
        #         request.session.pop('user_id', None)
        #         raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not Authorized: No User ID Found in Session") from e
        #     claims_token = self.fetch_refresh_claims_token(user_id = request.session['user_id'])
        #     self.autologger.info(f'Refreshing Claims Token: {claims_token} - {request.session["user_id"]}')
        #     raise e
        
        # if client._has_refreshed_token:
        #     # Save the refreshed token to the user data if it has been refreshed
        #     await self.token_data.aset(client.user_id, client.access_token_obj)
        #     client._has_refreshed_token = False

        self.logger.info(f'{client.access_token_obj} - {client.user_id}')

    async def configure_initial_request(
        self,
        request: Request,
    ) -> None:
        """
        Configures the initial request
        """
        if not request.session.get('user_role'): request.session['user_role'] = UserRole.ANON
        if request.session['user_role'] == UserRole.ANON:
            request.session['is_anon'] = True

    def create_dependency(
        self,
        optional: Optional[bool] = False,
        **kwargs,
    ) -> Callable[..., Union['KindeApiClient', Awaitable['KindeApiClient']]]:
        """
        Creates a Kinde Client Dependency
        """

        async def inner(
            request: Request,
            x_api_key: APIKey = None,
            authorization: Authorization = None,
        ) -> Optional['KindeApiClient']:
            """
            Fetches the Kinde Client from the Request
            """
            await self.configure_initial_request(request)
            client: Optional['KindeApiClient'] = None
            await self.settings.ctx.run_pre_validate_hooks(request)
            if user_id := request.session.get("user_id"):
                client = await self.get_kinde_client_for_user_id(request, user_id, optional = optional)
            
            if client is None and x_api_key:
                client = await self.get_kinde_client_for_api_key(request, x_api_key, optional = optional)
            
            if client is None and authorization:
                client = await self.get_kinde_client_for_authorization(request, authorization, optional = optional)
            
            await self.settings.ctx.run_post_validate_hooks(request, client)
            await self.run_post_validate_auth_hooks(request, client)
            await self.settings.ctx.run_post_validate_auth_hooks(request, client)
            return client
        
        return inner
    
    async def run_kinde_callback(
        self,
        request: Request,
    ) -> 'KindeApiClient':
        """
        Runs the Kinde Callback Hook
        """
        kinde_client = self.create_api_client()
        kinde_client.fetch_token(authorization_response = str(request.url))
        request.session["access_token"] = kinde_client.access_token_obj
        request.session["user_id"] = kinde_client.user_id
        # Save the token to the user data
        await self.token_data.aset(kinde_client.user_id, kinde_client.access_token_obj)
        # Create the api key for the user
        request.session["x_api_key"] = await self.settings.acreate_api_key(kinde_client.user_id)
        return kinde_client




    """
    Downstream APIs
    """

    @overload
    def mount_endpoints(
        self,
        login_path: Optional[str] = '/api/auth/login',
        logout_path: Optional[str] = '/api/auth/logout',
        register_path: Optional[str] = '/api/auth/register',
        callback_path: Optional[str] = '/api/auth/callback',

        user_profile_path: Optional[str] = '/api/auth/user',
        user_profile_enabled: Optional[bool] = True,

        logout_redirect_path: Optional[str] = '/docs',

        include_in_schema: Optional[bool] = False,
        **kwargs,
    ):
        """
        Mounts the endpoints
        """
        ...


    def mount_endpoints(
        self,
        **kwargs,
    ):
        """
        Mounts the endpoints
        """
        self.router_handler.mount_endpoints(**kwargs)
        self.app.include_router(self.router_handler.router, tags = ['Kinde Auth'])
        self.app.mount(self.settings.staticfile_url_path, self.settings.staticfiles, name="kstatic")


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
            base_url = str(self.app.url_path_for('docs').make_absolute_url(self.settings.app_endpoint)) + '#/operations'
            redirect = redirect.replace('docs=', '')
            if redirect in self.docs_schema_index:
                return f'{base_url}/{self.docs_schema_index[redirect]}'
        return self.app.url_path_for(redirect).make_absolute_url(self.settings.app_endpoint)



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
