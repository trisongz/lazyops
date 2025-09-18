from __future__ import annotations

"""Hybrid sync/async HTTP client facade built on top of :mod:`httpx`."""

import contextlib
import typing as t

import httpx

from .presets import PresetConfig, get_preset
from .types import typed as ht
from .types.params import ClientParams
from .utils.helpers import http_retry_wrapper, is_coro_func, raise_for_status, wrap_soup_response
from .utils.logs import logger

__all__ = ["Client", "Response"]

if t.TYPE_CHECKING:
    from bs4 import BeautifulSoup


if t.TYPE_CHECKING:

    class Response(httpx.Response):

        def json(self, **kwargs) -> t.Union[t.Dict[str, t.Any], t.List[t.Any], t.Any]:
            """
            Returns the JSON response.
            """
            ...

        @property
        def soup(self) -> BeautifulSoup:
            """
            Returns the BeautifulSoup object
            """
            ...

else:
    Response = httpx.Response



RT = t.TypeVar('RT')

httpx.Response.raise_for_status = raise_for_status

class Client:

    """
    An sync + asynchronous HTTP client, with connection pooling, HTTP/2, redirects,
    cookie persistence, etc.

    Usage:

    ```python
    >>> async with aiohttpx.Client() as client:
    >>>     response = await client.async_get('https://example.org')
    ```

    **Parameters:**

    * **auth** - *(optional)* An authentication class to use when sending
    requests.
    * **params** - *(optional)* Query parameters to include in request URLs, as
    a string, dictionary, or sequence of two-tuples.
    * **headers** - *(optional)* Dictionary of HTTP headers to include when
    sending requests.
    * **cookies** - *(optional)* Dictionary of Cookie items to include when
    sending requests.
    * **verify** - *(optional)* SSL certificates (a.k.a CA bundle) used to
    verify the identity of requested hosts. Either `True` (default CA bundle),
    a path to an SSL certificate file, or `False` (disable verification).
    * **cert** - *(optional)* An SSL certificate used by the requested host
    to authenticate the client. Either a path to an SSL certificate file, or
    two-tuple of (certificate file, key file), or a three-tuple of (certificate
    file, key file, password).
    * **http2** - *(optional)* A boolean indicating if HTTP/2 support should be
    enabled. Defaults to `False`.
    * **proxies** - *(optional)* A dictionary mapping HTTP protocols to proxy
    URLs.
    * **timeout** - *(optional)* The timeout configuration to use when sending
    requests.
    * **limits** - *(optional)* The limits configuration to use.
    * **max_redirects** - *(optional)* The maximum number of redirect responses
    that should be followed.
    * **base_url** - *(optional)* A URL to use as the base when building
    request URLs.
    * **transport** - *(optional)* [Sync] A transport class to use for sending requests
    over the network.
    * **async_transport** - *(optional)* [Async] A transport class to use for sending requests
    over the network.
    * **app** - *(optional)* An ASGI application to send requests to,
    rather than sending actual network requests.
    * **trust_env** - *(optional)* Enables or disables usage of environment
    variables for configuration.
    * **default_encoding** - *(optional)* The default encoding to use for decoding
    response text, if no charset information is included in a response Content-Type
    header. Set to a callable for automatic character set detection. Default: "utf-8".
    """

    def __init__(
        self,
        *,
        auth: t.Optional[ht.AuthTypes] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        verify: t.Optional[ht.VerifyTypes] = None,
        cert: t.Optional[ht.CertTypes] = None,
        http1: t.Optional[bool] = None,
        http2: t.Optional[bool] = None,
        proxies: t.Optional[ht.ProxiesTypes] = None,

        mounts: t.Optional[t.Mapping[str, ht.BaseTransport]] = None,
        async_mounts: t.Optional[t.Mapping[str, ht.AsyncBaseTransport]] = None,

        timeout: t.Optional[ht.TimeoutTypes] = None,
        follow_redirects: t.Optional[bool] = None,
        limits: t.Optional[ht.Limits] = None,
        retries: t.Optional[int] = None,

        max_redirects: int = ht.DEFAULT_MAX_REDIRECTS,
        event_hooks: t.Optional[t.Mapping[str, t.List[t.Callable]]] = None,
        async_event_hooks: t.Optional[t.Mapping[str, t.List[t.Callable]]] = None,
        base_url: ht.URLTypes = "",
        transport: t.Optional[ht.BaseTransport] = None,
        async_transport: t.Optional[ht.AsyncBaseTransport] = None,
        app: t.Optional[t.Callable] = None,
        trust_env: t.Optional[bool] = None,
        default_encoding: str = "utf-8",
        soup_enabled: t.Optional[bool] = None,
        debug: t.Optional[bool] = None,
        init_hooks: t.Optional[t.List[t.Union[t.Tuple[t.Callable, t.Dict], t.Callable]]] = None,
        preset_config: t.Optional[PresetConfig] = 'default',
        disable_httpx_logger: t.Optional[bool] = None,
        **kwargs: t.Any,
    ):
        preset = get_preset(preset_config)
        if preset:
            if timeout is None: timeout = preset['timeout']
            if limits is None: limits = preset['limits']
            if retries is None: retries = preset['retries']
            if preset['kwargs']:
                pkwargs = preset['kwargs']
                if follow_redirects is None and pkwargs.get('follow_redirects'):
                    follow_redirects = pkwargs['follow_redirects']
                if verify is None and pkwargs.get('verify'):
                    verify = pkwargs['verify']
                if disable_httpx_logger is None and pkwargs.get('disable_httpx_logger'):
                    disable_httpx_logger = pkwargs['disable_httpx_logger']
        
        if disable_httpx_logger:
            from .utils.logs import mute_httpx_logger
            mute_httpx_logger()

        self._config = ClientParams(
            auth=auth,
            params=params,
            headers=headers,
            cookies=cookies,
            verify=verify,
            cert=cert,
            http1=http1,
            http2=http2,
            proxies=proxies,
            mounts=mounts,
            async_mounts=async_mounts,
            timeout=timeout,
            follow_redirects=follow_redirects,
            limits=limits,
            retries=retries,
            max_redirects=max_redirects,
            event_hooks=event_hooks,
            async_event_hooks=async_event_hooks,
            base_url=base_url,
            transport=transport,
            async_transport=async_transport,
            app=app,
            trust_env=trust_env,
            default_encoding=default_encoding,
            soup_enabled=soup_enabled,
            debug=debug,
            kwargs=kwargs
        )
        self._sync_client: t.Optional[httpx.Client] = None
        self._async_client: t.Optional[httpx.AsyncClient] = None
        
        self._sync_init_hooks_completed: t.Optional[bool] = False
        self._async_init_hooks_completed: t.Optional[bool] = False

        self._sync_active: bool = False
        self._async_active: bool = False

        self._init_hooks: t.Optional[t.List[t.Union[t.Tuple[t.Callable, t.Dict], t.Callable]]] = init_hooks or []
        # Reserved for the async client if the init hooks are coros
        self._incomplete_hooks: t.Optional[t.List[t.Union[t.Tuple[t.Callable, t.Dict], t.Callable]]] = []

    def _wrap_retry(self, client: httpx.Client | httpx.AsyncClient) -> httpx.Client | httpx.AsyncClient:
        """Attach retry-aware wrappers to the primary HTTP verbs."""
        if self._config.retries is None:
            return client
        for method in {
            'get', 'options', 'head', 'post', 'put', 'patch', 'delete', 'stream',
        }:
            setattr(client, method, http_retry_wrapper(max_tries  = self._config.retries + 1)(getattr(client, method)))
        return client
    
    def _wrap_retry_method(self, method: t.Callable[..., RT], max_retries: t.Optional[int] = None) -> t.Callable[..., RT]:
        """Return *method* wrapped with the configured retry strategy."""

        if max_retries is None:
            max_retries = self._config.retries
        if max_retries is None:
            return method
        return http_retry_wrapper(max_tries=max_retries + 1)(method)


    @property
    def async_client(self) -> httpx.AsyncClient:
        """
        Returns an async client instance.
        """
        if self._async_client is None or not self._async_active:
            self._async_client = self._wrap_retry(httpx.AsyncClient(**self._config.async_kwargs))
            self._async_active = True
        return self._async_client

    @property
    def sync_client(self) -> httpx.Client:
        """
        Returns a sync client instance.
        """
        if self._sync_client is None or not self._sync_active:
            self._sync_client = self._wrap_retry(httpx.Client(**self._config.sync_kwargs))
            self._sync_active = True
        return self._sync_client
    
    """
    Base Url
    """
    @property
    def base_url(self) -> t.Union[str, httpx.URL]:
        """
        Returns the base url
        """
        if self._async_client: return self._async_client.base_url
        return self._sync_client.base_url if self._sync_client else self._config.base_url
    
    @base_url.setter
    def base_url(self, value: t.Union[str, httpx.URL]) -> None:
        return self.set_base_url(value)
    
    def set_base_url(self, base_url: ht.URLTypes):
        """
        Sets the base url
        """
        if isinstance(base_url, str): base_url = httpx.URL(base_url)
        if self._async_client: self._async_client.base_url = base_url
        if self._sync_client: self._sync_client.base_url = base_url
        self._config.base_url = str(base_url)


    """
    Headers
    """

    @property
    def headers(self) -> t.Dict[str, str]:
        """
        Get the headers dictionary.

        The headers are retrieved in order of priority:
        1. From the async client if it exists
        2. From the sync client if it exists  
        3. From the config

        If no headers exist yet, initializes an empty dict in the config.

        Returns:
        Dict[str, str]: The headers dictionary.
        """

        if self._async_client is not None:
            return self._async_client.headers
        if self._sync_client is not None:
            return self._sync_client.headers
        if self._config.headers is None:
            self._config.headers = {}
        return self._config.headers

    @headers.setter
    def headers(self, key, value):
        """
        Sets a header key/value pair.
        """
        if self._async_client is not None:
            self._async_client.headers[key] = value
        if self._sync_client is not None:
            self._sync_client.headers[key] = value
        if self._config.headers is None: self._config.headers = {}
        self._config.headers[key] = value

    
    def set_headers(self, headers: ht.HeaderTypes, update: t.Optional[bool] = None):
        """
        Sets the headers dictionary.
        """
        if self._async_client: 
            if update: self._async_client.headers.update(headers)
            else: self._async_client.headers = headers
        if self._sync_client: 
            if update: self._sync_client.headers.update(headers)
            else: self._sync_client.headers = headers
        if update: self._config.headers.update(headers)
        else: self._config.headers = headers
    
    """
    cookies
    """
    @property
    def cookies(self) -> t.Dict[str, str]:
        """
        Get the cookies dictionary.

        The cookies are retrieved in order of priority:
        1. From the async client if it exists  
        2. From the sync client if it exists
        3. From the config

        If no cookies exist yet, initializes an empty dict in the config.

        Returns:
        Dict[str, str]: The cookies dictionary.
        """

        if self._async_client is not None:
            return self._async_client.cookies
        if self._sync_client is not None:
            return self._sync_client.cookies
        if self._config.cookies is None:
            self._config.cookies = {}
        return self._config.cookies
    
    @cookies.setter
    def cookies(self, key, value):
        if self._async_client is not None:
            self._async_client.cookies[key] = value
        if self._sync_client is not None:
            self._sync_client.cookies[key] = value
        if self._config.cookies is None: self._config.cookies = {}
        self._config.cookies[key] = value

    def set_cookies(self, cookies: ht.CookieTypes):
        """
        Sets the cookies dictionary.
        """
        if self._async_client:
            self._async_client.cookies = cookies
        if self._sync_client:
            self._sync_client.cookies = cookies
        self._config.cookies = cookies
    
    def clear_cookies(self) -> None:
        """
        Clears the cookies dictionary.
        """
        if self._async_client:
            self._async_client.cookies = None
        if self._sync_client:
            self._sync_client.cookies = None
        self._config.cookies = None

    """
    params
    """

    @property
    def params(self) -> t.Dict[str, str]:
        """
        Returns the params dictionary.
        """
        if self._async_client:
            return self._async_client.params
        if self._sync_client:
            return self._sync_client.params
        if self._config.params is None:
            self._config.params = {}
        return self._config.params
    
    @params.setter
    def params(self, key, value):
        if self._async_client:
            self._async_client.params[key] = value
        if self._sync_client:
            self._sync_client.params[key] = value
        if self._config.params is None: self._config.params = {}
        self._config.params[key] = value

    
    def set_params(self, params: ht.QueryParamTypes):
        if self._async_client:
            self._async_client.params = params
        if self._sync_client:
            self._sync_client.params = params
        self._config.params = params

    """
    auth
    """

    @property
    def auth(self) -> t.Optional[ht.AuthTypes]:
        """
        Returns the auth object.
        """
        if self._async_client:
            return self._async_client.auth
        return self._sync_client.auth if self._sync_client else self._config.auth
    
    @auth.setter
    def auth(self, value: t.Optional[ht.AuthTypes]):
        if self._async_client:
            self._async_client.auth = value
        if self._sync_client:
            self._sync_client.auth = value
        self._config.auth = value


    def set_auth(self, auth: ht.AuthTypes):
        """
        Sets the auth object.
        """
        if self._async_client:
            self._async_client.auth = auth
        if self._sync_client:
            self._sync_client.auth = auth
        self._config.auth = auth

    """
    timeout
    """
    @property
    def timeout(self) -> ht.TimeoutTypes:
        """
        Get the timeout configuration.
        """
        if self._async_client:
            return self._async_client.timeout
        return self._sync_client.timeout if self._sync_client else self._config.timeout

    @timeout.setter
    def timeout(self, value: ht.TimeoutTypes):
        if self._async_client:
            self._async_client.timeout = value
        if self._sync_client:
            self._sync_client.timeout = value
        self._config.timeout = value

    
    def set_timeout(self, timeout: ht.TimeoutTypes):
        if self._async_client:
            self._async_client.timeout = timeout
        if self._sync_client:
            self._sync_client.timeout = timeout
        self._config.timeout = timeout

    """
    proxies
    """
    @property
    def proxies(self) -> t.Dict[str, str]:
        """
        Get the proxies dictionary.
        """
        return self._config.proxies
    
    @proxies.setter
    def proxies(self, value: t.Dict[str, str]):
        self._config.proxies = value

    """
    event hooks
    """

    @property
    def event_hooks(self) -> t.Optional[t.Mapping[str, t.List[t.Callable]]]:
        """
        The event hooks dictionary.
        """
        if self._async_client: return self._async_client.event_hooks
        return self._sync_client.event_hooks if self._sync_client else self._config.event_hooks


    def set_event_hooks(
        self, 
        event_hooks: t.Optional[t.Mapping[str, t.List[t.Callable]]] = None,
        async_event_hooks: t.Optional[t.Mapping[str, t.List[t.Callable]]] = None
    ):
        if async_event_hooks:
            if self._async_client:
                self._async_client.event_hooks = async_event_hooks
            self._config.async_event_hooks = async_event_hooks
        if event_hooks: 
            if self._sync_client:
                self._sync_client.event_hooks = event_hooks
            self._config.event_hooks = event_hooks
    
    """
    init hooks
    """

    def _run_init_hooks(self):
        """
        Run init hooks if present
        """
        if self._sync_init_hooks_completed: return
        if self._init_hooks:
            while self._init_hooks:
                hook = self._init_hooks.pop()
                func, kwargs = hook if type(hook) == tuple else (hook, {})
                if is_coro_func(func):
                    self._incomplete_hooks.append(hook)
                    continue
                func(self, **kwargs)
        self._sync_init_hooks_completed = True
    
    async def _async_run_init_hooks(self):
        """
        Run init hooks if present
        """
        if self._async_init_hooks_completed: return
        if self._init_hooks:
            while self._init_hooks:
                hook = self._init_hooks.pop()
                func, kwargs = hook if type(hook) == tuple else (hook, {})
                if is_coro_func(func): await func(self, **kwargs)
                else: func(self, **kwargs)

        if self._incomplete_hooks:
            # these should all be coros
            while self._incomplete_hooks:
                hook = self._incomplete_hooks.pop()
                func, kwargs = hook if type(hook) == tuple else (hook, {})
                await func(self, **kwargs)
        self._async_init_hooks_completed = True

        
    def build_request(
        self,
        method: str,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> httpx.Request:
        """
        Build and return a request instance.

        * The `params`, `headers` and `cookies` arguments
        are merged with any values set on the client.
        * The `url` argument is merged with any `base_url` set on the client.

        See also: [Request instances][0]

        [0]: /advanced/#request-instances
        """
        self._run_init_hooks()
        return self.sync_client.build_request(
            method,
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            extensions=extensions,
        )
    
    async def async_build_request(
        self,
        method: str,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> httpx.Request:
        """
        Build and return a request instance.

        * The `params`, `headers` and `cookies` arguments
        are merged with any values set on the client.
        * The `url` argument is merged with any `base_url` set on the client.

        See also: [Request instances][0]

        [0]: /advanced/#request-instances
        """
        await self._async_run_init_hooks()
        return self.async_client.build_request(
            method,
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            extensions=extensions,
        )
    
    abuild_request = async_build_request

    """
    Async Methods
    """
    async def async_send(
        self,
        request: httpx.Request,
        *args,
        stream: bool = False,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault, None] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
    ) -> 'Response':
        """
        Send a request.

        The request is sent as-is, unmodified.

        Typically you'll want to build one with `Client.build_request()`
        so that any client-level configuration is merged into the request,
        but passing an explicit `httpx.Request()` is supported as well.

        See also: [Request instances][0]

        [0]: /advanced/#request-instances
        """
        await self._async_run_init_hooks()
        return await self.async_client.send(
            request,
            *args,
            stream=stream,
            auth=auth,
            follow_redirects=follow_redirects,
        )
    
    asend = async_send

    async def async_create_stream(
        self,
        method: str,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Creates an asynchronous streaming response.

        Builds an asynchronous HTTP request, sends it, and returns a streaming response.

        Args:
            method: The HTTP method to use.
            url: The URL to send the request to.
            content: The body content.
            data: The body data.
            files: The files to include.
            json: JSON data to include. 
            params: URL parameters to include.
            headers: Headers to include.
            cookies: Cookies to include.
            auth: Authentication settings.
            follow_redirects: Whether to follow redirects.
            timeout: Timeout settings.
            extensions: Extensions to use.

        Returns:
            httpx.Response: The streaming response.
        """

        request = await self.async_build_request(
            method=method,
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            extensions=extensions,
        )
        return await self.async_send(
            request=request,
            auth=auth,
            follow_redirects=follow_redirects,
            stream=True,
        )

    acreate_stream = async_create_stream

    @contextlib.asynccontextmanager
    async def async_stream(
        self,
        method: str,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> t.AsyncIterator['Response']:
        """
        Creates an asynchronous streaming response.

        Builds an asynchronous HTTP request, sends it, and returns a streaming response wrapped in a contextmanager.

        Args:
            method: The HTTP method to use.
            url: The URL to send the request to.
            content: The body content.
            data: The body data.
            files: The files to include.
            json: JSON data to include. 
            params: URL parameters to include.
            headers: Headers to include.
            cookies: Cookies to include.
            auth: Authentication settings.
            follow_redirects: Whether to follow redirects.
            timeout: Timeout settings.
            extensions: Extensions to use.

        Returns:
            t.AsyncIterator[httpx.Response]: The streaming response.
        """
        response = await self.async_create_stream(
            method=method,
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )
        try:
            yield response
        finally:
            await response.aclose()

    astream = async_stream

    async def async_request(
        self,
        method: str,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault, None] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
        **kwargs,
    ) -> 'Response':
        """Sends an asynchronous HTTP request.

        Sends an asynchronous HTTP request using the async client.

        Args:
            method: The HTTP method to use.
            url: The URL to send the request to.
            content: The body content.
            data: The body data.
            files: The files to include.
            json: JSON data to include.
            params: URL parameters to include.
            headers: Headers to include.
            cookies: Cookies to include.
            auth: Authentication settings.
            follow_redirects: Whether to follow redirects.
            timeout: Timeout settings.
            extensions: Extensions to use.
            kwargs: Additional arguments to pass to the request.

        Returns:
            httpx.Response: The HTTP response.

        Raises:
            Any exceptions raised by the async client.
        """

        #if not self._async_active:
        #    self._init_clients(_reset_async = True)
        if self._config.debug:
            logger.info(f"Request: {method} {url}")
            logger.info(f"Headers: {headers}")
            logger.info(f"Params: {params}")

        await self._async_run_init_hooks()
        return await self.async_client.request(
            method=method,
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
            **kwargs,
        )
    
    arequest = async_request
    
    async def async_get(
        self,
        url: ht.URLTypes,
        *,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault, None] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
        soup_enabled: t.Optional[bool] = None,
    ) -> 'Response':
        """
        Send a `GET` request.

        **Parameters**: See `httpx.request`.
        """
        response = await self.async_request(
            "GET",
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )
        if soup_enabled is True or self._config.soup_enabled is True:
            response = wrap_soup_response(response)
        return response

    async def async_options(
        self,
        url: ht.URLTypes,
        *,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Send an `OPTIONS` request.

        **Parameters**: See `httpx.request`.
        """
        return await self.async_request(
            "OPTIONS",
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )
    
    aget = async_get

    async def async_head(
        self,
        url: ht.URLTypes,
        *,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Send a `HEAD` request.

        **Parameters**: See `httpx.request`.
        """
        return await self.async_request(
            "HEAD",
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )
    
    ahead = async_head

    async def async_post(
        self,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Send a `POST` request.

        **Parameters**: See `httpx.request`.
        """
        return await self.async_request(
            "POST",
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )
    
    apost = async_post

    async def async_put(
        self,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Send a `PUT` request.

        **Parameters**: See `httpx.request`.
        """
        return await self.async_request(
            "PUT",
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    aput = async_put

    async def async_patch(
        self,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Send a `PATCH` request.

        **Parameters**: See `httpx.request`.
        """
        return await self.async_request(
            "PATCH",
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )
    
    apatch = async_patch

    async def async_delete(
        self,
        url: ht.URLTypes,
        *,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Send a `DELETE` request.

        **Parameters**: See `httpx.request`.
        """
        return await self.async_request(
            "DELETE",
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    adelete = async_delete

    
    """
    Sync Methods
    """
    def send(
        self,
        request: httpx.Request,
        *args,
        stream: bool = False,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault, None] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
    ) -> 'Response':
        """
        Send a request.

        The request is sent as-is, unmodified.

        Typically you'll want to build one with `Client.build_request()`
        so that any client-level configuration is merged into the request,
        but passing an explicit `httpx.Request()` is supported as well.

        See also: [Request instances][0]

        [0]: /advanced/#request-instances
        """
        self._run_init_hooks()
        return self.sync_client.send(
            request,
            *args,
            stream=stream,
            auth=auth,
            follow_redirects=follow_redirects,
        )

    def create_stream(
        self,
        method: str,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Creates a streaming response for a synchronous request.

        Builds a synchronous HTTP request, sends it, and returns a streaming response.

        Args:
            method: The HTTP method to use.
            url: The URL to send the request to.
            content: The body content.
            data: The body data.
            files: The files to include.
            json: JSON data to include.
            params: URL parameters to include.
            headers: Headers to include.
            cookies: Cookies to include.
            auth: Authentication settings.
            follow_redirects: Whether to follow redirects.
            timeout: Timeout settings.
            extensions: Extensions to use.
        
        Returns:
            httpx.Response: The streaming response.
        """
        request = self.build_request(
            method=method,
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            extensions=extensions,
        )
        return self.send(
            request=request,
            auth=auth,
            follow_redirects=follow_redirects,
            stream=True,
        )


    @contextlib.contextmanager
    def stream(
        self,
        method: str,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> t.Iterator['Response']:
        """
        Creates a synchronous streaming response.

        Builds a synchronous HTTP request, sends it, and returns a streaming response wrapped in a contextmanager.

        Args:
            method: The HTTP method to use.
            url: The URL to send the request to.
            content: The body content.
            data: The body data.
            files: The files to include.
            json: JSON data to include. 
            params: URL parameters to include.
            headers: Headers to include.
            cookies: Cookies to include.
            auth: Authentication settings.
            follow_redirects: Whether to follow redirects.
            timeout: Timeout settings.
            extensions: Extensions to use.

        Returns:
            t.Iterator[httpx.Response]: The streaming response.
        """
        
        response = self.create_stream(
            method=method,
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )
        try:
            yield response
        finally:
            response.close()

    def request(
        self,
        method: str,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault, None] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
        **kwargs,
    ) -> 'Response':
        """Sends a synchronous HTTP request.

        Sends a synchronous HTTP request using the sync client. 

        Args:
            method: The HTTP method to use.
            url: The URL to send the request to.
            content: The body content.
            data: The body data.
            files: The files to include.
            json: JSON data to include.
            params: URL parameters to include.
            headers: Headers to include.
            cookies: Cookies to include.
            auth: Authentication settings.
            follow_redirects: Whether to follow redirects.
            timeout: Timeout settings.
            extensions: Extensions to use.
            kwargs: Additional arguments to pass to the request.
        
        Returns:
            httpx.Response: The HTTP response.
        
        Raises:
            Any exceptions raised by the sync client.
        """
        #if not self._sync_active:
        #    self._init_clients(_reset_sync = True)
        if self._config.debug:
            logger.info(f"Request: {method} {url}")
            logger.info(f"Headers: {headers}")
            logger.info(f"Params: {params}")
        self._run_init_hooks()
        return self.sync_client.request(
            method=method,
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
            **kwargs,
        )
    
    def get(
        self,
        url: ht.URLTypes,
        *,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault, None] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
        soup_enabled: t.Optional[bool] = None,
    ) -> 'Response':
        """
        Send a `GET` request.

        **Parameters**: See `httpx.request`.
        """
        response = self.request(
            "GET",
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )
        if soup_enabled is True or self._config.soup_enabled is True:
            response = wrap_soup_response(response)
        return response

    def options(
        self,
        url: ht.URLTypes,
        *,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Send an `OPTIONS` request.

        **Parameters**: See `httpx.request`.
        """
        return self.request(
            "OPTIONS",
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    def head(
        self,
        url: ht.URLTypes,
        *,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Send a `HEAD` request.

        **Parameters**: See `httpx.request`.
        """
        return self.request(
            "HEAD",
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    def post(
        self,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Send a `POST` request.

        **Parameters**: See `httpx.request`.
        """
        return self.request(
            "POST",
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    def put(
        self,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Send a `PUT` request.

        **Parameters**: See `httpx.request`.
        """
        return self.request(
            "PUT",
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    def patch(
        self,
        url: ht.URLTypes,
        *,
        content: t.Optional[ht.RequestContent] = None,
        data: t.Optional[ht.RequestData] = None,
        files: t.Optional[ht.RequestFiles] = None,
        json: t.Optional[t.Any] = None,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Send a `PATCH` request.

        **Parameters**: See `httpx.request`.
        """
        return self.request(
            "PATCH",
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    def delete(
        self,
        url: ht.URLTypes,
        *,
        params: t.Optional[ht.QueryParamTypes] = None,
        headers: t.Optional[ht.HeaderTypes] = None,
        cookies: t.Optional[ht.CookieTypes] = None,
        auth: t.Union[ht.AuthTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: t.Union[bool, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: t.Union[ht.TimeoutTypes, ht.UseClientDefault] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: t.Optional[dict] = None,
    ) -> 'Response':
        """
        Send a `DELETE` request.

        **Parameters**: See `httpx.request`.
        """
        return self.request(
            "DELETE",
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    """
    Startup/Shutdown
    """

    def startup(self) -> None:
        pass

    async def async_startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    async def async_shutdown(self) -> None:
        pass

    def close(self) -> None:
        """
        Close transport and proxies.
        """
        self.shutdown()
        if self._sync_active:
            self.sync_client.close()
            self._sync_active = False
            

    async def aclose(self) -> None:
        """
        Close transport and proxies.
        """
        await self.async_shutdown()
        if self._async_active:
            await self.async_client.aclose()
            self._async_active = False

    def __enter__(self):
        self.startup()
        # self.sync_client.__enter__()
        return self

    async def __aenter__(self):
        await self.async_startup()
        # await self.async_client.__aenter__()
        return self
    
    def __exit__(
        self,
        exc_type: t.Optional[t.Type[BaseException]] = None,
        exc_value: t.Optional[BaseException] = None,
        traceback: t.Optional[ht.TracebackType] = None,
    ) -> None:
        self.close()
        if self._sync_active:
            self.sync_client.__exit__(exc_type, exc_value, traceback)
            self._sync_active = False

    async def __aexit__(
        self,
        exc_type: t.Optional[t.Type[BaseException]] = None,
        exc_value: t.Optional[BaseException] = None,
        traceback: t.Optional[ht.TracebackType] = None,
    ) -> None:
        await self.aclose()
        if self._async_active:
            await self.async_client.__aexit__(exc_type, exc_value, traceback)
            self._async_active = False
