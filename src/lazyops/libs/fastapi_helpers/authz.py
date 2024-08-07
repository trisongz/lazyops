from __future__ import annotations

"""
FastAPI AuthZ Client

- Designed for internal use 
"""

import abc
import xxhash
import aiohttpx
from fastapi import Request, FastAPI
from urllib.parse import urlencode, urljoin, urlparse
from pydantic import BaseModel, Field, PrivateAttr
from pydantic_settings import BaseSettings
from lazyops.utils.logs import logger, null_logger
from lazyops.libs.abcs.types.security import Authorization, APIKey
from lazyops.utils.helpers import create_unique_id
from lazyops.utils.system import is_in_kubernetes
from lazyops.libs.abcs.configs.types import AppEnv
from typing import Optional, List, Dict, Any, Union, Callable, TYPE_CHECKING, Awaitable


class AuthZClientSettings(BaseSettings):
    """
    AuthZ Client Settings
    """

    endpoint: Optional[str] = None
    x_key: Optional[str] = None
    session_auth_key: Optional[str] = None
    session_secret_key: Optional[str] = None
    session_cookie_name: Optional[str] = 'authz-cookie'
    provider: Optional[str] = None
    debug_enabled: bool = False

    _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)

    @property
    def in_k8s(self) -> bool:
        """
        Returns if the app is running in kubernetes
        """
        if 'in_k8s' not in self._extra: self._extra['in_k8s'] = is_in_kubernetes()
        return self._extra['in_k8s']

    @property
    def module_name(self) -> Optional[str]:
        """
        Returns the module name
        """
        return self._extra.get('module_name')

    @module_name.setter
    def module_name(self, value: str):
        """
        Sets the module name
        """
        self._extra['module_name'] = value
        self._extra['app_env'] = AppEnv.from_module_name(value)
    

    @property
    def app_env(self) -> AppEnv:
        """
        Returns the app env
        """
        if 'app_env' not in self._extra: 
            self._extra['app_env'] = AppEnv.from_module_name(self.module_name) if \
                self.module_name else AppEnv.from_module_name('authz')
        return self._extra['app_env']


    @property
    def authz_url(self) -> str:
        """
        Returns the authz url
        """
        if 'authz_url' not in self._extra:
            if self.in_k8s: self._extra['authz_url'] = 'http://authz-api-service.api.svc.cluster.local:8080'
            elif self.debug_enabled: self._extra['authz_url'] = 'http://127.0.0.1:8080'
            else: self._extra['authz_url'] = self.endpoint
        return self._extra['authz_url']
    
    @property
    def authz_provider(self) -> str:
        """
        Returns the authz provider
        """
        return self._extra.get('authz_provider', self.provider)

    @authz_provider.setter
    def authz_provider(self, value: str):
        """
        Sets the authz provider
        """
        self._extra['authz_provider'] = value


    class Config:
        env_prefix = "AUTHZ_"
        case_sensitive = False
        extra = 'allow'


class AuthZAppConfig(BaseModel):
    """
    The AuthZ App Config
    """
    srv_domain: Optional[str] = None
    srv_env: Optional[str] = None
    srv_identity: Optional[str] = None
    authz_optional: Optional[bool] = None
    authz_offline: Optional[bool] = None
    required_role: Optional[str] = None
    provider: Optional[str] = None

    set_role: Optional[bool] = None # If True, will set the role in the session
    set_authorization: Optional[bool] = None # If True, will set the authorization in the session
    set_api_key: Optional[bool] = None # If True, will set the api key in the session



class AuthZClient(abc.ABC):
    """
    The AuthZ Client
    """
    def __init__(
        self,
        authz_endpoint: str,
        x_authz_key: str,
        app_config: AuthZAppConfig,

        callback_app_path: Optional[str] = None,
        redirect_app_path: Optional[str] = None,

        callback_url: Optional[str] = None,
        redirect_url: Optional[str] = None,

        hash_method: Optional[str] = 'xxh128',
        debug_enabled: Optional[bool] = False,
        app_endpoint: Optional[str] = None,
        app: Optional['FastAPI'] = None,
    ):
        """
        The AuthZ Client
        """
        self.authz_endpoint = authz_endpoint
        self.x_authz_key = x_authz_key
        self.debug_enabled = debug_enabled
        self.logger = logger
        self.autologger = logger if debug_enabled else null_logger
        self.hasher = getattr(xxhash, f'{hash_method}_hexdigest')
        
        self.callback_app_path = callback_app_path
        self.redirect_app_path = redirect_app_path

        self.callback_url = callback_url
        self.redirect_url = redirect_url
        
        self.app = app
        self.app_endpoint = app_endpoint
        self.app_config = app_config

        self.in_k8s = is_in_kubernetes()
        self._extra: Dict[str, Any] = {}

    
    @property
    def srv_domain(self) -> Optional[str]:
        """
        Returns the server domain
        """
        if self.app_config.srv_domain: return self.app_config.srv_domain
        if 'srv_domain' not in self._extra and self.app_endpoint:
            self._extra['srv_domain'] = urlparse(self.app_endpoint).netloc
        return self._extra.get('srv_domain')

    def create_authz_key(
        self,
        session_id: str,
        callback_url: str,
    ) -> str:
        """
        Encodes the AuthZ Key
        """
        return self.hasher(f'{session_id}:{callback_url}:{self.x_authz_key}')

    def encode_sid(
        self,
        session_id: str,
    ) -> str:
        """
        Encodes the Session ID
        """
        return self.hasher(f'{self.x_authz_key}:{session_id}')

    def create_session_id(self):
        """
        Creates a new session id
        """
        return create_unique_id(alph_only=True)

    def get_app_endpoint_from_request(
        self,
        request: Request,
    ) -> str:
        """
        Returns the app endpoint from the request
        """
        headers = request.headers
        if headers.get(':authority:'):
            return headers[':scheme:'] + '://' + headers[':authority:']
        if headers.get('x-forwarded-host'):
            if headers.get('x-forwaded-scheme'):
                return headers['x-forwaded-scheme'] + '://' + headers['x-forwarded-host']
            if self.in_k8s:
                return 'https://' + headers['x-forwarded-host']
            forwaded_port = headers['x-forwarded-port']
            if '443' in forwaded_port: return 'https://' + headers['x-forwarded-host']
            return 'http://' + headers['x-forwarded-host']
        if headers.get('host'):
            scheme = 'https' if self.in_k8s else 'http'
            return f'{scheme}://' + headers['host']
        return None

    async def retrieve_offline_session(
        self,
        session_id: str,
        request: Request,
    ):
        """
        Retrieves the offline session
        """
        sid = self.encode_sid(session_id)
        validation_response = await aiohttpx.async_get(
            url = urljoin(self.authz_endpoint, '/api/offline/retrieve'),
            params = {
                'sid': sid,
            }
        )
        data: Dict[str, Any] = validation_response.json()
        if data.get('validation_result'):
            request.session['authz_result'] = data['validation_result']
            _ = request.session.pop('authz_started')
            self.autologger.info(data["validation_result"], colored = True, prefix = f'Validation Result: {sid}')
            return True
        else:
            request.session['authz_error'] = data
            self.logger.info(data, colored = True, prefix = f'Validation Error - {sid}')
            return False

    def get_callback_url(
        self,
        callback_url: Optional[str] = None,
        callback_app_path: Optional[str] = None,
        callback_path_params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Returns the callback url
        """
        if callback_url: 
            if not callback_url.startswith('http'):
                callback_url = urljoin(self.app_endpoint, callback_url)
            return callback_url
        if callback_app_path and self.app:
            callback_path_params = callback_path_params or {}
            return self.app.url_path_for(callback_app_path).make_absolute_url(self.app_endpoint, **callback_path_params)
        if self.callback_url:
            if not self.callback_url.startswith('http'):
                self.callback_url = urljoin(self.app_endpoint, self.callback_url)
            return self.callback_url
        if self.callback_app_path and self.app:
            callback_path_params = callback_path_params or {}
            return self.app.url_path_for(self.callback_app_path).make_absolute_url(self.app_endpoint, **callback_path_params)
        return None
    
    def get_redirect_url(
        self,
        redirect_url: Optional[str] = None,
        redirect_app_path: Optional[str] = None,
        redirect_path_params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Returns the redirect url
        """
        if redirect_url: 
            if not redirect_url.startswith('http'):
                redirect_url = urljoin(self.app_endpoint, redirect_url)
            return redirect_url
        if redirect_app_path and self.app:
            redirect_path_params = redirect_path_params or {}
            return self.app.url_path_for(redirect_app_path).make_absolute_url(self.app_endpoint, **redirect_path_params)
        if self.redirect_url:
            if not self.redirect_url.startswith('http'):
                self.redirect_url = urljoin(self.app_endpoint, self.redirect_url)
            return self.redirect_url
        if self.redirect_app_path and self.app:
            redirect_path_params = redirect_path_params or {}
            return self.app.url_path_for(self.redirect_app_path).make_absolute_url(self.app_endpoint, **redirect_path_params)
        return None

    async def create_authz_request(
        self,
        api_key: APIKey,
        authorization: Authorization,
        session_id: str,
        required_role: Optional[str] = None,
        authz_optional: Optional[bool] = None,
        authz_offline: Optional[bool] = None,
        provider: Optional[str] = None,

        callback_url: Optional[str] = None,
        callback_app_path: Optional[str] = None,
        callback_path_params: Optional[Dict[str, Any]] = None,

        redirect_url: Optional[str] = None,
        redirect_app_path: Optional[str] = None,
        redirect_path_params: Optional[Dict[str, Any]] = None,

        **kwargs,
    ) -> Dict[str, Union[str, Dict[str, Any]]]:
        """
        Creates the authz request
        """
        callback_url = self.get_callback_url(callback_url = callback_url, callback_app_path = callback_app_path, callback_path_params = callback_path_params)
        request_body = {
            'session_id': session_id,
            'callback_url': callback_url,
            'redirect_url': self.get_redirect_url(redirect_url = redirect_url, redirect_app_path = redirect_app_path, redirect_path_params = redirect_path_params),
            'authz_key': self.create_authz_key(session_id, callback_url),
            'api_key': api_key,
            'authorization': authorization.credentials if authorization else None,
            'srv_domain': self.srv_domain,
            'srv_env': self.app_config.srv_env,
            'srv_identity': self.app_config.srv_identity,
            'required_role': required_role or self.app_config.required_role,
            'authz_optional': authz_optional if authz_optional is not None else self.app_config.authz_optional,
            'authz_offline': authz_offline if authz_offline is not None else self.app_config.authz_offline,
            'provider': provider or self.app_config.provider,
        }
        request_body = {k:v for k,v in request_body.items() if v}
        self.autologger.info(request_body, colored = True, prefix = f'AuthZ Request: {session_id}')
        response = await aiohttpx.async_post(
            url = urljoin(self.authz_endpoint, '/api/validate'),
            headers = {
                'content-type': 'application/json',
            },
            json = request_body,
        )
        # response.raise_for_status()
        return response.json()


    async def validate_request_handler(
        self,
        request: Request,
        api_key: APIKey,
        authorization: Authorization,

        required_role: Optional[str] = None,
        authz_optional: Optional[bool] = None,
        authz_offline: Optional[bool] = None,
        provider: Optional[str] = None,

        callback_url: Optional[str] = None,
        callback_app_path: Optional[str] = None,
        callback_path_params: Optional[Dict[str, Any]] = None,

        redirect_url: Optional[str] = None,
        redirect_app_path: Optional[str] = None,
        redirect_path_params: Optional[Dict[str, Any]] = None,

    ) -> bool:
        """
        Validates the request
        """
        if not self.app_endpoint: self.app_endpoint = self.get_app_endpoint_from_request(request)
        if request.session.get('authz_result'): return True
        if not request.session.get('session_id'):
            request.session['session_id'] = self.create_session_id()
            self.autologger.info(f'New Session ID: {request.session["session_id"]}', colored = True)
        session_id = request.session['session_id']
        if request.session.get('authz_started'):
            return await self.retrieve_offline_session(session_id, request)
        data = await self.create_authz_request(
            api_key = api_key,
            authorization = authorization,
            session_id = session_id,
            required_role = required_role,
            authz_optional = authz_optional,
            authz_offline = authz_offline,
            provider = provider,
            callback_url = callback_url,
            callback_app_path = callback_app_path,
            callback_path_params = callback_path_params,
            redirect_url = redirect_url,
            redirect_app_path = redirect_app_path,
            redirect_path_params = redirect_path_params,
        )
        if data.get('validation_result'):
            request.session['authz_result'] = data['validation_result']
            if data['validation_result'].get('role') and self.app_config.set_role:
                request.session['role'] = data['validation_result']['role']
            if data['validation_result'].get('authorization') and self.app_config.set_authorization:
                request.session['authorization'] = data['validation_result']['authorization']
            if data['validation_result'].get('api_key') and self.app_config.set_api_key:
                request.session['api_key'] = data['validation_result']['api_key']
            self.autologger.info(f'Validation Result: {data["validation_result"]}', colored = True, prefix = f'Validation Result: {session_id}')
            return True
        if data.get('redirect_url'):
            request.session['authz_redirect_url'] = data['redirect_url']
            self.autologger.info(f'Redirecting to login: {data["redirect_url"]}', colored = True, prefix = f'Validation Start: {session_id}')
            request.session['authz_started'] = True
            return False
        if data.get('error'):
            request.session['authz_error'] = data
            self.logger.info(data, colored = True, prefix = f'Validation Error: {session_id}')
            return False
        self.autologger.info(f'No Validation Result: {data}', colored = True, prefix = f'Validation Result: {session_id}')
        return False
    

    def create_authz_validation(
        self,
        required_role: Optional[str] = None,
        authz_optional: Optional[bool] = None,
        authz_offline: Optional[bool] = None,
        provider: Optional[str] = None,

        callback_url: Optional[str] = None,
        callback_app_path: Optional[str] = None,
        callback_path_params: Optional[Dict[str, Any]] = None,

        redirect_url: Optional[str] = None,
        redirect_app_path: Optional[str] = None,
        redirect_path_params: Optional[Dict[str, Any]] = None,
    ) -> Callable[..., Awaitable[bool]]:
        """
        Creates the authz validation
        """
        async def inner(
            request: Request,
            api_key: APIKey,
            authorization: Authorization,
        ) -> bool:
            """
            Validates the request
            """
            return await self.validate_request_handler(
                request = request,
                api_key = api_key,
                authorization = authorization,
                required_role = required_role,
                authz_optional = authz_optional,
                authz_offline = authz_offline,
                provider = provider,
                callback_url = callback_url,
                callback_app_path = callback_app_path,
                callback_path_params = callback_path_params,
                redirect_url = redirect_url,
                redirect_app_path = redirect_app_path,
                redirect_path_params = redirect_path_params,
            )
        return inner
    
    """
    AuthZ API Methods (Mountable)
    """

    def mount_authz_components(
        self,
        app: 'FastAPI',
        
        required_role: Optional[str] = None,
        authz_optional: Optional[bool] = None,
        authz_offline: Optional[bool] = None,
        provider: Optional[str] = None,

        callback_url: Optional[str] = '/authz/callback',
        callback_app_path: Optional[str] = None,
        callback_path_params: Optional[Dict[str, Any]] = None,

        redirect_url: Optional[str] = '/docs',
        redirect_app_path: Optional[str] = None,
        redirect_path_params: Optional[Dict[str, Any]] = None,

        test_endpoint: Optional[str] = None,
        test_endpoint_include_schema: Optional[bool] = None,

    ):
        """
        Mounts the authz components
        """
        from fastapi import Depends, Body
        from fastapi.responses import RedirectResponse
        from .responses import PrettyJSONResponse

        self.app = app
        if not self.callback_url and callback_url: self.callback_url = callback_url
        if not self.redirect_url and redirect_url: self.redirect_url = redirect_url

        @app.post(callback_url, include_in_schema = self.debug_enabled)
        async def app_authz_callback(
            request: Request,
            session_id: str = Body(..., description='Session ID'),
            validation_result: Dict[str, Any] = Body(..., description='Validation Result'),
        ):
            """
            Handles the AuthZ Callback
            """
            self.autologger.info(validation_result, colored = True, prefix = f'AuthZ Callback: {session_id}')
            request.session['authz_result'] = validation_result
            request.session['session_id'] = session_id
            return PrettyJSONResponse({'status': 'ok', 'validation_result': validation_result, 'session_id': session_id})

        if test_endpoint:
            @app.get(test_endpoint, include_in_schema = test_endpoint_include_schema if test_endpoint_include_schema is not None else self.debug_enabled)
            async def app_authz_test(
                request: Request,
                valid_authz: bool = Depends(self.create_authz_validation(
                    required_role = required_role,
                    authz_optional = authz_optional,
                    authz_offline = authz_offline,
                    provider = provider,
                    callback_url = callback_url,
                    callback_app_path = callback_app_path,
                    callback_path_params = callback_path_params,
                    redirect_url = redirect_url,
                    redirect_app_path = redirect_app_path,
                    redirect_path_params = redirect_path_params,
                )),
            ):
                """
                Handles the AuthZ Test
                """
                if valid_authz:
                    self.autologger.info(request.session.get('authz_result'), colored = True, prefix = f'AuthZ Test: {request.session["session_id"]}')
                    return PrettyJSONResponse({'status': 'ok', 'valid': valid_authz, 'validation_result': request.session.get('authz_result')})
                if request.session.get('authz_error'):
                    error = request.session['authz_error']
                    request.session.clear()
                    return PrettyJSONResponse({'status': 'error', 'error': error})
                response = RedirectResponse(url = request.session['authz_redirect_url'])
                if request.session.get('session_id'):
                    response.set_cookie(
                        key = 'x-authz-sid',
                        value = request.session['session_id'],
                        expires = 300,
                        httponly = True,
                    )
                return response
            