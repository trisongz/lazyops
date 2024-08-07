from __future__ import annotations

"""
Kinde Handlers
"""

import abc
from fastapi import FastAPI, Request, Response, Depends, HTTPException, APIRouter, status
from fastapi.responses import RedirectResponse, HTMLResponse
from lazyops.utils.lazy import lazy_import
from .base import kinde_api_import_paths
from typing import Optional, List, Dict, Any, overload, TYPE_CHECKING


if TYPE_CHECKING:
    import jinja2
    from kvdb import PersistentDict
    from authlib.oauth2.rfc6749 import OAuth2Token
    from .api import KindeApiClient
    from .config import KindeSettings
    from .client import KindeClient
    from .base import (
        KindeAPIs,
        UsersApi,
        ApplicationsApi,
        OrganizationsApi,
        CallbacksApi,
        RolesApi,
        PermissionsApi,
    )
    from lazyops.utils.logs import Logger


class BaseKindeHandler(abc.ABC):
    """
    The Base Kinde Handler
    """

    def __init__(
        self,
        settings: Optional['KindeSettings'] = None,
        **kwargs,
    ):
        """
        Initializes the Kinde Handler
        """
        if settings is None:
            from .utils import get_kinde_settings
            settings = get_kinde_settings()
        self.settings = settings
        self._mtg_api: Optional['KindeApiClient'] = None
        self._apis: Dict[str, 'KindeAPIs'] = {}
        self._pdicts: Dict[str, 'PersistentDict'] = {}
        self.post_init(**kwargs)
    
    def post_init(self, **kwargs):
        """
        Post Initialization
        """
        pass

    @property
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        return self.settings.logger
    
    @property
    def autologger(self) -> 'Logger':
        """
        Returns the autologger
        """
        return self.settings.autologger

    @property
    def data(self) -> 'PersistentDict':
        """
        Returns the Persistent Dict for data
        """
        return self.settings.data
    
    @property
    def mtg_api(self) -> 'KindeApiClient':
        """
        Returns the mtg api
        """
        if self._mtg_api is None and self.settings.is_mtg_enabled:
            from kinde_sdk.kinde_api_client import KindeApiClient
            self._mtg_api = KindeApiClient(**self.settings.get_kinde_mtg_client_config())
        return self._mtg_api
    

    @property
    def user_api(self) -> 'UsersApi':
        """
        Returns the user api
        """
        if 'user_api' not in self._apis and self.settings.is_mtg_enabled:
            self._apis['user_api'] = self._get_api('user_api')
        return self._apis['user_api']
    
    @property
    def organization_api(self) -> 'OrganizationsApi':
        """
        Returns the organization api
        """
        if 'organization_api' not in self._apis and self.settings.is_mtg_enabled:
            self._apis['organization_api'] = self._get_api('organization_api')
        return self._apis['organization_api']
    
    @property
    def application_api(self) -> 'ApplicationsApi':
        """
        Returns the application api
        """
        if 'application_api' not in self._apis and self.settings.is_mtg_enabled:
            self._apis['application_api'] = self._get_api('application_api')
        return self._apis['application_api']
    
    @property
    def callback_api(self) -> 'CallbacksApi':
        """
        Returns the callback api
        """
        if 'callback_api' not in self._apis and self.settings.is_mtg_enabled:
            self._apis['callback_api'] = self._get_api('callback_api')
        return self._apis['callback_api']
    
    @property
    def role_api(self) -> 'RolesApi':
        """
        Returns the role api
        """
        if 'role_api' not in self._apis and self.settings.is_mtg_enabled:
            self._apis['role_api'] = self._get_api('role_api')
        return self._apis['role_api']
    
    @property
    def permission_api(self) -> 'PermissionsApi':
        """
        Returns the permission api
        """
        if 'permission_api' not in self._apis and self.settings.is_mtg_enabled:
            self._apis['permission_api'] = self._get_api('permission_api')
        return self._apis['permission_api']

    def _get_api(
        self,
        api_class: str,
        **kwargs,
    ) -> 'KindeAPIs':
        """
        Returns the api
        """
        api_class = kinde_api_import_paths.get(api_class, api_class)
        return lazy_import(api_class)(self.mtg_api, **kwargs)
    
    @property
    def token_data(self) -> 'PersistentDict[str, OAuth2Token]':
        """
        Returns the token data
        """
        if 'token_data' not in self._pdicts:
            self._pdicts['token_data'] = self.data.get_child(
                'token_data',
                serializer = 'pickle',
                compression = 'zstd',
                compression_level = 19,
            )
        return self._pdicts['token_data']


    @property
    def session_data(self) -> 'PersistentDict[str, Dict[str, Any]]':
        """
        Returns the session data
        """
        if 'session_data' not in self._pdicts:
            self._pdicts['session_data'] = self.data.get_child(
                'session_data',
                serializer = 'pickle',
                compression = 'zstd',
                compression_level = 19,
                expiration = self.settings.user_session_expiration + 600,
            )
        return self._pdicts['session_data']
    



class KindeRouter(BaseKindeHandler):
    """
    The Kinde Router
    """


    if TYPE_CHECKING:
        def __init__(
            self,
            settings: Optional['KindeSettings'] = None,
            client: Optional['KindeClient'] = None,
            **kwargs,
        ):
            ...


    def post_init(self, client: Optional['KindeClient'] = None, **kwargs):
        """
        Post Initialization
        """
        self.client = client
        from fastapi import APIRouter

        # This isn't resolved yet in fastapi
        # https://github.com/tiangolo/fastapi/pull/9630
        # @contextlib.asynccontextmanager
        # async def lifespan(app: APIRouter):
        #     """
        #     Handles the lifespan of the router
        #     """
        #     self.logger.info('Starting Up: Authorizing Application')
        #     await self.client.authorize_application()
        #     yield

        self.router = APIRouter(
            # lifespan = lifespan,
        )
        self.paths: Dict[str, str] = {}



    def configure_endpoint_paths(
        self,
        login_path: Optional[str] = None,
        logout_path: Optional[str] = None,
        register_path: Optional[str] = None,
        callback_path: Optional[str] = None,

        user_profile_path: Optional[str] = None,
        logout_redirect_path: Optional[str] = None,
        **kwargs,
    ):
        """
        Configures the endpoint paths
        """
        if login_path is None: login_path = self.settings.login_path
        elif login_path != self.settings.login_path: 
            self.settings.login_url = login_path
        self.paths['login'] = login_path

        if logout_path is None: logout_path = self.settings.logout_path
        elif logout_path != self.settings.logout_path: 
            self.settings.logout_url = logout_path
        self.paths['logout'] = logout_path
        
        if register_path is None: register_path = self.settings.register_path
        elif register_path != self.settings.register_path: 
            self.settings.register_url = register_path
        self.paths['register'] = register_path

        if callback_path is None: callback_path = self.settings.callback_path
        elif callback_path != self.settings.callback_path: 
            self.settings.callback_url = callback_path
        self.paths['callback'] = callback_path

        if user_profile_path is None: user_profile_path = self.settings.user_profile_path
        elif user_profile_path != self.settings.user_profile_path:
            self.settings.user_profile_path = user_profile_path
        self.paths['user_profile'] = user_profile_path

        if logout_redirect_path is None: logout_redirect_path = self.settings.logout_redirect_path
        elif logout_redirect_path != self.settings.logout_redirect_path: 
            self.settings.logout_redirect_url = logout_redirect_path
        self.paths['logout_redirect'] = logout_redirect_path


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
        login_path: Optional[str] = None,
        logout_path: Optional[str] = None,
        register_path: Optional[str] = None,
        callback_path: Optional[str] = None,

        user_profile_path: Optional[str] = None,
        user_profile_enabled: Optional[bool] = None,
        include_in_schema: Optional[bool] = None,

        server_identity: Optional[str] = None,
        server_identity_path: Optional[str] = '/_identity',

        enable_authorize: Optional[bool] = True,
        authorize_path: Optional[str] = '/authorize',
        x_api_key_path: Optional[str] = '/apikey',

        **kwargs,
    ):
        """
        Mounts the endpoints
        """
        from fastapi import Depends, Query
        from fastapi.responses import RedirectResponse, JSONResponse, PlainTextResponse, HTMLResponse
        from kinde_sdk.kinde_api_client import KindeApiClient

        self.configure_endpoint_paths(
            login_path = login_path,
            logout_path = logout_path,
            register_path = register_path,
            callback_path = callback_path,
            user_profile_path = user_profile_path,
            **kwargs,
        )

        if user_profile_enabled is None: user_profile_enabled = self.settings.user_profile_enabled
        elif user_profile_enabled != self.settings.user_profile_enabled:
            self.settings.user_profile_enabled = user_profile_enabled
        
        @self.router.on_event('startup')
        async def auth_startup():
            """
            Handles the startup of the auth endpoints
            """
            if self.settings.is_mtg_enabled:
                await self.client.authorize_application()
                self.logger.info('Completed Kinde Application Authorization')

        @self.router.get(self.paths['login'], include_in_schema = include_in_schema)
        async def login(
            request: Request,
            kinde_client: Optional[KindeApiClient] = Depends(self.client.create_dependency(optional=True)),
            redirect: Optional[str] = Query(None, description="The redirect page to use after login"),
        ):
            """
            Kinde Login Endpoint
            """
            if kinde_client is not None:
                if redirect is not None: return RedirectResponse(self.client.get_app_redirection(redirect))
                return {'login': 'success', 'x-api-key': request.session.get('x_api_key')}

            kinde_client = self.client.create_api_client()
            response = RedirectResponse(kinde_client.get_login_url())
            if redirect: response.set_cookie(
                key = 'x-auth-redirect', value = redirect, max_age = 60, httponly = True,
            )
            return response

        @self.router.get(self.paths['logout'], include_in_schema = include_in_schema)
        async def logout(
            request: Request,
            kinde_client: Optional[KindeApiClient] = Depends(self.client.create_dependency(optional=True)),
            redirect: Optional[str] = Query(None, description="The redirect page to use after logout"),
        ):
            """
            Kinde Logout Endpoint
            """
            redirect = redirect or self.settings.logout_redirect_url
            if kinde_client is not None:
                logout_url = kinde_client.logout(redirect_to = redirect)
                request.session.pop("user_id", None)
                return RedirectResponse(logout_url)
            raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not Authorized")

        
        @self.router.get(self.paths['callback'], include_in_schema = include_in_schema)
        async def kinde_callback(
            request: Request,
        ):
            """
            Kinde Callback Endpoint
            """
            kinde_client = await self.client.run_kinde_callback(request)
            await self.client.run_post_callback_auth_hooks(request, kinde_client)

            # kinde_client = self.client.create_api_client()
            # kinde_client.fetch_token(authorization_response = str(request.url))
            # user = kinde_client.get_user_details()

            # user_id = user.get("id")
            # request.session["access_token"] = kinde_client.access_token_obj
            # request.session["user_id"] = user_id
            # # Save the token to the user data
            # await self.client.token_data.aset(user_id, kinde_client.access_token_obj)

            # # Create the api key for the user
            # x_api_key = await self.settings.acreate_api_key(user_id) 
            # request.session["x_api_key"] = x_api_key
            
            if self.settings.is_development_env:
                self.logger.info(f'User {kinde_client.user_id} logged in')
                # self.autologger.info(f'User Claims Names: {kinde_client.__decoded_tokens}')
            if redir_value := request.cookies.get('x-auth-redirect'):
                redirect = self.client.get_app_redirection(redir_value)
                if self.settings.is_development_env:
                    self.autologger.info(f'Found redirect cookie: {redir_value} - Redirecting to {redirect}')
                response = RedirectResponse(redirect)
                response.delete_cookie('x-auth-redirect')
            elif user_profile_enabled:
                response = RedirectResponse(self.router.url_path_for('kinde_user_profile'))
            else:
                response = JSONResponse({'login': 'success', 'x-api-key': request.session.get('x_api_key')})
            return response
            
        @self.router.get(self.paths['register'], include_in_schema = include_in_schema)
        async def kinde_register(
            request: Request,
            kinde_client: Optional[KindeApiClient] = Depends(self.client.create_dependency(optional=True)),
        ):
            """
            Kinde Register Endpoint
            """
            if kinde_client is not None:
                raise HTTPException(status_code = status.HTTP_409_CONFLICT, detail = "You are already registered. Please logout instead")
            kinde_client = self.client.create_api_client()
            register_url = kinde_client.get_register_url()
            if self.settings.enable_org_signup:
                register_url = kinde_client.create_org()
            return RedirectResponse(register_url)
        
        
        if user_profile_enabled:
            @self.router.get(self.paths['user_profile'], include_in_schema = include_in_schema)
            async def kinde_user_profile(
                request: Request,
                kinde_client: Optional[KindeApiClient] = Depends(self.client.create_dependency(optional=True)),
            ):
                """
                Kinde User Profile Endpoint
                """
                if kinde_client is None: 
                    template: 'jinja2.Template' = self.settings.templates.get_template('logged_out.html')
                    return HTMLResponse(
                        await template.render_async(
                            request = request, 
                            settings = self.settings,
                            client = self.client,
                        )
                    )
                    # raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Not Logged In")
                template: 'jinja2.Template' = self.settings.templates.get_template('user_profile.html')
                return HTMLResponse(
                    await template.render_async(
                        request = request, 
                        api_client = kinde_client,
                        client = self.client,
                        # client = kinde_client, 
                        settings = self.settings,
                        user = kinde_client.get_user_details(),
                    )
                )

        """
        Extra Endpoints
        """

        @self.router.get(x_api_key_path, include_in_schema = include_in_schema)
        async def kinde_get_api_key(
            request: Request,
            kinde_client: Optional[KindeApiClient] = Depends(self.client.create_dependency(optional=True)),
            plaintext: Optional[bool] = Query(None, description="If True, will return the api key in plaintext"),
        ):
            """
            Fetches the API Key for the Current User
            """
            if kinde_client is None: return 'null' if plaintext else {'api_key': 'no_user_found'}
            response = PlainTextResponse(
                content = request.session.get("x_api_key")
            ) if plaintext else JSONResponse(
                content = {'api_key': request.session.get("x_api_key")}
            )
            return response
        

        if server_identity:
            @self.router.get(server_identity_path, include_in_schema = include_in_schema)
            async def get_server_identity(
                request: Request,
            ):
                """
                Get the Server Identity
                """
                return PlainTextResponse(content = server_identity)
        

        if enable_authorize:
            @self.router.get(authorize_path, include_in_schema = include_in_schema)
            async def kinde_authorize(
                request: Request,
                kinde_client: Optional[KindeApiClient] = Depends(self.client.create_dependency(optional=True)),
            ):
                """
                Authorize the User or Client API by configuring the Cookies
                """
                if kinde_client is None: return JSONResponse(content = {'authorize': 'invalid_user'})
                return JSONResponse(
                    content = {
                        'authorized': True, 
                        'identity': server_identity or self.settings.app_name, 
                        'environment': self.settings.app_env.value, 
                        'api-key': request.session.get("x_api_key"),
                    }
                )
                


            




