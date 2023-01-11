import json
import functools

from lazyops.types.models import BaseModel, validator
from lazyops.types.classprops import lazyproperty
from lazyops.types.static import RESPONSE_SUCCESS_CODES
from lazyops.types.resources import BaseResource, ResourceType, ResponseResource, ResponseResourceType
from lazyops.types.errors import ClientError, fatal_exception
from lazyops.imports._aiohttpx import aiohttpx, resolve_aiohttpx
from lazyops.imports._backoff import backoff, require_backoff
from lazyops.configs.base import DefaultSettings
from lazyops.utils.logs import default_logger as logger
from lazyops.utils.serialization import ObjectEncoder

from typing import Optional, Dict, List, Any, Type, Callable


"""
Client Session
"""
SettingType = Type[DefaultSettings]

_settings: SettingType = None

def get_settings(settings_cls: Optional[SettingType] = None, **kwargs) -> DefaultSettings:
    global _settings
    if _settings is None:
        if settings_cls is None: settings_cls = DefaultSettings
        _settings = settings_cls(**kwargs)
    return _settings


class ClientSession(BaseModel):
    # Base
    client: 'aiohttpx.Client'
    headers: Dict[str, str] = None
    success_codes: Optional[List[int]] = RESPONSE_SUCCESS_CODES

    # Options
    max_retries: Optional[int] = 3
    timeout: Optional[int] = None
    debug_enabled: Optional[bool] = False
    on_error: Optional[Callable] = None
    ignore_errors: Optional[bool] = False

    # Settings
    settings_cls: Optional[SettingType] = None
    settings: Optional[DefaultSettings] = None

    # Resource Models
    input_model: Optional[Type[ResourceType]] = BaseResource
    response_model: Optional[Type[BaseResource]] = ResponseResource
    error_model: Optional[Type[ClientError]] = ClientError

    @validator('settings_cls', pre = True)
    def validate_settings_cls(cls, v):
        if v is None: v = DefaultSettings
        return v

    @validator('settings', pre = True)
    def validate_settings(cls, v, values):
        if v is None: v = get_settings(settings_cls = values.get('settings_cls'))
        return v

    @validator('headers')
    def validate_headers(cls, v, values):
        if v is None: 
            try: v = values.get('settings').get_client_headers()
            except:  v = {}
        return v
    
    @validator('timeout')
    def validate_timeout(cls, v, values):
        if v is None: 
            try: v = values.get('settings').client.timeout
            except: v = None
        return v
    
    @validator('max_retries')
    def validate_max_retries(cls, v, values):
        if v is None: 
            try: v = values.get('settings').client.max_retries
            except: v = 3
        return v
    
    @validator('debug_enabled')
    def validate_debug_enabled(cls, v, values):
        if v is None: 
            try: v = values.get('settings').client.debug_enabled
            except: v = False
        return v

    @lazyproperty
    def api_endpoints(self) -> Dict[str, Dict[str, str]]:
        """
        Returns the api endpoints and methods
        """
        return {
            'get': {
                'url': '/v1/get',
                'method': 'GET',
            },
            'list': {
                'url': '/v1/list',
                'method': 'GET',
            },
            'create': {
                'url': '/v1/create',
                'method': 'POST',
            },
            'update': {
                'url': '/v1/update',
                'method': 'PUT',
            },
            'delete': {
                'url': '/v1/delete',
                'method': 'DELETE',
            },
        }

    @lazyproperty
    def expo_func(self):
        return functools.partial(backoff.expo, base = 4)
    
    @staticmethod
    def object_dumps(input_object: ResourceType) -> str:
        return json.dumps(input_object.dict(), cls = ObjectEncoder)
    
    def get(self,
        input_object: Optional[ResourceType] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ResponseResourceType:
        """
        Get a resource
        """
        if input_object is None: 
            input_object, kwargs = self.input_model.parse_resource(**kwargs)
        data = self.object_dumps(input_object)
        api_method_data = self.api_endpoints['get']
        api_response = self._send(
            method = api_method_data['method'],
            url = api_method_data['url'],
            data = data,
            params = params,
            headers = self.headers,
            timeout = self.timeout,
            **kwargs
        )
        data = self.handle_response(api_response)
        return self.prepare_response(input_obj = input_object, response = data)
    
    async def async_get(self,
        input_object: Optional[ResourceType] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ResponseResourceType:
        """
        Get a resource
        """
        if input_object is None: 
            input_object, kwargs = self.input_model.parse_resource(**kwargs)
        data = self.object_dumps(input_object)
        api_method_data = self.api_endpoints['get']
        api_response = await self._async_send(
            method = api_method_data['method'],
            url = api_method_data['url'],
            data = data,
            params = params,
            headers = self.headers,
            timeout = self.timeout,
            **kwargs
        )
        data = self.handle_response(api_response)
        return self.prepare_response(input_obj = input_object, response = data)
    
    def list(
        self,
        input_object: Optional[ResourceType] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ResponseResourceType:
        """
        List Resources
        """
        if input_object is None: 
            input_object, kwargs = self.input_model.parse_resource(**kwargs)
        data = self.object_dumps(input_object)
        api_method_data = self.api_endpoints['list']
        api_response = self._send(
            method = api_method_data['method'],
            url = api_method_data['url'],
            data = data,
            params = params,
            headers = self.headers,
            timeout = self.timeout,
            **kwargs
        )
        data = self.handle_response(api_response)
        return self.prepare_response(input_obj = input_object, response = data)
    
    async def async_list(
        self,
        input_object: Optional[ResourceType] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ResponseResourceType:
        """
        List Resources
        """
        if input_object is None: 
            input_object, kwargs = self.input_model.parse_resource(**kwargs)
        data = self.object_dumps(input_object)
        api_method_data = self.api_endpoints['list']
        api_response = await self._async_send(
            method = api_method_data['method'],
            url = api_method_data['url'],
            data = data,
            params = params,
            headers = self.headers,
            timeout = self.timeout,
            **kwargs
        )
        data = self.handle_response(api_response)
        return self.prepare_response(input_obj = input_object, response = data)
    
    def create(
        self,
        input_object: Optional[ResourceType] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ResponseResourceType:
        """
        Create a resource
        """
        if input_object is None: 
            input_object, kwargs = self.input_model.parse_resource(**kwargs)
        data = self.object_dumps(input_object)
        api_method_data = self.api_endpoints['create']
        api_response = self._send(
            method = api_method_data['method'],
            url = api_method_data['url'],
            data = data,
            params = params,
            headers = self.headers,
            timeout = self.timeout,
            **kwargs
        )
        data = self.handle_response(api_response)
        return self.prepare_response(input_obj = input_object, response = data)
    
    async def async_create(
        self,
        input_object: Optional[ResourceType] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ResponseResourceType:
        """
        Create a resource
        """
        if input_object is None: 
            input_object, kwargs = self.input_model.parse_resource(**kwargs)
        data = self.object_dumps(input_object)
        api_method_data = self.api_endpoints['create']
        api_response = await self._async_send(
            method = api_method_data['method'],
            url = api_method_data['url'],
            data = data,
            params = params,
            headers = self.headers,
            timeout = self.timeout,
            **kwargs
        )
        data = self.handle_response(api_response)
        return self.prepare_response(input_obj = input_object, response = data)
    
    def update(
        self,
        input_object: Optional[ResourceType] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ResponseResourceType:
        """
        Update a resource
        """
        if input_object is None: 
            input_object, kwargs = self.input_model.parse_resource(**kwargs)
        data = self.object_dumps(input_object)
        api_method_data = self.api_endpoints['update']
        api_response = self._send(
            method = api_method_data['method'],
            url = api_method_data['url'],
            data = data,
            params = params,
            headers = self.headers,
            timeout = self.timeout,
            **kwargs
        )
        data = self.handle_response(api_response)
        return self.prepare_response(input_obj = input_object, response = data)
    
    async def async_update(
        self,
        input_object: Optional[ResourceType] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ResponseResourceType:
        """
        Update a resource
        """
        if input_object is None: 
            input_object, kwargs = self.input_model.parse_resource(**kwargs)
        data = self.object_dumps(input_object)
        api_method_data = self.api_endpoints['update']
        api_response = await self._async_send(
            method = api_method_data['method'],
            url = api_method_data['url'],
            data = data,
            params = params,
            headers = self.headers,
            timeout = self.timeout,
            **kwargs
        )
        data = self.handle_response(api_response)
        return self.prepare_response(input_obj = input_object, response = data)
    
    def delete(
        self,
        input_object: Optional[ResourceType] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ResponseResourceType:
        """
        Delete a resource
        """
        if input_object is None: 
            input_object, kwargs = self.input_model.parse_resource(**kwargs)
        data = self.object_dumps(input_object)
        api_method_data = self.api_endpoints['delete']
        api_response = self._send(
            method = api_method_data['method'],
            url = api_method_data['url'],
            data = data,
            params = params,
            headers = self.headers,
            timeout = self.timeout,
            **kwargs
        )
        data = self.handle_response(api_response)
        return self.prepare_response(input_obj = input_object, response = data)
    
    async def async_delete(
        self,
        input_object: Optional[ResourceType] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ResponseResourceType:
        """
        Delete a resource
        """
        if input_object is None: 
            input_object, kwargs = self.input_model.parse_resource(**kwargs)
        data = self.object_dumps(input_object)
        api_method_data = self.api_endpoints['delete']
        api_response = await self._async_send(
            method = api_method_data['method'],
            url = api_method_data['url'],
            data = data,
            params = params,
            headers = self.headers,
            timeout = self.timeout,
            **kwargs
        )
        data = self.handle_response(api_response)
        return self.prepare_response(input_obj = input_object, response = data)

    def handle_response(
        self, 
        response: 'aiohttpx.Response',
        **kwargs
    ):
        """
        Handle the Response

        :param response: The Response
        """
        if self.debug_enabled:
            logger.info(f'[{response.status_code} - {response.request.url}] headers: {response.headers}, body: {response.text}')
        
        if response.status_code in self.success_codes:
            return response if response.text else None
        
        if self.ignore_errors: return None
        raise self.error_model(
            response = response
        )

    def prepare_response(
        self,
        input_obj: 'ResourceType',
        response: 'aiohttpx.Response',
        response_object: Optional[ResponseResourceType] = None,
        **kwargs
    ):
        """
        Prepare the Response Object
        
        :param data: The Response Data
        :param response_object: The Response Object
        """
        response_object = response_object or self.response_model
        if response_object:
            return response_object.parse_from(input_obj = input_obj, response = response, **kwargs)
        raise NotImplementedError('Response model not defined for this resource.')

    
    def _send(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        retries: Optional[int] = None,
        **kwargs
    ) -> 'aiohttpx.Response':
        if retries is None: retries = self.max_retries
        if timeout is None: timeout = self.timeout
        @backoff.on_exception(
            self.expo_func, Exception, max_tries = retries + 1, giveup = fatal_exception
        )
        def _retryable_send():
            return self.client.request(
                method = method,
                url = url,
                params = params,
                data = data,
                headers = headers,
                timeout = timeout,
                **kwargs
            )
        return _retryable_send()
    
    async def _async_send(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        retries: Optional[int] = None,
        **kwargs
    ) -> 'aiohttpx.Response':
        if retries is None: retries = self.max_retries
        if timeout is None: timeout = self.timeout
        @backoff.on_exception(
            self.expo_func, Exception, max_tries = retries + 1, giveup = fatal_exception
        )
        async def _retryable_async_send():
            return await self.client.async_request(
                method = method,
                url = url,
                params = params,
                data = data,
                headers = headers,
                timeout = timeout,
                **kwargs
            )
        return await _retryable_async_send()



"""
Global Client Class
"""

class BaseClient:
    """
    Base Client Class
    - intended to be subclassed.
    - manages the various sessions
    """

    ctx: Optional[ClientSession] = None
    current: Optional[str] = None
    sessions: Dict[str, ClientSession] = {}

    # Settings
    settings_cls: Optional[SettingType] = None
    settings: Optional[DefaultSettings] = None

    """
    Sessions
    """
    @classmethod
    def init_settings(
        cls,
        settings_cls: Optional[SettingType] = None,
        settings: Optional[DefaultSettings] = None,
        **kwargs
    ):
        """
        Initializes the settings
        """
        if settings_cls is not None:
            cls.settings_cls = settings_cls
            if cls.settings is None: cls.settings = cls.settings_cls()
        if settings is not None: cls.settings = settings
        if cls.settings is None and cls.settings_cls: cls.settings = cls.settings_cls()
        if cls.settings and kwargs: cls.settings.update_config(**kwargs)
    

    @classmethod
    def init_session(
        cls,
        name: str = 'default',
        set_current: bool = False,
        overwrite: Optional[bool] = None,
        **kwargs,
    ) -> ClientSession:
        """
        Initialize the session
        """
        cls.init_settings(**kwargs)
        if name == 'default': name = cls.settings.default_client_name
        if name in cls.sessions and overwrite is not True:
            logger.warning(f'Session {name} already exists')
            return
        resolve_aiohttpx(True)
        client = aiohttpx.Client(
            base_url = kwargs.get('base_url', cls.settings.client.endpoints[name]),
            timeout = cls.settings.client.timeout,
        )
        ctx = ClientSession(
            client = client,
            **kwargs
        )
        cls.sessions[name] = ctx
        logger.info(f'Initialized Session: {name}')
        if (set_current or overwrite) or cls.ctx is None:
            cls.ctx = ctx
            cls.current = name
            logger.info(f'Setting to Current Session: {name}')
        return ctx


    @classmethod
    def get_session(
        cls, 
        name: Optional[str] = None,
        **kwargs
    ) -> ClientSession:
        """
        Get a session by name

        :param name: The name of the session.
        :type name: str
        :return: A :class:`ClientSession` instance.
        """
        if not name: name = cls.current or cls.settings.default_client_name
        if name not in cls.sessions:
            cls.init_session(name = name, **kwargs)
        return cls.sessions[name]


