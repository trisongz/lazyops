from __future__ import annotations

"""
Base API Client and HTTP Pool Client
"""

import asyncio
import random
import inspect
import aiohttpx
import functools
import subprocess
from pydantic import BaseModel
from urllib.parse import urlparse
from lazyops.libs.proxyobj import ProxyObject, proxied
from .base import BaseGlobalClient, cachify
from .utils import aget_root_domain, get_user_agent, http_retry_wrapper

from typing import Optional, Type, TypeVar, Literal, Union, Set, Awaitable, Any, Dict, List, Callable, overload, TYPE_CHECKING

if TYPE_CHECKING:
    from kvdb import KVDBSession, SerializerT
    from docx.document import Document


ReturnType = Literal['json', 'text', 'bytes']
ReturnModelT = TypeVar('ReturnModelT', bound = BaseModel)
ReturnTypeT = TypeVar('ReturnTypeT', bound = Union[str, bytes, Dict[str, Any], List[Any], BaseModel, List[BaseModel], Dict[str, BaseModel], List[Dict[str, BaseModel]]])


@cachify.register_object()
class BaseAPIClient(BaseGlobalClient):

    name: Optional[str] = 'api'
    verbose_errors: Optional[bool] = True
    http_timeout: Optional[float] = None
    http_errors_verbose: Optional[bool] = True
    http_errors_truncate_length: Optional[int] = 1000

    _endpoint: Optional[str] = None
    _headers: Optional[Dict[str, Any]] = None
    _api: Optional[aiohttpx.Client] = None


    @property
    def endpoint(self) -> str:
        """
        Returns the endpoint

        - Override this to add custom endpoints
        """
        return self._endpoint
    
    def get_user_agent(self, *args, **kwargs) -> str:
        """
        Returns the user agent
        """
        return get_user_agent(*args, **kwargs)
    
    @property
    def headers(self) -> Dict[str, Any]:
        """
        Returns the headers

        - Override this to add custom headers
        """
        return self._headers or {}
    
    @property
    def api_client_kwargs(self) -> Dict[str, Any]:
        """
        Returns the api client kwargs

        - Override this to add custom kwargs
        """
        return {}
    

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
    
    def configure_api_client(self, *args, **kwargs) -> aiohttpx.Client:
        """
        Configures the API Client
        """
        if hasattr(self.settings, 'clients') and hasattr(self.settings.clients, 'http_pool'):
            limits = aiohttpx.Limits(
                max_connections = self.settings.clients.http_pool.max_connections,
                max_keepalive_connections = self.settings.clients.http_pool.max_keepalive_connections,
                keepalive_expiry = self.settings.clients.http_pool.keepalive_expiry,
            )
            timeout = self.http_timeout or self.settings.clients.http_pool.default_timeout
        else:
            limits = aiohttpx.Limits(
                max_connections = 100,
                max_keepalive_connections = 20,
                keepalive_expiry = 60,
            )
            timeout = self.http_timeout or 60
        return aiohttpx.Client(
            base_url = self.endpoint,
            limits = limits,
            timeout = timeout,
            headers = self.headers,
            verify = False,
            **self.api_client_kwargs,
        )
    

    @property
    def api(self) -> aiohttpx.Client:
        """
        Returns the API Client
        """
        if self._api is None:
            self._api = self.configure_api_client()
        return self._api
    

    async def areset_api(self):
        """
        Resets the api client
        """
        if self._api:
            await self._api.aclose()
            self._api = None

    def wrap_retryable_method(
        self,
        func: Callable[..., Any],
        retry_limit: Optional[int] = 3,
    ) -> Union[Callable[..., aiohttpx.Response], Callable[..., Awaitable[aiohttpx.Response]]]:
        """
        Wraps a retryable method
        """
        if isinstance(func, str): func = getattr(self.api, func)
        return http_retry_wrapper(max_tries = retry_limit + 1)(func)
    
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
    

    def cachify_get_name_builder_kwargs(self, func: str, **kwargs) -> Dict[str, Any]:
        """
        Gets the name builder kwargs
        """
        return {
            'include_http_methods': True,
        }

    """
    Modified HTTP Methods
    """

    @overload
    def get(
        self, 
        url: str, 
        *args,
        return_type: Optional[Union[ReturnType, ReturnModelT]] = 'json', 
        cachable: Optional[bool] = True,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> ReturnTypeT:
        ...

    @cachify.register()
    def get(
        self, 
        url: str, 
        *args,
        return_type: Optional[Union[ReturnType, ReturnModelT]] = 'json', 
        cachable: Optional[bool] = True,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> ReturnTypeT:
        """
        Creates a GET Request and returns a `ReturnTypeT`
        """
        if background:
            return self.pooler.create_background(
                self._get,
                url = url,
                *args,
                return_type = return_type,
                task_callback = callback,
                retryable = retryable,
                retry_limit = retry_limit,
                **kwargs
            )
        return self._get(url = url, *args, return_type = return_type, retryable = retryable, retry_limit = retry_limit, **kwargs)
    
    @cachify.register()
    def post(
        self, 
        url: str, 
        *args,
        return_type: Optional[Union[ReturnType, ReturnModelT]] = 'json', 
        cachable: Optional[bool] = True,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> ReturnTypeT:
        """
        Creates a POST Request and returns a `ReturnTypeT`
        """
        if background:
            return self.pooler.create_background(
                self._post,
                url = url,
                *args,
                return_type = return_type,
                task_callback = callback,
                retryable = retryable,
                retry_limit = retry_limit,
                **kwargs
            )
        return self._post(url = url, *args, return_type = return_type, retryable = retryable, retry_limit = retry_limit, **kwargs)
    
    @overload
    async def aget(
        self,
        url: str, 
        *args,
        return_type: Optional[Union[ReturnType, ReturnModelT]] = 'json', 
        cachable: Optional[bool] = True,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> ReturnTypeT:
        """
        Creates a GET Request and returns a `ReturnTypeT`
        """

    @cachify.register()
    async def aget(
        self, 
        url: str, 
        *args,
        return_type: Optional[Union[ReturnType, ReturnModelT]] = 'json', 
        cachable: Optional[bool] = True,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> ReturnTypeT:
        """
        Creates a GET Request and returns a `ReturnTypeT`
        """
        if background:
            return self.pooler.create_background(
                self._aget,
                url = url,
                *args,
                return_type = return_type,
                task_callback = callback,
                retryable = retryable,
                retry_limit = retry_limit,
                **kwargs
            )
        return await self._aget(url = url, *args, return_type = return_type, retryable = retryable, retry_limit = retry_limit,  **kwargs)
    
    @cachify.register()
    async def apost(
        self, 
        url: str, 
        *args,
        return_type: Optional[Union[ReturnType, ReturnModelT]] = 'json', 
        cachable: Optional[bool] = True,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> ReturnTypeT:
        """
        Creates a POST Request and returns a `ReturnTypeT`
        """
        # base_post = self._apost_cachable if cachable else self._apost
        if background:
            return self.pooler.create_background(
                self._apost,
                url = url,
                *args,
                return_type = return_type,
                task_callback = callback,
                retryable = retryable,
                retry_limit = retry_limit,
                **kwargs
            )
        return await self._apost(url = url, *args, return_type = return_type, retryable = retryable, retry_limit = retry_limit, **kwargs)
    


    """
    Basic HTTP Methods
    """

    def _get_(self, url: str, **kwargs) -> aiohttpx.Response:
        """
        Makes a GET request
        """
        return self.api.get(url, **kwargs)
    
    def _post_(self, url: str, **kwargs) -> aiohttpx.Response:
        """
        Makes a POST request
        """
        return self.api.post(url, **kwargs)
    
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
        
    async def _aget_(self, url: str, **kwargs) -> aiohttpx.Response:
        """
        Makes a GET request
        """
        return await self.api.async_get(url, **kwargs)
    
    async def _apost_(self, url: str, **kwargs) -> aiohttpx.Response:
        """
        Makes a POST request
        """
        return await self.api.async_post(url, **kwargs)
    
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

    """
    Enhanced HTTP Methods
    """

    def _get(
        self,
        url: str,
        *args,
        return_type: Optional[Union[ReturnType, ReturnModelT]] = 'json',
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> ReturnTypeT:
        """
        Creates a GET Request and returns a `ReturnTypeT`
        """
        get_func = self._get_
        if retryable: get_func = http_retry_wrapper(max_tries = retry_limit + 1)(get_func)
        response = get_func(url, *args, **kwargs)
        return self.handle_response(response, return_type = return_type)
    
    def _post(
        self,
        url: str,
        *args,
        return_type: Optional[Union[ReturnType, ReturnModelT]] = 'json',
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> ReturnTypeT:
        """
        Creates a POST Request and returns a `ReturnTypeT`
        """
        post_func = self._post_
        if retryable: post_func = http_retry_wrapper(max_tries = retry_limit + 1)(post_func)
        response = post_func(url, *args, **kwargs)
        return self.handle_response(response, return_type = return_type)


    async def _aget(
        self,
        url: str,
        *args,
        return_type: Optional[Union[ReturnType, ReturnModelT]] = 'json',
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> ReturnTypeT:
        """
        Creates a GET Request and returns a `ReturnTypeT`
        """
        get_func = self._aget_
        if retryable: get_func = http_retry_wrapper(max_tries = retry_limit + 1)(get_func)
        response = await get_func(url, *args, **kwargs)
        return self.handle_response(response, return_type = return_type)

    
    async def _apost(
        self,
        url: str,
        *args,
        return_type: Optional[Union[ReturnType, ReturnModelT]] = 'json',
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> ReturnTypeT:
        """
        Creates a POST Request and returns a `ReturnTypeT`
        """
        post_func = self._apost_
        if retryable: post_func = http_retry_wrapper(max_tries = retry_limit + 1)(post_func)
        response = await post_func(url, *args, **kwargs)
        return self.handle_response(response, return_type = return_type)
    

    def handle_response(
        self, 
        response: aiohttpx.Response, 
        return_type: Optional[Union[ReturnType, ReturnModelT]] = 'json',
    ) -> Union[ReturnModelT, Dict[str, Any]]:
        """
        Handle the response
        """
        try:
            response.raise_for_status()
            if not return_type: return response
            if not isinstance(return_type, str):
                # Must be a model
                return return_type.model_validate(response.json())
            return_type = str(return_type).lower()
            if return_type == 'json':
                return response.json()
            if return_type == 'text':
                return response.text
            if return_type == 'bytes':
                return response.content
            else:
                raise ValueError(f'Invalid return type: {return_type}')
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
    

class HTTPPoolClient(BaseAPIClient):
    """
    This is a Global HTTP API Client that can be used by any client
    """
    name: Optional[str] = 'http'
    cachify_ttl: Optional[int] = 60 * 60 * 24 * 7 # 1 Week

    google_csx_base_url: Optional[str] = 'https://www.googleapis.com/customsearch/v1'

    # Extended Methods
    _pdftotext_enabled: Optional[bool] = None
    _doctotext_enabled: Optional[bool] = None

    _google_csx_api_key: Optional[str] = None
    _google_csx_id: Optional[str] = None


    @property
    def google_csx_api_key(self) -> str:
        """
        Override this to add a Google CSX API Key
        """
        if self._google_csx_api_key is None:
            if hasattr(self.settings, 'clients') and hasattr(self.settings.clients, 'http_pool'):
                self._google_csx_api_key = getattr(self.settings.clients.http_pool, 'google_csx_api_key', None)
        return self._google_csx_api_key
    
    @property
    def google_csx_id(self) -> str:
        """
        Override this to add a Google CSX ID
        """
        if self._google_csx_id is None:
            if hasattr(self.settings, 'clients') and hasattr(self.settings.clients, 'http_pool'):
                self._google_csx_id = getattr(self.settings.clients.http_pool, 'google_csx_id', None)
        return self._google_csx_id
    

    @property
    def pdftotext_enabled(self) -> bool:
        """
        Returns whether pdftotext is enabled
        """
        if self._pdftotext_enabled is None:
            try:
                subprocess.check_output(['which', 'pdftotext'])
                self._pdftotext_enabled = True
            except Exception as e:
                self._pdftotext_enabled = False
        return self._pdftotext_enabled

    
    def cachify_get_name_builder_kwargs(self, func: str, **kwargs) -> Dict[str, Any]:
        """
        Gets the name builder kwargs
        """
        return {
            'include_http_methods': True,
            'special_names': ['pdftotext', 'csx'],
        }

    def __get_pdftotext(
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
        
        cmd = f'curl -s {url} | pdftotext -layout -nopgbrk -eol unix -colspacing 0.7 -y 58 -x 0 -H 741 -W 596 - -'
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
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        raise_errors: Optional[bool] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Transform a PDF File to Text directly from URL
        """
        if not self.pdftotext_enabled:
            raise ValueError('pdftotext is not enabled. Please install pdftotext')
        get_func = self.__get_pdftotext
        if retryable: get_func = http_retry_wrapper(max_tries = retry_limit + 1)(get_func)
        return get_func(url, raise_errors = raise_errors, **kwargs)


    async def __aget_pdftotext(
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
        cmd = f'curl -s {url} | pdftotext -layout -nopgbrk -eol unix -colspacing 0.7 -y 58 -x 0 -H 741 -W 596 - -'
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
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        raise_errors: Optional[bool] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Transform a PDF File to Text directly from URL
        """
        if not self.pdftotext_enabled:
            raise ValueError('pdftotext is not enabled. Please install pdftotext')
        get_func = self.__aget_pdftotext
        if retryable: get_func = http_retry_wrapper(max_tries = retry_limit + 1)(get_func)
        return await get_func(url, raise_errors = raise_errors, **kwargs)

    @cachify.register()
    def get_pdftotext(
        self,
        url: str,
        cachable: Optional[bool] = True,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> Optional[str]:
        """
        Transform a PDF File to Text directly from URL
        """
        return self._get_pdftotext(url, retryable = retryable, retry_limit = retry_limit, **kwargs)

    @cachify.register()
    async def aget_pdftotext(
        self,
        url: str,
        cachable: Optional[bool] = True,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> Optional[str]:
        """
        Transform a PDF File to Text directly from URL
        """
        return await self._aget_pdftotext(url, retryable = retryable, retry_limit = retry_limit, **kwargs)

    

    """
    Google CSX Methods
    """

    def get_csx(
        self,
        query: str,
        exact_terms: Optional[str] = None,
        exclude_terms: Optional[str] = None,
        file_type: Optional[str] = None,
        cachable: Optional[bool] = True,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        **kwargs,
    ) -> Dict[str, Union[List[Dict[str, Any]], Any]]:
        """
        Returns the Google CSX Results

        file_type: pdf
        """
        if not self.google_csx_api_key and not self.google_csx_id:
            raise ValueError('Google CSX API Key and ID are not set')
        params = {
            'key': self.google_csx_api_key, 'cx': self.google_csx_id, 'q': query,
        }
        if exact_terms: params['exactTerms'] = exact_terms
        if exclude_terms: params['excludeTerms'] = exclude_terms
        if file_type: 
            if 'application/' not in file_type: file_type = f'application/{file_type}'
            params['fileType'] = file_type
        if kwargs: params.update(kwargs)
        if background:
            return self.pooler.create_background(
                self.get,
                url = self.google_csx_base_url,
                return_type = 'json',
                params = params,
                task_callback = callback,
                cachable = cachable,
                overwrite_cache = overwrite_cache,
                disable_cache = disable_cache,
            )
        return self.get(url = self.google_csx_base_url, return_type = 'json', params = params, cachable = cachable, overwrite_cache = overwrite_cache, disable_cache = disable_cache)


    async def _aget_csx(
        self,
        # url: str,
        *args,
        return_type: Optional[Union[ReturnType, ReturnModelT]] = 'json',
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> ReturnTypeT:
        """
        Creates a GET Request and returns a `ReturnTypeT` for Google CSX to handle rate limiting
        """
        get_func = self._aget_
        url = self.google_csx_base_url
        if retryable: get_func = http_retry_wrapper(max_tries = retry_limit + 1)(get_func)
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
        return self.handle_response(response, return_type = return_type)

    @cachify.register()
    async def acsx_request(
        self, 
        # url: str, 
        *args,
        cachable: Optional[bool] = True,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = False,
        retry_limit: Optional[int] = 3,
        **kwargs
    ) -> Dict[str, Union[List[Dict[str, Any]], Any]]:
        """
        Creates a CSX Request while handling rate limiting
        """
        if background:
            return self.pooler.create_background(
                self._aget_csx,
                *args,
                task_callback = callback,
                retryable = retryable,
                retry_limit = retry_limit,
                **kwargs
            )
        return await self._aget_csx(*args, retryable = retryable, retry_limit = retry_limit,  **kwargs)
    

            
    async def aget_csx(
        self,
        query: str,
        exact_terms: Optional[str] = None,
        exclude_terms: Optional[str] = None,
        file_type: Optional[str] = None,
        cachable: Optional[bool] = True,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        **kwargs,
    ) -> Dict[str, Union[List[Dict[str, Any]], Any]]:
        """
        Returns the Google CSX Results

        file_type: pdf
        """
        if not self.google_csx_api_key and not self.google_csx_id:
            raise ValueError('Google CSX API Key and ID are not set')
        params = {
            'key': self.google_csx_api_key, 'cx': self.google_csx_id, 'q': query,
        }
        if exact_terms: params['exactTerms'] = exact_terms
        if exclude_terms: params['excludeTerms'] = exclude_terms
        if file_type: 
            if 'application/' not in file_type: file_type = f'application/{file_type}'
            params['fileType'] = file_type
        if kwargs: params.update(kwargs)
        if background:
            return self.pooler.create_background(
                self.acsx_request,
                params = params,
                task_callback = callback,
                cachable = cachable,
                overwrite_cache = overwrite_cache,
                disable_cache = disable_cache,
            )
        return await self.acsx_request(params = params, cachable = cachable, overwrite_cache = overwrite_cache, disable_cache = disable_cache)
        # return await self._aget(url = self.google_csx_base_url, return_type = 'json', params = params)
        # return await self.aget(url = self.google_csx_base_url, return_type = 'json', params = params, cachable = cachable, overwrite_cache = overwrite_cache, disable_cache = disable_cache)
    
        