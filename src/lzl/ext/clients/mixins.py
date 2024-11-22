from __future__ import annotations

"""
Cachify Client Mixin
"""

import os
import abc
import time
import asyncio
import subprocess
from lzl import load
from lzl.types import eproperty, Literal
from kvdb.io import cachify as _cachify
from .utils import create_cachify_build_name_func, get_user_agent, get_default_headers, http_retry_wrapper
from typing import Optional, Type, TypeVar, Union, Set, List, Any, Dict, Callable, Awaitable, overload, TYPE_CHECKING

if TYPE_CHECKING:
    from lzl.logging import Logger
    from lzo.types.base import RegisteredSettings, BaseModel
    from lzl.pool import ThreadPool
    from .base import DataSchema, ResultSchema

if load.TYPE_CHECKING:
    import aiohttpx
    from aiohttpx import Response, Client as HTTPClient
else:
    aiohttpx = load.LazyLoad("aiohttpx", install_missing=True)


ResponseDataType = Literal['json', 'text', 'bytes']
ResponseType = Optional[Union[ResponseDataType, Type['ResultSchema'], Type['BaseModel'], str]]
ResponseT = Union[str, bytes, Dict[str, Any], List[Any], 'ResultSchema', List['ResultSchema'], Dict[str, 'ResultSchema'], List[Dict[str, 'ResultSchema']]]


cachify = _cachify.create_context()

class CachifyClientMixin(abc.ABC):
    """
    Cachify Client Mixin
    """

    cachify_enabled: Optional[bool] = True
    cachify_ttl: Optional[int] = None
    cachify_shared_global: Optional[bool] = False
    
    if TYPE_CHECKING:
        name: str
        settings: RegisteredSettings

        serialization: Optional[str] = 'json'
        serialization_compression: Optional[str] = 'zstd'
        serialization_compression_level: Optional[int] = 19 # 6 for default (lz4, zlib) 19 for zstd


    """
    Cachify Validation Methods
    """

    def cachify_validator_is_not_cachable(self, *args, cachable: Optional[bool] = True, **kwargs) -> bool:
        """
        Checks if the function is not cachable
        """
        from kvdb.io.cachify.helpers import is_not_cachable
        return is_not_cachable(*args, cachable = cachable, **kwargs)
    
    def cachify_validator_is_disabled(self, *args, disabled: Optional[bool] = None, **kwargs) -> bool:
        """
        Checks if the function is disabled
        """
        from kvdb.io.cachify.helpers import is_disabled
        return is_disabled(*args, disabled = disabled, **kwargs)
    
    def cachify_validator_is_overwrite(self, *args, overwrite: Optional[bool] = None, **kwargs) -> bool:
        """
        Checks if the function is overwrite
        """
        from kvdb.io.cachify.helpers import is_overwrite
        return is_overwrite(*args, overwrite = overwrite, **kwargs)
    
    def cachify_get_exclude_keys(self, func: str, **kwargs) -> List[str]:
        """
        Gets the exclude keys
        """
        return None
    
    def cachify_get_name_builder_kwargs(self, func: str, **kwargs) -> Dict[str, Any]:
        """
        Gets the name builder kwargs
        """
        return {}
    
    def cachify_get_extra_serialization_kwargs(self, func: str, **kwargs) -> Dict[str, Any]:
        """
        Gets the extra serialization kwargs
        """
        return {}

    def cachify_create_base_name(self, func: str, **kwargs) -> str:
        """
        Creates the base name
        """
        return f'{self.settings.ctx.module_name}.{self.name}' if self.cachify_shared_global  else \
            f'{self.settings.ctx.module_name}.{self.settings.app_env.name}.{self.name}'
    

    def validate_cachify(self, func: str, **kwargs) -> Dict[str, Any]:
        """
        Validates the cachify function
        """
        if not self.cachify_enabled: return None
        base_name = self.cachify_create_base_name(func, **kwargs)
        if 'name' not in kwargs: kwargs['name'] = create_cachify_build_name_func(
            base_name = base_name,
            **self.cachify_get_name_builder_kwargs(func, **kwargs),
        )
        if 'ttl' not in kwargs: kwargs['ttl'] = self.cachify_ttl
        if 'serializer' not in kwargs and 'encoder' not in kwargs and 'decoder' not in kwargs:
            kwargs['serializer'] = self.serialization
            kwargs['serializer_kwargs'] = {
                'compression': self.serialization_compression,
                'compression_level': self.serialization_compression_level,
                'raise_errors': True,
                **self.cachify_get_extra_serialization_kwargs(func, **kwargs),
            }
        if 'verbosity' not in kwargs and self.settings.is_local_env: kwargs['verbosity'] = 2
        kwargs['disabled'] = self.cachify_validator_is_not_cachable
        kwargs['overwrite_if'] = self.cachify_validator_is_overwrite
        kwargs['disabled_if'] = self.cachify_validator_is_disabled
        if exclude_keys := self.cachify_get_exclude_keys(func, **kwargs):
            kwargs['exclude_keys'] = exclude_keys
        kwargs['exclude_null'] = True
        return kwargs
    

class CachifyHTTPClientMixin(CachifyClientMixin):

    default_cachable: Optional[bool] = True


    def cachify_validator_is_not_cachable(self, *args, cachable: Optional[bool] = None, **kwargs) -> bool:
        """
        Checks if the function is not cachable
        """
        if cachable is None: cachable = self.default_cachable
        return super().cachify_validator_is_not_cachable(*args, cachable = cachable, **kwargs)


    def cachify_validator_is_disabled(self, *args, disable_cache: Optional[bool] = None, **kwargs) -> bool:
        """
        Checks if the function is disabled
        """
        return disable_cache
    
    def cachify_validator_is_overwrite(self, *args, overwrite_cache: Optional[bool] = None, **kwargs) -> bool:
        """
        Checks if the function is overwrite
        """
        return overwrite_cache

    def cachify_get_exclude_keys(self, func: str, **kwargs) -> List[str]:
        """
        Gets the exclude keys
        """
        return [
            'background',
            'callback',
            'retryable',
            'retry_limit',
            'validate_url',
            'cachable',
            'disable_cache',
            'overwrite_cache',
            'verify',
        ]
    
    def cachify_get_name_builder_kwargs(self, func: str, **kwargs) -> Dict[str, Any]:
        """
        Gets the name builder kwargs
        """
        return {
            'include_http_methods': True,
            'special_names': ['pdftotext', 'csx'],
        }



class BaseHTTPClientMixin(abc.ABC):
    """
    The Base HTTP Client Mixin
    """

    http_timeout: Optional[float] = None
    http_errors_verbose: Optional[bool] = True
    http_errors_truncate_length: Optional[int] = 1000

    default_endpoint: Optional[str] = None
    default_headers: Optional[Dict[str, Any]] = None
    default_response_type: ResponseType = 'json'

    default_retryable: Optional[bool] = False
    default_retryable_limit: Optional[int] = 3

    _extra: Dict[str, Any] = {}

    if TYPE_CHECKING:
        settings: RegisteredSettings
        pooler: ThreadPool
        schemas: Dict[str, Union[Type['DataSchema'], Type['ResultSchema']]]
        logger: Logger
        autologger: Logger


    @eproperty
    def endpoint(self) -> str:
        """
        Returns the endpoint

        - Override this to add custom endpoints
        """
        return self.default_endpoint
    
    @eproperty
    def headers(self) -> Dict[str, Any]:
        """
        Returns the headers

        - Override this to add custom headers
        """
        base_headers = get_default_headers()
        if self.default_headers: base_headers.update(self.default_headers)
        return base_headers
    
    @eproperty
    def http_client_kwargs(self) -> Dict[str, Any]:
        """
        Returns the http client kwargs

        - Override this to add custom kwargs
        """
        return {}
    
    @eproperty
    def http_client_timeout(self) -> Optional[float]:
        """
        Returns the http client timeout
        """
        if hasattr(self.settings, 'clients') and hasattr(self.settings.clients, 'http_pool'):
            return self.http_timeout or self.settings.clients.http_pool.default_timeout
        return self.http_timeout or 60
    
    @eproperty
    def http_client_limits(self) -> Dict[str, int]:
        """
        Returns the http client limits
        """
        if hasattr(self.settings, 'clients') and hasattr(self.settings.clients, 'http_pool'):
            return {
                'max_connections': self.settings.clients.http_pool.max_connections,
                'max_keepalive_connections': self.settings.clients.http_pool.max_keepalive_connections,
                'keepalive_expiry': self.settings.clients.http_pool.keepalive_expiry,
            }
    
    def wrap_retryable_method(
        self,
        func: Union[Callable[..., Any], str],
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
    ) -> Union[Callable[..., 'Response'], Callable[..., Awaitable['Response']]]:
        """
        Wraps a retryable method
        """
        if isinstance(func, str): func = getattr(self.api, func)
        if retryable is None: retryable = self.default_retryable
        if not retryable: return func
        if retry_limit is None: retry_limit = self.default_retryable_limit
        return http_retry_wrapper(max_tries = retry_limit + 1)(func)
    
    def generate_headers(self, browser: Optional[str] = 'chrome', **kwargs) -> Dict[str, str]:
        """
        Generates the headers
        """
        return get_default_headers(browser = browser, **kwargs)

    def configure_http_client(self, *args, **kwargs) -> 'HTTPClient':
        """
        Configures the HTTP Client
        """
        limits = aiohttpx.Limits(**self.http_client_limits)
        return aiohttpx.Client(
            base_url = self.endpoint,
            timeout = self.http_client_timeout,
            limits = limits,
            headers = self.headers,
            verify = False,
            **self.http_client_kwargs, 
        )


    @property
    def api(self) -> 'HTTPClient':
        """
        Returns the API Client
        """
        if self._extra.get('api') is None:
            self._extra['api'] = self.configure_http_client()
        return self._extra['api']
    
    def reset_api(self):
        """
        Resets the API Client
        """
        if self._extra.get('api') is not None:
            self._extra['api'].close()
            self._extra['api'] = None
    
    async def areset_api(self):
        """
        Resets the API Client
        """
        if self._extra.get('api') is not None:
            await self._extra['api'].aclose()
            self._extra['api'] = None

    """
    Basic HTTP Methods
    """

    def _validate_url(self, url: str) -> Union[bool, str]:
        """
        Quickly validates a URL
        """
        try:
            response = self.api.head(url, follow_redirects = True)
            try:
                response.raise_for_status()
                return True
            except Exception as e:
                return f'[{response.status_code}]: {response.text}'
        except Exception as e:
            return f'[{type(e)}]: {str(e)}'
        
    
    def _fetch_content_type(self, url: str) -> Optional[str]:
        """
        Fetches the content type
        """
        try:
            response = self.api.head(url, follow_redirects = True)
            return response.headers.get('content-type')
        except Exception as e:
            return None

    def _get_(self, url: str, **kwargs) -> 'Response':
        """
        Makes a GET request
        """
        return self.api.get(url, **kwargs)
    
    def _post_(self, url: str, **kwargs) -> 'Response':
        """
        Makes a POST request
        """
        return self.api.post(url, **kwargs)
    

    async def _avalidate_url(self, url: str) -> Union[bool, str]:
        """
        Quickly validates a URL
        """
        try:
            response = await self.api.async_head(url, follow_redirects = True)
            try:
                response.raise_for_status()
                return True
            except Exception as e:
                return f'[{response.status_code}] {response.text}'
        except Exception as e:
            return f'[{type(e)}]: {str(e)}'
        
    async def _afetch_content_type(self, url: str) -> Optional[str]:
        """
        Fetches the content type
        """
        try:
            response = await self.api.async_head(url, follow_redirects = True)
            return response.headers.get('content-type')
        except Exception as e:
            return None

    async def _aget_(self, url: str, **kwargs) -> 'Response':
        """
        Makes a GET request
        """
        return await self.api.async_get(url, **kwargs)
    
    async def _apost_(self, url: str, **kwargs) -> 'Response':
        """
        Makes a POST request
        """
        return await self.api.async_post(url, **kwargs)
    
    def handle_response(
        self, 
        response: 'Response', 
        response_type: ResponseType = None,
    ) -> ResponseT:
        """
        Handle the response
        """
        try:
            response.raise_for_status()
            if response_type is None: response_type = self.default_response_type
            if not response_type: return response
            if not isinstance(response_type, str):
                # Must be a model
                return response_type.model_validate_json(response.text)
                # return response_type.model_validate(response.json())
            response_type = str(response_type).lower()
            if response_type == 'raw': return response
            if response_type == 'json': return response.json()
            if response_type == 'text': return response.text
            if response_type == 'bytes': return response.content
            if response_type in self.schemas:
                return self.schemas[response_type].model_validate_json(response.text)
            else:
                raise ValueError(f'Invalid Response Type: {response_type}')
        except aiohttpx.HTTPStatusError as e:
            if not self.http_errors_verbose or self.settings.is_production_env:
                self.logger.warning(f'[{response.status_code} - {e.request.url}]')
            else:
                response_text = response.text
                if self.http_errors_truncate_length:
                    response_text = response_text[:self.http_errors_truncate_length]
                self.logger.error(f'[{response.status_code} - {e.request.url}] {response_text}')
        except Exception as e:
            if not self.http_errors_verbose:
                self.logger.error(f'[{type(e)}] {str(e)}')
            else:
                response_text = response.text
                if self.http_errors_truncate_length:
                    response_text = response_text[:self.http_errors_truncate_length]
                self.logger.trace(f'Error in response: {response_text}', e)
            raise e
    
    """
    Enhanced HTTP Methods
    """

    def _get(
        self,
        url: str,
        *args,
        response_type: ResponseType = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        """
        Creates a GET Request and returns a `ReturnTypeT`
        """
        get_func = self.wrap_retryable_method(self._get_, retryable = retryable, retry_limit = retry_limit)
        response = get_func(url, *args, **kwargs)
        return self.handle_response(response, response_type = response_type)
    
    def _post(
        self,
        url: str,
        *args,
        response_type: ResponseType = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        """
        Creates a POST Request and returns a `ReturnTypeT`
        """
        post_func = self.wrap_retryable_method(self._post_, retryable = retryable, retry_limit = retry_limit)
        response = post_func(url, *args, **kwargs)
        return self.handle_response(response, response_type = response_type)
    
    async def _aget(
        self,
        url: str,
        *args,
        response_type: ResponseType = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        """
        Creates a GET Request and returns a `ReturnTypeT`
        """
        get_func = self.wrap_retryable_method(self._aget_, retryable = retryable, retry_limit = retry_limit)
        response = await get_func(url, *args, **kwargs)
        return self.handle_response(response, response_type = response_type)
    
    async def _apost(
        self,
        url: str,
        *args,
        response_type: ResponseType = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        """
        Creates a POST Request and returns a `ReturnTypeT`
        """
        post_func = self.wrap_retryable_method(self._apost_, retryable = retryable, retry_limit = retry_limit)
        response = await post_func(url, *args, **kwargs)
        return self.handle_response(response, response_type = response_type)
    

    """
    Extended Functions
    """

    @eproperty
    def google_csx_base_url(self) -> Optional[str]:
        """
        Returns the Google CSX Base URL
        """
        return 'https://www.googleapis.com/customsearch/v1'
    

    @eproperty
    def google_csx_api_key(self) -> str:
        """
        Override this to add a Google CSX API Key
        """
        if hasattr(self.settings, 'clients') and hasattr(self.settings.clients, 'http_pool'):
            return getattr(self.settings.clients.http_pool, 'google_csx_api_key', None)
        return None
    
    @eproperty
    def google_csx_id(self) -> str:
        """
        Override this to add a Google CSX ID
        """
        if hasattr(self.settings, 'clients') and hasattr(self.settings.clients, 'http_pool'):
            return getattr(self.settings.clients.http_pool, 'google_csx_id', None)
        return None
    
    @eproperty
    def pdftotext_enabled(self) -> bool:
        """
        Returns whether pdftotext is enabled
        """
        try:
            subprocess.check_output(['which', 'pdftotext'])
            return True
        except Exception as e:
            return False
        
    @eproperty
    def pdftotext_cmd_args(self) -> str:
        """
        Returns the pdftotext command arguments
        """
        return '-layout -nopgbrk -eol unix -colspacing 0.7 -y 58 -x 0 -H 741 -W 596 - -'
        
    
    def _get_pdftotext_(
        self,
        url: str,
        validate_url: Optional[bool] = False,
        raise_errors: Optional[bool] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Transform a PDF File to Text directly from URL
        """
        if validate_url:
            validate_result = self._validate_url(url)
            if validate_result != True:
                if raise_errors: raise ValueError(f'Invalid URL: {url}. {validate_result}')
                self.logger.error(f'Invalid URL: {url}. {validate_result}')
                return None
        
        cmd = f'curl -s {url} | pdftotext {self.pdftotext_cmd_args}'
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate()
            stdout = stdout.decode('utf-8')
            return stdout
        except Exception as e:
            stderr = stderr.decode('utf-8')
            self.logger.error(f'Error in pdftotext: {stderr}: {e}')
            if raise_errors: raise e
            return None
        
    def _get_pdftotext(
        self,
        url: str,
        validate_url: Optional[bool] = False,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        raise_errors: Optional[bool] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Transform a PDF File to Text directly from URL
        """
        if not self.pdftotext_enabled:
            raise ValueError('pdftotext is not enabled. Please install pdftotext')
        get_func = self.wrap_retryable_method(self._get_pdftotext_, retryable = retryable, retry_limit = retry_limit)
        return get_func(url, validate_url = validate_url, raise_errors = raise_errors, **kwargs)

    async def _aget_pdftotext_(
        self,
        url: str,
        validate_url: Optional[bool] = False,
        raise_errors: Optional[bool] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Transform a PDF File to Text directly from URL
        """
        if validate_url:
            validate_result = await self._avalidate_url(url)
            if validate_result != True:
                if raise_errors: raise ValueError(f'Invalid URL: {url}. {validate_result}')
                self.logger.error(f'Invalid URL: {url}. {validate_result}')
                return None
        cmd = f'curl -s {url} | pdftotext {self.pdftotext_cmd_args}'
        process = await asyncio.subprocess.create_subprocess_shell(cmd, shell=True, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await process.communicate()
            stdout = stdout.decode('utf-8')
            return stdout
        except Exception as e:
            stderr = stderr.decode('utf-8')
            self.logger.error(f'Error in pdftotext: {stderr}: {e}')
            if raise_errors: raise e
            return None
        
    async def _aget_pdftotext(
        self,
        url: str,
        validate_url: Optional[bool] = False,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        raise_errors: Optional[bool] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Transform a PDF File to Text directly from URL
        """
        if not self.pdftotext_enabled:
            raise ValueError('pdftotext is not enabled. Please install pdftotext')
        get_func = self.wrap_retryable_method(self._aget_pdftotext_, retryable = retryable, retry_limit = retry_limit)
        return await get_func(url, validate_url = validate_url, raise_errors = raise_errors, **kwargs)


    """
    Google CSX Methods
    """

    def _get_csx_(
        self,
        *args,
        response_type: ResponseType = 'json',
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        """
        Returns the Google CSX Results
        """
        url = self.google_csx_base_url
        get_func = self.wrap_retryable_method(self._get_, retryable = retryable, retry_limit = retry_limit)
        response = get_func(url, *args, **kwargs)
        if response.status_code == 429:
            self.logger.warning(f'[{response.status_code}] Rate Limit Exceeded. Retrying after a bit', colored = True, prefix = 'GoogleCSX')    
            attempts = 1
            while response.status_code == 429:
                time.sleep(10.0 * attempts)
                response = get_func(url, *args, **kwargs)
                if response.status_code != 429: 
                    self.autologger.info(f'[{response.status_code}] Completed Retry after {attempts} Attempts', colored = True, prefix = 'GoogleCSX')
                    break
                attempts += 1
        return self.handle_response(response, response_type = response_type)

    async def _aget_csx_(
        self,
        *args,
        response_type: ResponseType = 'json',
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        """
        Creates a GET Request and returns a `ReturnTypeT` for Google CSX to handle rate limiting
        """
        get_func = self.wrap_retryable_method(self._aget_, retryable = retryable, retry_limit = retry_limit)
        url = self.google_csx_base_url
        response = await get_func(url, *args, **kwargs)
        if response.status_code == 429:
            self.logger.warning(f'[{response.status_code}] Rate Limit Exceeded. Retrying after a bit', colored = True, prefix = 'GoogleCSX')    
            attempts = 1
            while response.status_code == 429:
                await asyncio.sleep(10.0 * attempts)
                response = await get_func(url, *args, **kwargs)
                if response.status_code != 429: 
                    self.autologger.info(f'[{response.status_code}] Completed Retry after {attempts} Attempts', colored = True, prefix = 'GoogleCSX')
                    break
                attempts += 1
        return self.handle_response(response, response_type = response_type)
    


"""
Browser Mixin
"""

if TYPE_CHECKING:
    from playwright.sync_api import (
        PlaywrightContextManager, 
        Playwright, 
        Browser as SyncBrowser,
        BrowserType as SyncBrowserType
    )
    from playwright.async_api import (
        PlaywrightContextManager as AsyncPlaywrightContextManager, 
        Playwright as AsyncPlaywright,
        Browser as AsyncBrowser,
        BrowserType as AsyncBrowserType
    )

class BrowserMixin(abc.ABC):
    """
    The Browser Client Mixin
    """

    initialized: bool = False
    default_browser_type: Optional[str] = 'chromium'
    
    _extra: Dict[str, Any] = {}

    if TYPE_CHECKING:
        settings: RegisteredSettings
        logger: Logger
        pooler: ThreadPool
    
    @eproperty
    def downloads_path(self) -> Optional[str]:
        """
        Returns the downloads path
        """
        if hasattr(self.settings, 'module_path'):
            return self.settings.module_path.joinpath('data').as_posix()
        return os.getcwd()

    @eproperty
    def browser_launch_config(self) -> Dict[str, Any]:
        """
        Returns the browser launch config
        
        - Can be overridden by subclasses
        """
        return {
            'headless': True,
            'downloads_path': self.downloads_path,
        }


    @eproperty
    def initializing(self) -> bool:
        """
        Returns whether the client is initializing
        """
        return self._extra.get('initializing', False)
    
    @eproperty
    def cm(self) -> 'PlaywrightContextManager':
        """
        Returns the Playwright context manager
        """
        from playwright.sync_api import sync_playwright
        return sync_playwright()
    
    @eproperty
    def client(self) -> 'Playwright':
        """
        Returns the Playwright instance
        """
        return self.cm.start()
    
    @eproperty
    def browser(self) -> 'SyncBrowser':
        """
        Returns the browser instance
        """
        browser_t: 'SyncBrowserType' = getattr(self.client, self.default_browser_type)
        return browser_t.launch(**self.browser_launch_config)

    
    """
    Async Methods
    """

    @eproperty
    def acm(self) -> 'AsyncPlaywrightContextManager':
        """
        Returns the Playwright async context manager
        """
        from playwright.async_api import async_playwright
        return async_playwright()
    
    @property
    def aclient(self) -> 'AsyncPlaywright':
        """
        Returns the Playwright instance
        """
        if 'aclient' not in self._extra:
            raise RuntimeError('AsyncPlaywright not initialized. Initialize with Browser.ainit()')
        return self._extra['aclient']
    
    @aclient.setter
    def aclient(self, value: 'AsyncPlaywright'):
        """
        Sets the Playwright instance
        """
        self._extra['aclient'] = value
    
    @property
    def abrowser(self) -> 'AsyncBrowser':
        """
        Returns the browser instance
        """
        if 'abrowser' not in self._extra:
            raise RuntimeError('AsyncBrowser not initialized. Initialize with Browser.ainit()')
        return self._extra['abrowser']
    
    @abrowser.setter
    def abrowser(self, value: 'AsyncBrowser'):
        """
        Sets the browser instance
        """
        self._extra['abrowser'] = value


    def _set_aclient(self, task: asyncio.Task):
        """
        Sets the AsyncPlaywright instance
        """
        self.logger.info('Setting AsyncPlaywright')
        self.aclient = task.result()

    def _set_abrowser(self, task: asyncio.Task):
        """
        Sets the AsyncBrowser instance
        """
        self.logger.info('Setting AsyncBrowser')
        self.abrowser = task.result()

    async def ainit(self):
        """
        Initializes the browser
        """
        if self.initialized: return
        self.logger.info('Initializing Browser')
        self.initializing = True
        if 'aclient' not in self._extra:
            self.aclient = await self.acm.start()
        if 'abrowser' not in self._extra:
            browser_t: 'AsyncBrowserType' = getattr(self.aclient, self.default_browser_type)
            self.abrowser = await browser_t.launch(**self.browser_launch_config)
        self.initialized = True
        self.initializing = False
        return self
    

    def close(self):
        """
        Closes the browser
        """
        if 'abrowser' in self._extra:
            self.pooler.create_background(self.abrowser.close)
            _ = self._extra.pop('abrowser')
        if 'browser' in self._extra:
            self.browser.close()
            _ = self._extra.pop('browser')
        if 'aclient' in self._extra:
            self.pooler.create_background(self.aclient.stop)
            _ = self._extra.pop('aclient')
        if 'client' in self._extra:
            self.client.stop()
            _ = self._extra.pop('client')
        _ = self._extra.pop('cm', None)
        _ = self._extra.pop('acm', None)
        self.initialized = False
    
    async def aclose(self):
        """
        Closes the browser
        """
        if 'abrowser' in self._extra:
            await self.abrowser.close()
            _ = self._extra.pop('abrowser')
        if 'browser' in self._extra:
            self.browser.close()
            _ = self._extra.pop('browser')
        if 'aclient' in self._extra:
            await self.aclient.stop()
            _ = self._extra.pop('aclient')
        if 'client' in self._extra:
            await self.client.stop()
            _ = self._extra.pop('client')
        _ = self._extra.pop('cm', None)
        _ = self._extra.pop('acm', None)
        self.initialized = False
    