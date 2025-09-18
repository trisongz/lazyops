"""
Async Client API
"""

import typing as t
import contextlib
from httpx._client import AsyncClient
from httpx._config import DEFAULT_TIMEOUT_CONFIG
from httpx._models import Response
from .types.typed import (
    AuthTypes,
    CertTypes,
    CookieTypes,
    HeaderTypes,
    QueryParamTypes,
    RequestContent,
    RequestData,
    RequestFiles,
    TimeoutTypes,
    ProxiesTypes,
    VerifyTypes,
    URLTypes,
)

async def arequest(
    method: str,
    url: URLTypes,
    *,
    params: t.Optional[QueryParamTypes] = None,
    content: t.Optional[RequestContent] = None,
    data: t.Optional[RequestData] = None,
    files: t.Optional[RequestFiles] = None,
    json: t.Optional[t.Any] = None,
    headers: t.Optional[HeaderTypes] = None,
    cookies: t.Optional[CookieTypes] = None,
    auth: t.Optional[AuthTypes] = None,
    proxy: t.Optional[ProxiesTypes] = None,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    follow_redirects: bool = False,
    verify: VerifyTypes = True,
    cert: t.Optional[CertTypes] = None,
    trust_env: bool = True,
) -> Response:
    """
    Sends an HTTP request.

    **Parameters:**

    * **method** - HTTP method for the new `Request` object: `GET`, `OPTIONS`,
    `HEAD`, `POST`, `PUT`, `PATCH`, or `DELETE`.
    * **url** - URL for the new `Request` object.
    * **params** - *(optional)* Query parameters to include in the URL, as a
    string, dictionary, or sequence of two-tuples.
    * **content** - *(optional)* Binary content to include in the body of the
    request, as bytes or a byte iterator.
    * **data** - *(optional)* Form data to include in the body of the request,
    as a dictionary.
    * **files** - *(optional)* A dictionary of upload files to include in the
    body of the request.
    * **json** - *(optional)* A JSON serializable object to include in the body
    of the request.
    * **headers** - *(optional)* Dictionary of HTTP headers to include in the
    request.
    * **cookies** - *(optional)* Dictionary of Cookie items to include in the
    request.
    * **auth** - *(optional)* An authentication class to use when sending the
    request.
    * **proxy** - *(optional)* A dictionary mapping proxy keys to proxy URLs.
    * **timeout** - *(optional)* The timeout configuration to use when sending
    the request.
    * **follow_redirects** - *(optional)* Enables or disables HTTP redirects.
    * **verify** - *(optional)* SSL certificates (a.k.a CA bundle) used to
    verify the identity of requested hosts. Either `True` (default CA bundle),
    a path to an SSL certificate file, an `ssl.SSLContext`, or `False`
    (which will disable verification).
    * **cert** - *(optional)* An SSL certificate used by the requested host
    to authenticate the client. Either a path to an SSL certificate file, or
    two-tuple of (certificate file, key file), or a three-tuple of (certificate
    file, key file, password).
    * **trust_env** - *(optional)* Enables or disables usage of environment
    variables for configuration.

    **Returns:** `Response`

    Usage:

    ```
    >>> import aiohttpx
    >>> response = await aiohttpx.async_request('GET', 'https://httpbin.org/get')
    >>> response
    <Response [200 OK]>
    ```
    """
    async with AsyncClient(
        cookies=cookies,
        proxy=proxy,
        cert=cert,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
    ) as client:
        return await client.request(
            method=method,
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            auth=auth,
            follow_redirects=follow_redirects,
        )

async_request = arequest

async def acreate_stream(
    method: str,
    url: URLTypes,
    *,
    params: t.Optional[QueryParamTypes] = None,
    content: t.Optional[RequestContent] = None,
    data: t.Optional[RequestData] = None,
    files: t.Optional[RequestFiles] = None,
    json: t.Optional[t.Any] = None,
    headers: t.Optional[HeaderTypes] = None,
    cookies: t.Optional[CookieTypes] = None,
    auth: t.Optional[AuthTypes] = None,
    proxy: t.Optional[ProxiesTypes] = None,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    follow_redirects: bool = False,
    verify: VerifyTypes = True,
    cert: t.Optional[CertTypes] = None,
    trust_env: bool = True,
) -> Response:
    """Create an asynchronous streaming response.

    Parameters are identical to :func:`arequest`; the key difference is that
    this helper returns the streaming response immediately instead of loading
    the body in memory.
    """
    async with AsyncClient(
        cookies=cookies,
        proxy=proxy,
        cert=cert,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
    ) as client:
        return await client.stream(
            method=method,
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            auth=auth,
            follow_redirects=follow_redirects,
        )

async_create_stream = acreate_stream

@contextlib.asynccontextmanager
async def astream(
    method: str,
    url: URLTypes,
    *,
    params: t.Optional[QueryParamTypes] = None,
    content: t.Optional[RequestContent] = None,
    data: t.Optional[RequestData] = None,
    files: t.Optional[RequestFiles] = None,
    json: t.Optional[t.Any] = None,
    headers: t.Optional[HeaderTypes] = None,
    cookies: t.Optional[CookieTypes] = None,
    auth: t.Optional[AuthTypes] = None,
    proxy: t.Optional[ProxiesTypes] = None,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    follow_redirects: bool = False,
    verify: VerifyTypes = True,
    cert: t.Optional[CertTypes] = None,
    trust_env: bool = True,
) -> t.AsyncIterator[Response]:
    """
    Alternative to `httpx.request()` that streams the response body
    instead of loading it into memory at once.

    **Parameters**: See `httpx.request`.

    See also: [Streaming Responses][0]

    [0]: /quickstart#streaming-responses
    """
    async with AsyncClient(
        cookies=cookies,
        proxy=proxy,
        cert=cert,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
    ) as client:
        async with client.stream(
            method=method,
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            auth=auth,
            follow_redirects=follow_redirects,
        ) as response:
            yield response

async_stream = astream

async def aget(
    url: URLTypes,
    *,
    params: t.Optional[QueryParamTypes] = None,
    headers: t.Optional[HeaderTypes] = None,
    cookies: t.Optional[CookieTypes] = None,
    auth: t.Optional[AuthTypes] = None,
    proxy: t.Optional[ProxiesTypes] = None,
    follow_redirects: bool = False,
    cert: t.Optional[CertTypes] = None,
    verify: VerifyTypes = True,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    trust_env: bool = True,
) -> Response:
    """
    Sends a `GET` request.

    **Parameters**: See `httpx.request`.

    Note that the `data`, `files`, `json` and `content` parameters are not available
    on this function, as `GET` requests should not include a request body.
    """
    return await async_request(
        "GET",
        url,
        params=params,
        headers=headers,
        cookies=cookies,
        auth=auth,
        proxy=proxy,
        follow_redirects=follow_redirects,
        cert=cert,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
    )

async_get = aget

async def aoptions(
    url: URLTypes,
    *,
    params: t.Optional[QueryParamTypes] = None,
    headers: t.Optional[HeaderTypes] = None,
    cookies: t.Optional[CookieTypes] = None,
    auth: t.Optional[AuthTypes] = None,
    proxy: t.Optional[ProxiesTypes] = None,
    follow_redirects: bool = False,
    cert: t.Optional[CertTypes] = None,
    verify: VerifyTypes = True,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    trust_env: bool = True,
) -> Response:
    """
    Sends an `OPTIONS` request.

    **Parameters**: See `httpx.request`.

    Note that the `data`, `files`, `json` and `content` parameters are not available
    on this function, as `OPTIONS` requests should not include a request body.
    """
    return await async_request(
        "OPTIONS",
        url,
        params=params,
        headers=headers,
        cookies=cookies,
        auth=auth,
        proxy=proxy,
        follow_redirects=follow_redirects,
        cert=cert,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
    )

async_options = aoptions

async def ahead(
    url: URLTypes,
    *,
    params: t.Optional[QueryParamTypes] = None,
    headers: t.Optional[HeaderTypes] = None,
    cookies: t.Optional[CookieTypes] = None,
    auth: t.Optional[AuthTypes] = None,
    proxy: t.Optional[ProxiesTypes] = None,
    follow_redirects: bool = False,
    cert: t.Optional[CertTypes] = None,
    verify: VerifyTypes = True,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    trust_env: bool = True,
) -> Response:
    """
    Sends a `HEAD` request.

    **Parameters**: See `httpx.request`.

    Note that the `data`, `files`, `json` and `content` parameters are not available
    on this function, as `HEAD` requests should not include a request body.
    """
    return await async_request(
        "HEAD",
        url,
        params=params,
        headers=headers,
        cookies=cookies,
        auth=auth,
        proxy=proxy,
        follow_redirects=follow_redirects,
        cert=cert,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
    )

async_head = ahead

async def apost(
    url: URLTypes,
    *,
    content: t.Optional[RequestContent] = None,
    data: t.Optional[RequestData] = None,
    files: t.Optional[RequestFiles] = None,
    json: t.Optional[t.Any] = None,
    params: t.Optional[QueryParamTypes] = None,
    headers: t.Optional[HeaderTypes] = None,
    cookies: t.Optional[CookieTypes] = None,
    auth: t.Optional[AuthTypes] = None,
    proxy: t.Optional[ProxiesTypes] = None,
    follow_redirects: bool = False,
    cert: t.Optional[CertTypes] = None,
    verify: VerifyTypes = True,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    trust_env: bool = True,
) -> Response:
    """
    Sends a `POST` request.

    **Parameters**: See `httpx.request`.
    """
    return await async_request(
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
        proxy=proxy,
        follow_redirects=follow_redirects,
        cert=cert,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
    )

async_post = apost

async def aput(
    url: URLTypes,
    *,
    content: t.Optional[RequestContent] = None,
    data: t.Optional[RequestData] = None,
    files: t.Optional[RequestFiles] = None,
    json: t.Optional[t.Any] = None,
    params: t.Optional[QueryParamTypes] = None,
    headers: t.Optional[HeaderTypes] = None,
    cookies: t.Optional[CookieTypes] = None,
    auth: t.Optional[AuthTypes] = None,
    proxy: t.Optional[ProxiesTypes] = None,
    follow_redirects: bool = False,
    cert: t.Optional[CertTypes] = None,
    verify: VerifyTypes = True,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    trust_env: bool = True,
) -> Response:
    """
    Sends a `PUT` request.

    **Parameters**: See `httpx.request`.
    """
    return await async_request(
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
        proxy=proxy,
        follow_redirects=follow_redirects,
        cert=cert,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
    )

async_put = aput

async def apatch(
    url: URLTypes,
    *,
    content: t.Optional[RequestContent] = None,
    data: t.Optional[RequestData] = None,
    files: t.Optional[RequestFiles] = None,
    json: t.Optional[t.Any] = None,
    params: t.Optional[QueryParamTypes] = None,
    headers: t.Optional[HeaderTypes] = None,
    cookies: t.Optional[CookieTypes] = None,
    auth: t.Optional[AuthTypes] = None,
    proxy: t.Optional[ProxiesTypes] = None,
    follow_redirects: bool = False,
    cert: t.Optional[CertTypes] = None,
    verify: VerifyTypes = True,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    trust_env: bool = True,
) -> Response:
    """
    Sends a `PATCH` request.

    **Parameters**: See `httpx.request`.
    """
    return await async_request(
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
        proxy=proxy,
        follow_redirects=follow_redirects,
        cert=cert,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
    )

async_patch = apatch

async def adelete(
    url: URLTypes,
    *,
    params: t.Optional[QueryParamTypes] = None,
    headers: t.Optional[HeaderTypes] = None,
    cookies: t.Optional[CookieTypes] = None,
    auth: t.Optional[AuthTypes] = None,
    proxy: t.Optional[ProxiesTypes] = None,
    follow_redirects: bool = False,
    cert: t.Optional[CertTypes] = None,
    verify: VerifyTypes = True,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    trust_env: bool = True,
) -> Response:
    """
    Sends a `DELETE` request.

    **Parameters**: See `httpx.request`.

    Note that the `data`, `files`, `json` and `content` parameters are not available
    on this function, as `DELETE` requests should not include a request body.
    """
    return await async_request(
        "DELETE",
        url,
        params=params,
        headers=headers,
        cookies=cookies,
        auth=auth,
        proxy=proxy,
        follow_redirects=follow_redirects,
        cert=cert,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
    )

async_delete = adelete

def stream_iterator(
    url: str,
    *,
    method: t.Optional[str] = 'GET',
    mode: t.Optional[t.Literal['r', 'rb']] = 'rb',
    chunk_size: t.Optional[int] = 1024,
    params: t.Optional[QueryParamTypes] = None,
    headers: t.Optional[HeaderTypes] = None,
    follow_redirects: bool = False,
    verify: VerifyTypes = True,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    trust_env: bool = True,
    **kwargs,
) -> t.Generator[t.Union[str, bytes], None, None]:
    """
    Returns an iterator of responses from a streaming request.

    **Parameters**: See `httpx.request`.
    """
    from httpx._api import stream
    with stream(
        method,
        url,
        params=params,
        headers=headers,
        follow_redirects=follow_redirects,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
        **kwargs,
    ) as response:
        if mode == 'r':
            yield from response.iter_lines()
        else:
            yield from response.iter_bytes(chunk_size = chunk_size)


async def astream_iterator(
    url: str,
    *,
    method: t.Optional[str] = 'GET',
    mode: t.Optional[t.Literal['r', 'rb']] = 'rb',
    chunk_size: t.Optional[int] = 1024,
    params: t.Optional[QueryParamTypes] = None,
    headers: t.Optional[HeaderTypes] = None,
    follow_redirects: bool = False,
    verify: VerifyTypes = True,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    trust_env: bool = True,
    **kwargs,
) -> t.AsyncGenerator[t.Union[str, bytes], None]:
    """
    Returns an async iterator of responses from a streaming request.

    **Parameters**: See `httpx.request`.
    """
    async with astream(
        method,
        url,
        params=params,
        headers=headers,
        follow_redirects=follow_redirects,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
        **kwargs,
    ) as response:
        if mode == 'r':
            async for line in response.aiter_lines():
                yield line
        else:
            async for chunk in response.aiter_bytes(chunk_size = chunk_size):
                yield chunk
