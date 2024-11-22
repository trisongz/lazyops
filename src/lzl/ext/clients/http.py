from __future__ import annotations

"""
HTTP Client
"""

import abc
from lzl import load
from lzl.types import eproperty, Literal

from .base import BaseClient
from .mixins import cachify, CachifyHTTPClientMixin, BaseHTTPClientMixin, ResponseType, ResponseT
from typing import Optional, Type, TypeVar, Union, Set, List, Any, Dict, Callable, Awaitable, overload, TYPE_CHECKING

if TYPE_CHECKING:
    from lzl.logging import Logger
    from lzo.types.base import RegisteredSettings
    from lzl.pool import ThreadPool
    from .base import DataSchema, ResultSchema


@cachify.register_object()
class BaseHTTPClient(BaseClient, BaseHTTPClientMixin, CachifyHTTPClientMixin):
    """
    The Base HTTP Client Class
    """
    name: Optional[str] = 'http'

    @overload
    def get(
        self, 
        url: str, 
        *args,
        response_type: ResponseType = None,
        cachable: Optional[bool] = None,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        ...

    @cachify.register()
    def get(
        self, 
        url: str, 
        *args,
        response_type: ResponseType = None,
        cachable: Optional[bool] = None,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        """
        Creates a GET Request and returns a `ResponseT`
        """
        if background:
            return self.pooler.create_background(
                self._get,
                url = url,
                *args,
                response_type = response_type,
                task_callback = callback,
                retryable = retryable,
                retry_limit = retry_limit,
                **kwargs
            )
        return self._get(url = url, *args, response_type = response_type, retryable = retryable, retry_limit = retry_limit, **kwargs)
    
    @overload
    def post(
        self, 
        url: str, 
        *args,
        response_type: ResponseType = None,
        cachable: Optional[bool] = None,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        ...

    @cachify.register()
    def post(
        self, 
        url: str, 
        *args,
        response_type: ResponseType = None,
        cachable: Optional[bool] = None,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        """
        Creates a POST Request and returns a `ResponseT`
        """
        if background:
            return self.pooler.create_background(
                self._post,
                url = url,
                *args,
                response_type = response_type,
                task_callback = callback,
                retryable = retryable,
                retry_limit = retry_limit,
                **kwargs
            )
        return self._post(url = url, *args, response_type = response_type, retryable = retryable, retry_limit = retry_limit, **kwargs)

    @overload
    async def aget(
        self, 
        url: str, 
        *args,
        response_type: ResponseType = None,
        cachable: Optional[bool] = None,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        ...

    @cachify.register()
    async def aget(
        self, 
        url: str, 
        *args,
        response_type: ResponseType = None,
        cachable: Optional[bool] = None,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        """
        Creates a GET Request and returns a `ResponseT`
        """
        if background:
            return self.pooler.create_background(
                self._aget,
                url = url,
                *args,
                response_type = response_type,
                task_callback = callback,
                retryable = retryable,
                retry_limit = retry_limit,
                **kwargs
            )
        return await self._aget(url = url, *args, response_type = response_type, retryable = retryable, retry_limit = retry_limit, **kwargs)

    @overload
    async def apost(
        self, 
        url: str, 
        *args,
        response_type: ResponseType = None,
        cachable: Optional[bool] = None,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        ...

    @cachify.register()
    async def apost(
        self, 
        url: str, 
        *args,
        response_type: ResponseType = None,
        cachable: Optional[bool] = None,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        background: Optional[bool] = False,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> ResponseT:
        """
        Creates a POST Request and returns a `ResponseT`
        """
        if background:
            return self.pooler.create_background(
                self._apost,
                url = url,
                *args,
                response_type = response_type,
                task_callback = callback,
                retryable = retryable,
                retry_limit = retry_limit,
                **kwargs
            )
        return await self._apost(url = url, *args, response_type = response_type, retryable = retryable, retry_limit = retry_limit, **kwargs)
    
    @cachify.register()
    def get_pdftotext(
        self,
        url: str,
        cachable: Optional[bool] = None,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        validate_url: Optional[bool] = False,
        raise_errors: Optional[bool] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Transform a PDF File to Text directly from URL
        """
        return self._get_pdftotext(url = url, validate_url = validate_url, retryable = retryable, retry_limit = retry_limit, raise_errors = raise_errors, **kwargs)
    

    @cachify.register()
    async def aget_pdftotext(
        self,
        url: str,
        cachable: Optional[bool] = None,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Transform a PDF File to Text directly from URL
        """
        return await self._aget_pdftotext(url = url, retryable = retryable, retry_limit = retry_limit, **kwargs)
    

    @cachify.register()
    async def acsx_request(
        self, 
        *args,
        cachable: Optional[bool] = None,
        overwrite_cache: Optional[bool] = None,
        disable_cache: Optional[bool] = None,
        callback: Optional[Callable[..., Any]] = None,
        retryable: Optional[bool] = None,
        retry_limit: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Union[List[Dict[str, Any]], Any]]:
        """
        Creates a CSX Request while handling rate limiting
        """
        return await self._aget_csx_(*args, retryable = retryable, retry_limit = retry_limit,  **kwargs)
    
    async def aget_csx(
        self,
        query: str,
        exact_terms: Optional[str] = None,
        exclude_terms: Optional[str] = None,
        file_type: Optional[str] = None,
        cachable: Optional[bool] = None,
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