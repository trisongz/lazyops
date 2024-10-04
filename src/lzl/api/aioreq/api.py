from __future__ import annotations

import typing as t
from .client import Client, DEFAULT_RETRIES, DEFAULT_TIMEOUT

if t.TYPE_CHECKING:
    from niquests import Response, AsyncResponse
    from niquests.sessions import HttpAuthenticationType, HttpMethodType, QueryParameterType, BodyType, HeadersType, CookiesType, MultiPartFilesType, MultiPartFilesAltType, TimeoutType, ProxyType, HookType, TLSVerifyType, TLSClientCertType
    from niquests.sessions import PreparedRequest
    from niquests._async import RetryType
    from niquests._typing import AsyncHttpAuthenticationType, AsyncBodyType
    from niquests.structures import QuicSharedCache

_QUIC_CACHE: t.Optional['QuicSharedCache'] = None

def get_shared_quic_cache() -> 'QuicSharedCache':
    """
    Returns the shared quic cache
    """
    global _QUIC_CACHE
    if _QUIC_CACHE is None:
        from niquests.api import _SHARED_QUIC_CACHE
        _QUIC_CACHE = _SHARED_QUIC_CACHE
    return _QUIC_CACHE


@t.overload
def request(
    method: 'HttpMethodType',
    url: str,
    *,
    params: 'QueryParameterType' | None = ...,
    data: 'BodyType' | None = ...,
    json: t.Any | None = ...,
    headers: 'HeadersType' | None = None,
    cookies: 'CookiesType' | None = None,
    files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    retries: 'RetryType' = ...,
) -> 'Response':
    """Constructs and sends a :class:`Request <Request>`.

    :param method: method for the new :class:`Request` object: ``GET``, ``OPTIONS``, ``HEAD``, ``POST``, ``PUT``, ``PATCH``, or ``DELETE``.
    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary, list of tuples or bytes to send
        in the query string for the :class:`Request`.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) A JSON serializable Python object to send in the body of the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the :class:`Request`.
    :param files: (optional) Dictionary of ``'name': file-like-objects`` (or ``{'name': file-tuple}``) for multipart encoding upload.
        ``file-tuple`` can be a 2-tuple ``('filename', fileobj)``, 3-tuple ``('filename', fileobj, 'content_type')``
        or a 4-tuple ``('filename', fileobj, 'content_type', custom_headers)``, where ``'content_type'`` is a string
        defining the content type of the given file and ``custom_headers`` a dict-like object containing additional headers
        to add for the file.
    :param auth: (optional) Auth tuple to enable Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How many seconds to wait for the server to send data
        before giving up, as a float, or a :ref:`(connect timeout, read
        timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Boolean. Enable/disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection. Defaults to ``True``.
    :param proxies: (optional) Dictionary mapping protocol to the URL of the proxy.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
            the server's TLS certificate, or a string, in which case it must be a path
            to a CA bundle to use. Defaults to ``True``.
            It is also possible to put the certificates (directly) in a string or bytes.
    :param stream: (optional) if ``False``, the response content will be immediately downloaded.
    :param cert: (optional) if String, path to ssl client cert file (.pem). If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    :param hooks: (optional) Register functions that should be called at very specific moment in the request lifecycle.
    :param retries: (optional) If integer, determine the number of retry in case of a timeout or connection error.
            Otherwise, for fine gained retry, use directly a ``Retry`` instance from urllib3.
    :return: :class:`Response <Response>` object

    Usage::

      >>> from lzl.api import aioreq
      >>> req = aioreq.request('GET', 'https://httpbin.org/get')
      >>> req
      <Response HTTP/2 [200]>
    """
    ...

    
@t.overload
def request(
    method: 'HttpMethodType',
    url: str,
    *,
    retries: 'RetryType' = DEFAULT_RETRIES,
    **kwargs: t.Any,
) -> 'Response':
    # By using the 'with' statement we are sure the session is closed, thus we
    # avoid leaving sockets open which can trigger a ResourceWarning in some
    # cases, and look like a memory leak in others.
    with Client(
        quic_cache_layer = get_shared_quic_cache(),
        retries=retries
    ) as session:
        return session.request(
            method=method,
            url=url,
            **kwargs,
        )
    

@t.overload
async def arequest(
    method: 'HttpMethodType',
    url: str,
    *,
    params: 'QueryParameterType' | None = ...,
    data: 'BodyType' | 'AsyncBodyType' | None = ...,
    json: t.Any | None = ...,
    headers: 'HeadersType' | None = None,
    cookies: 'CookiesType' | None = None,
    files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
    auth: 'HttpAuthenticationType' | 'AsyncHttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: t.Literal[False] = ...,
    cert: 'TLSClientCertType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    retries: 'RetryType' = ...,
) -> 'Response':
    """Constructs and sends a :class:`Request <Request>`.

    :param method: method for the new :class:`Request` object: ``GET``, ``OPTIONS``, ``HEAD``, ``POST``, ``PUT``, ``PATCH``, or ``DELETE``.
    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary, list of tuples or bytes to send
        in the query string for the :class:`Request`.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) A JSON serializable Python object to send in the body of the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the :class:`Request`.
    :param files: (optional) Dictionary of ``'name': file-like-objects`` (or ``{'name': file-tuple}``) for multipart encoding upload.
        ``file-tuple`` can be a 2-tuple ``('filename', fileobj)``, 3-tuple ``('filename', fileobj, 'content_type')``
        or a 4-tuple ``('filename', fileobj, 'content_type', custom_headers)``, where ``'content_type'`` is a string
        defining the content type of the given file and ``custom_headers`` a dict-like object containing additional headers
        to add for the file.
    :param auth: (optional) Auth tuple to enable Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How many seconds to wait for the server to send data
        before giving up, as a float, or a :ref:`(connect timeout, read
        timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Boolean. Enable/disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection. Defaults to ``True``.
    :param proxies: (optional) Dictionary mapping protocol to the URL of the proxy.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
            the server's TLS certificate, or a string, in which case it must be a path
            to a CA bundle to use. Defaults to ``True``.
            It is also possible to put the certificates (directly) in a string or bytes.
    :param stream: (optional) if ``False``, the response content will be immediately downloaded.
    :param cert: (optional) if String, path to ssl client cert file (.pem). If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    :param hooks: (optional) Register functions that should be called at very specific moment in the request lifecycle.
    :param retries: (optional) If integer, determine the number of retry in case of a timeout or connection error.
            Otherwise, for fine gained retry, use directly a ``Retry`` instance from urllib3.
    :return: :class:`Response <Response>` object

    Usage::

      >>> from lzl.api import aioreq
      >>> req = await aioreq.arequest('GET', 'https://httpbin.org/get')
      >>> req
      <Response HTTP/2 [200]>
    """
    ...


@t.overload
async def arequest(
    method: 'HttpMethodType',
    url: str,
    *,
    params: 'QueryParameterType' | None = ...,
    data: 'BodyType' | 'AsyncBodyType' | None = ...,
    json: t.Any | None = ...,
    headers: 'HeadersType' | None = None,
    cookies: 'CookiesType' | None = None,
    files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
    auth: 'HttpAuthenticationType' | 'AsyncHttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: t.Literal[True] = ...,
    cert: 'TLSClientCertType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    retries: 'RetryType' = ...,
) -> 'AsyncResponse':
    """Constructs and sends a :class:`Request <Request>`.

    :param method: method for the new :class:`Request` object: ``GET``, ``OPTIONS``, ``HEAD``, ``POST``, ``PUT``, ``PATCH``, or ``DELETE``.
    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary, list of tuples or bytes to send
        in the query string for the :class:`Request`.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) A JSON serializable Python object to send in the body of the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the :class:`Request`.
    :param files: (optional) Dictionary of ``'name': file-like-objects`` (or ``{'name': file-tuple}``) for multipart encoding upload.
        ``file-tuple`` can be a 2-tuple ``('filename', fileobj)``, 3-tuple ``('filename', fileobj, 'content_type')``
        or a 4-tuple ``('filename', fileobj, 'content_type', custom_headers)``, where ``'content_type'`` is a string
        defining the content type of the given file and ``custom_headers`` a dict-like object containing additional headers
        to add for the file.
    :param auth: (optional) Auth tuple to enable Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How many seconds to wait for the server to send data
        before giving up, as a float, or a :ref:`(connect timeout, read
        timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Boolean. Enable/disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection. Defaults to ``True``.
    :param proxies: (optional) Dictionary mapping protocol to the URL of the proxy.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
            the server's TLS certificate, or a string, in which case it must be a path
            to a CA bundle to use. Defaults to ``True``.
            It is also possible to put the certificates (directly) in a string or bytes.
    :param stream: (optional) if ``False``, the response content will be immediately downloaded.
    :param cert: (optional) if String, path to ssl client cert file (.pem). If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    :param hooks: (optional) Register functions that should be called at very specific moment in the request lifecycle.
    :param retries: (optional) If integer, determine the number of retry in case of a timeout or connection error.
            Otherwise, for fine gained retry, use directly a ``Retry`` instance from urllib3.
    :return: :class:`AsyncResponse <AsyncResponse>` object

    Usage::

      >>> from lzl.api import aioreq
      >>> req = await aioreq.arequest('GET', 'https://httpbin.org/get', stream = True)
      >>> req
      <AsyncResponse HTTP/2 [200]>
    """
    ...

async def arequest(
    method: 'HttpMethodType',
    url: str,
    *,
    retries: 'RetryType' = DEFAULT_RETRIES,
    **kwargs: t.Any,
) -> 'Response' | 'AsyncResponse':
    async with Client(
        quic_cache_layer = get_shared_quic_cache(),
        retries=retries
    ) as session:
        return await session.arequest(
            method=method,
            url=url,
            **kwargs,
        )

"""
Sync API Methods
"""

@t.overload
def get(
    url: str,
    *,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
    **kwargs: t.Any,
) -> 'Response':
    r"""Sends a GET request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

def get(
    url: str,
    *args,
    **kwargs: t.Any,
) -> 'Response':
    return request("GET", url, **kwargs)


@t.overload
def options(
    url: str,
    *,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = True,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
    **kwargs: t.Any,
) -> 'Response':
    r"""Sends a OPTIONS request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

def options(
    url: str,
    *args,
    **kwargs: t.Any,
) -> 'Response':
    return request("OPTIONS", url, **kwargs)


@t.overload
def head(
    url: str,
    *,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = True,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
    **kwargs: t.Any,
) -> 'Response':
    r"""Sends a HEAD request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to False by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

def head(
    url: str,
    *args,
    **kwargs: t.Any,
) -> 'Response':
    return request("HEAD", url, **kwargs)



@t.overload
def post(
    url: str,
    data: 'BodyType' | None = ...,
    json: t.Any | None = ...,
    *,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
) -> 'Response':
    r"""Sends a POST request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) json to send in the body of the
        :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param files: (optional) Dictionary of ``'filename': file-like-objects``
        for multipart encoding upload.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...


def post(
    url: str,
    *args,
    **kwargs: t.Any,
) -> 'Response':
    return request("POST", url, **kwargs)


@t.overload
def put(
    url: str,
    data: 'BodyType' | None = ...,
    *,
    json: t.Any | None = ...,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
) -> 'Response':
    r"""Sends a PUT request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) json to send in the body of the
        :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param files: (optional) Dictionary of ``'filename': file-like-objects``
        for multipart encoding upload.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

def put(
    url: str,
    *args,
    **kwargs: t.Any,
) -> 'Response':
    return request("PUT", url, **kwargs)


@t.overload
def patch(
    url: str,
    data: 'BodyType' | None = ...,
    *,
    json: t.Any | None = ...,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
) -> 'Response':
    r"""Sends a PATCH request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) json to send in the body of the
        :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param files: (optional) Dictionary of ``'filename': file-like-objects``
        for multipart encoding upload.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

def patch(
    url: str,
    *args,
    **kwargs: t.Any,
) -> 'Response':
    return request("PATCH", url, **kwargs)


@t.overload
def delete(
    url: str,
    *,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
    **kwargs: t.Any,
) -> 'Response':
    r"""Sends a DELETE request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

def delete(
    url: str,
    *args,
    **kwargs: t.Any,
) -> 'Response':
    return request("DELETE", url, **kwargs)

"""
Async API Methods
"""


@t.overload
async def aget(
    url: str,
    *,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: t.Literal[False] = ...,
    cert: 'TLSClientCertType' | None = ...,
    **kwargs: t.Any,
) -> 'Response':
    r"""Sends a GET request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...


@t.overload
async def aget(
    url: str,
    *,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: t.Literal[True] = ...,
    cert: 'TLSClientCertType' | None = ...,
    **kwargs: t.Any,
) -> 'AsyncResponse':
    r"""Sends a GET request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

async def aget(
    url: str,
    *args,
    **kwargs: t.Any,
) -> 'Response' | 'AsyncResponse':
    return await arequest("GET", url, **kwargs)


@t.overload
async def aoptions(
    url: str,
    *,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
    **kwargs: t.Any,
) -> 'Response' | 'AsyncResponse':
    r"""Sends a OPTIONS request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

async def aoptions(
    url: str,
    *args,
    **kwargs: t.Any,
) -> 'Response'| 'AsyncResponse':
    return await arequest("OPTIONS", url, **kwargs)


@t.overload
async def ahead(
    url: str,
    *,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
    **kwargs: t.Any,
) -> 'Response' | 'AsyncResponse':
    r"""Sends a HEAD request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to False by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

async def ahead(
    url: str,
    *args,
    **kwargs: t.Any,
) -> 'Response' | 'AsyncResponse':
    return await arequest("HEAD", url, **kwargs)


@t.overload
async def apost(
    url: str,
    data: 'BodyType' | None = ...,
    json: t.Any | None = ...,
    *,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: t.Literal[False] = ...,
    cert: 'TLSClientCertType' | None = ...,
) -> 'Response':
    r"""Sends a POST request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) json to send in the body of the
        :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param files: (optional) Dictionary of ``'filename': file-like-objects``
        for multipart encoding upload.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

@t.overload
async def apost(
    url: str,
    data: 'BodyType' | None = ...,
    json: t.Any | None = ...,
    *,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: t.Literal[True] = ...,
    cert: 'TLSClientCertType' | None = ...,
) -> 'AsyncResponse':
    r"""Sends a POST request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) json to send in the body of the
        :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param files: (optional) Dictionary of ``'filename': file-like-objects``
        for multipart encoding upload.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

async def apost(
    url: str,
    *args,
    **kwargs,
) -> 'Response' | 'AsyncResponse':
    return await arequest("POST", url, **kwargs)


@t.overload
async def aput(
    url: str,
    data: 'BodyType' | None = ...,
    *,
    json: t.Any | None = ...,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
) -> 'Response' | 'AsyncResponse':
    r"""Sends a PUT request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) json to send in the body of the
        :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param files: (optional) Dictionary of ``'filename': file-like-objects``
        for multipart encoding upload.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

async def aput(
    url: str,
    *args,
    **kwargs,
) -> 'Response' | 'AsyncResponse':
    return await arequest("PUT", url, **kwargs)


@t.overload
async def apatch(
    url: str,
    data: 'BodyType' | None = ...,
    *,
    json: t.Any | None = ...,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
) -> 'Response' | 'AsyncResponse':
    r"""Sends a PATCH request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) json to send in the body of the
        :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param files: (optional) Dictionary of ``'filename': file-like-objects``
        for multipart encoding upload.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...
    
async def apatch(
    url: str,
    *args,
    **kwargs,
) -> 'Response' | 'AsyncResponse':
    return await arequest("PATCH", url, **kwargs)


@t.overload
async def adelete(
    url: str,
    *,
    params: 'QueryParameterType' | None = ...,
    headers: 'HeadersType' | None = ...,
    cookies: 'CookiesType' | None = ...,
    auth: 'HttpAuthenticationType' | None = ...,
    timeout: 'TimeoutType' | None = ...,
    allow_redirects: bool = ...,
    proxies: 'ProxyType' | None = ...,
    hooks: 'HookType[PreparedRequest | Response]' | None = ...,
    verify: 'TLSVerifyType' = ...,
    stream: bool = ...,
    cert: 'TLSClientCertType' | None = ...,
    **kwargs: t.Any,
) -> 'Response' | 'AsyncResponse':
    r"""Sends a DELETE request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query
        string for the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the
        :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the
        :class:`Request`.
    :param auth: (optional) Auth tuple or callable to enable
        Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send
        data before giving up, as a float, or a :ref:`(connect timeout,
        read timeout) <timeouts>` tuple.
    :param allow_redirects: (optional) Set to True by default.
    :param proxies: (optional) Dictionary mapping protocol or protocol and
        hostname to the URL of the proxy.
    :param hooks: (optional) Dictionary mapping hook name to one event or
        list of events, event must be callable.
    :param stream: (optional) whether to immediately download the response
        content. Defaults to ``False``.
    :param verify: (optional) Either a boolean, in which case it controls whether we verify
        the server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``. When set to
        ``False``, requests will accept any TLS certificate presented by
        the server, and will ignore hostname mismatches and/or expired
        certificates, which will make your application vulnerable to
        man-in-the-middle (MitM) attacks. Setting verify to ``False``
        may be useful during local development or testing.
        It is also possible to put the certificates (directly) in a string or bytes.
    :param cert: (optional) if String, path to ssl client cert file (.pem).
        If Tuple, ('cert', 'key') pair, or ('cert', 'key', 'key_password').
    """
    ...

async def adelete(
    url: str,
    *args,
    **kwargs,
) -> 'Response' | 'AsyncResponse':
    return await arequest("DELETE", url, **kwargs)