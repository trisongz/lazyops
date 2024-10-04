from __future__ import annotations

"""
Niquests API Client
"""


import atexit
import typing as t
from lzl import load
from urllib.parse import urljoin
from .utils import logger

if load.TYPE_CHECKING:
    import niquests
    from niquests import Session, AsyncSession, Response, AsyncResponse
    from niquests.sessions import ResolverType, HttpAuthenticationType, HttpMethodType, QueryParameterType, BodyType, HeadersType, CookiesType, MultiPartFilesType, MultiPartFilesAltType, TimeoutType, ProxyType, HookType, TLSVerifyType, TLSClientCertType
    from niquests.sessions import PreparedRequest, BaseAdapter
    from niquests._async import AsyncResolverType, CacheLayerAltSvcType, RetryType
    from niquests._typing import AsyncHttpAuthenticationType, AsyncBodyType
    from niquests._async import AsyncBaseAdapter
else:
    niquests = load.LazyLoad("niquests", install_missing = True)


DEFAULT_POOLBLOCK: bool = False
DEFAULT_POOLSIZE: int = 10
DEFAULT_RETRIES: 'RetryType' = 0
DEFAULT_TIMEOUT: 'TimeoutType' = 120


class Client:
    """A Unified Requests Client.

    Provides cookie persistence, connection-pooling, and configuration.

    Basic Usage::

      >>> import niquests
      >>> s = niquests.AsyncSession()
      >>> await s.get('https://httpbin.org/get')
      <Response HTTP/2 [200]>

    Or as a context manager::

      >>> async with niquests.AsyncSession() as s:
      ...     await s.get('https://httpbin.org/get')
      <Response HTTP/2 [200]>
    """


    def __init__(
        self,
        *,
        base_url: t.Optional[str] = None,
        headers: t.Optional[t.Dict[str, str]] = None,
        auth: t.Optional['HttpAuthenticationType'] = None,
        proxies: 'ProxyType' | None = None,
        cookies: 'CookiesType' | None = None,
        verify: 'TLSVerifyType' = None,
        allow_redirects: bool = None,
        timeout: 'TimeoutType' = None,
        cert: 'TLSClientCertType' | None = None,
        hooks: 'HookType[PreparedRequest | Response]' | None = None,
        ahooks: 'HookType[PreparedRequest | Response]' | None = None,

        resolver: 'AsyncResolverType' | 'ResolverType' | None = None, 
        source_address: tuple[str, int] | None = None,
        quic_cache_layer: 'CacheLayerAltSvcType' | None = None,
        retries: 'RetryType' = DEFAULT_RETRIES,
        multiplexed: bool = False,
        disable_http1: bool = False,
        disable_http2: bool = False,
        disable_http3: bool = False,
        disable_ipv6: bool = False,
        disable_ipv4: bool = False,
        pool_connections: int = DEFAULT_POOLSIZE,
        pool_maxsize: int = DEFAULT_POOLSIZE,
        happy_eyeballs: bool | int = False,
        auto_close_on_exit: t.Optional[bool] = True,
        **kwargs,
    ):
        """
        Initialize a new Client. This is a wrapper around `niquests.Session` and `niquests.AsyncSession`.

        It allows setting intial headers, auth, proxies, cookies, verify, allow_redirects, timeout, and cert.
        that are used for all requests.


        """
        self.base_url = base_url
        self._base_headers = headers or {}
        self._base_auth = auth
        self._base_proxies = proxies
        self._base_cookies = cookies
        self._base_verify = verify
        if 'follow_redirects' in kwargs: allow_redirects = kwargs.pop('follow_redirects')
        
        self._base_allow_redirects = allow_redirects
        self._base_timeout = timeout
        self._base_cert = cert
        self._base_hooks = hooks
        self._base_ahooks = ahooks

        self._auto_close_on_exit = auto_close_on_exit

        self._io: t.Optional['Session'] = None
        self._aio: t.Optional['AsyncSession'] = None
        self._extra: t.Dict[str, t.Any] = {}
        self._client_kwargs: t.Dict[str, t.Any] = {
            'resolver': resolver,
            'source_address': source_address,
            'quic_cache_layer': quic_cache_layer,
            'retries': retries,
            'multiplexed': multiplexed,
            'disable_http1': disable_http1,
            'disable_http2': disable_http2,
            'disable_http3': disable_http3,
            'disable_ipv6': disable_ipv6,
            'disable_ipv4': disable_ipv4,
            'pool_connections': pool_connections,
            'pool_maxsize': pool_maxsize,
            'happy_eyeballs': happy_eyeballs,
        }

    def _get_url_(self, url: str) -> str:
        """
        Returns the URL
        """
        return urljoin(self.base_url, url) if self.base_url else url
    
    def _get_request_kwargs_(self, method: str, **kwargs) -> t.Dict[str, t.Any]:
        """
        Returns the request kwargs
        """
        method = method.upper()
        if 'cert' not in kwargs and self._base_cert:
            kwargs['cert'] = self._base_cert
        if 'timeout' not in kwargs and self._base_timeout is not None:
            kwargs['timeout'] = self._base_timeout
        if 'allow_redirects' not in kwargs and self._base_allow_redirects is not None:
            kwargs['allow_redirects'] = self._base_allow_redirects
        return kwargs


    def _update_session_(self, session: t.Union['Session', 'AsyncSession']) -> t.Union['Session', 'AsyncSession']:
        # sourcery skip: merge-else-if-into-elif
        """
        Updates the session
        """
        if self._base_headers: session.headers.update(self._base_headers)
        if self._base_auth: session.auth = self._base_auth
        if self._base_proxies: session.proxies.update(self._base_proxies)
        if self._base_cookies: session.cookies.update(self._base_cookies)
        if self._base_verify is not None: session.verify = self._base_verify
        # This is the async session
        if hasattr(session, '__aenter__'):
            if self._base_ahooks: session.hooks.update(self._base_ahooks)
        else:
            if self._base_hooks: session.hooks.update(self._base_hooks)
        return session
        
    
    @property
    def io(self) -> 'Session':
        """
        Returns the io session
        """
        if self._io is None:
            self._io = niquests.Session(**self._client_kwargs)
            self._io = self._update_session_(self._io)
            if self._auto_close_on_exit:
                atexit.register(self.close)
        return self._io
    
    @property
    def aio(self) -> 'AsyncSession':
        """
        Returns the async session
        """
        if self._aio is None:
            self._aio = niquests.AsyncSession(**self._client_kwargs)
            self._aio = self._update_session_(self._aio)
            if self._auto_close_on_exit:
                from lzo.utils import aexit as aioexit
                aioexit.register(self.aclose)
        return self._aio
    
    def close(self):
        """
        Closes the client
        """
        if self._io is not None: 
            self._io.close()
            self._io = None

    async def aclose(self):
        """
        Closes the client
        """
        self.close()
        if self._aio is not None: 
            await self._aio.close()
            self._aio = None
    
    """
    Sync Client Methods
    """

    @t.overload
    def request(
        self,
        method: 'HttpMethodType',
        url: str,
        params: 'QueryParameterType' | None = ...,
        data: 'BodyType' | None = ...,
        headers: 'HeadersType' | None = ...,
        cookies: 'CookiesType' | None = ...,
        files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
        auth: 'HttpAuthenticationType' | None = ...,
        timeout: 'TimeoutType' | None = ...,
        allow_redirects: bool = True,
        proxies: 'ProxyType' | None = ...,
        hooks: 'HookType[PreparedRequest | Response]' | None = ...,
        stream: bool | None = ...,
        verify: 'TLSVerifyType' | None = ...,
        cert: 'TLSClientCertType' | None = ...,
        json: t.Any | None = ...,
    ) -> 'Response':
        """Constructs a :class:`Request <Request>`, prepares it and sends it.
        Returns :class:`Response <Response>` object.

        :param method: method for the new :class:`Request` object.
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
    
    def request(
        self,
        method: 'HttpMethodType',
        url: str,
        **kwargs,
    ) -> 'Response':
        url = self._get_url_(url)
        kwargs = self._get_request_kwargs_(method, **kwargs)
        return self.io.request(method, url, **kwargs)

    @t.overload
    def get(
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response':
        return self.request(
            "GET",
            url,
            **kwargs,
        )

    @t.overload
    def options(
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response':
        return self.request(
            "OPTIONS",
            url,
            **kwargs,
        )

    @t.overload
    def head(
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response':
        return self.request(
            "HEAD",
            url,
            **kwargs,
        )

    @t.overload
    def post(
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response':
        return self.request("POST", url, **kwargs)

    @t.overload
    def put(
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response':
        return self.request("PUT", url, **kwargs)

    @t.overload
    def patch(
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response':
        return self.request("PATCH", url, **kwargs)

    @t.overload
    def delete(
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response':
        return self.request("DELETE", url, **kwargs)

    
    def gather(self, *responses: 'Response', max_fetch: int | None = None) -> None:
        """
        Call this method to make sure in-flight responses are retrieved efficiently. This is a no-op
        if multiplexed is set to False (which is the default value). Passing a limited set of responses
        will wait for given promises and discard others for later.

        :param max_fetch: Maximal number of response to be fetched before exiting the loop.
               By default, it waits until all pending (lazy) response are resolved.
        """
        return self.io.gather(*responses, max_fetch = max_fetch)
    

    def mount(self, prefix: str, adapter: 'BaseAdapter') -> None:
        """Registers a connection adapter to a prefix.

        Adapters are sorted in descending order by prefix length.
        """
        return self.io.mount(prefix, adapter)
    

    def get_adapter(self, url: str) -> 'BaseAdapter':
        """
        Returns the appropriate connection adapter for the given URL.
        """
        return self.io.get_adapter(url)


    def get_redirect_target(self, resp: 'Response') -> str | None:
        """Receives a Response. Returns a redirect URI or ``None``"""
        return self.io.get_redirect_target(resp)

    """
    Async Client Methods
    """


    @t.overload  # type: ignore[override]
    async def arequest(
        self,
        method: 'HttpMethodType',
        url: str,
        params: 'QueryParameterType' | None = ...,
        data: 'BodyType' | 'AsyncBodyType' | None = ...,
        headers: 'HeadersType' | None = ...,
        cookies: 'CookiesType' | None = ...,
        files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
        auth: 'HttpAuthenticationType' | 'AsyncHttpAuthenticationType' | None = ...,
        timeout: 'TimeoutType' | None = ...,
        allow_redirects: bool = ...,
        proxies: 'ProxyType' | None = ...,
        hooks: 'HookType[PreparedRequest | Response]' | None = ...,
        *,
        stream: t.Literal[True] = True,
        verify: 'TLSVerifyType' | None = ...,
        cert: 'TLSClientCertType' | None = ...,
        json: t.Any | None = ...,
    ) -> 'AsyncResponse': 
        """Constructs a :class:`Request <Request>`, prepares it and sends it.
        Returns :class:`Response <Response>` object.

        :param method: method for the new :class:`Request` object.
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
        
        :return: :class:`AsyncResponse <AsyncResponse>` object
        """
        ...

        
    @t.overload  # type: ignore[override]
    async def arequest(
        self,
        method: 'HttpMethodType',
        url: str,
        params: 'QueryParameterType' | None = ...,
        data: 'BodyType' | 'AsyncBodyType' | None = ...,
        headers: 'HeadersType' | None = ...,
        cookies: 'CookiesType' | None = ...,
        files: 'MultiPartFilesType' | 'MultiPartFilesAltType' | None = ...,
        auth: 'HttpAuthenticationType' | 'AsyncHttpAuthenticationType' | None = ...,
        timeout: 'TimeoutType' | None = ...,
        allow_redirects: bool = ...,
        proxies: 'ProxyType' | None = ...,
        hooks: 'HookType[PreparedRequest | Response]' | None = ...,
        stream: t.Literal[False] = False,
        verify: 'TLSVerifyType' | None = ...,
        cert: 'TLSClientCertType' | None = ...,
        json: t.Any | None = ...,
    ) -> 'Response':
        """Constructs a :class:`Request <Request>`, prepares it and sends it.
        Returns :class:`Response <Response>` object.

        :param method: method for the new :class:`Request` object.
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
        
        :return: :class:`Response <Response>` object
        """
        ...

    async def arequest(  # type: ignore[override]
        self,
        method: 'HttpMethodType',
        url: str,
        **kwargs,
    ) -> 'Response' | 'AsyncResponse':
        url = self._get_url_(url)
        kwargs = self._get_request_kwargs_(method, **kwargs)
        return await self.aio.request(method, url, **kwargs)
    

    @t.overload
    async def aget(
        self,
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
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response' | 'AsyncResponse':
        return await self.arequest(
            "GET",
            url,
            **kwargs,
        )

    @t.overload
    async def aoptions(
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response' | 'AsyncResponse':
        return await self.arequest(
            "OPTIONS",
            url,
            **kwargs,
        )

    @t.overload
    async def ahead(
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response' | 'AsyncResponse':
        return await self.arequest(
            "HEAD",
            url,
            **kwargs,
        )

    @t.overload
    async def apost(
        self,
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
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response' | 'AsyncResponse':
        return await self.arequest("POST", url, **kwargs)

    @t.overload
    async def aput(
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response' | 'AsyncResponse':
        return await self.arequest("PUT", url, **kwargs)

    @t.overload
    async def apatch(
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response' | 'AsyncResponse':
        return await self.arequest("PATCH", url, **kwargs)


    @t.overload
    async def adelete(
        self,
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
        self,
        url: str,
        *args,
        **kwargs,
    ) -> 'Response' | 'AsyncResponse':
        return await self.arequest("DELETE", url, **kwargs)

    async def agather(
        self, 
        *responses: 'Response', 
        max_fetch: int | None = None
    ) -> None:  # type: ignore[override]
        """
        Call this method to make sure in-flight responses are retrieved efficiently. This is a no-op
        if multiplexed is set to False (which is the default value). Passing a limited set of responses
        will wait for given promises and discard others for later.

        :param max_fetch: Maximal number of response to be fetched before exiting the loop.
               By default, it waits until all pending (lazy) response are resolved.
        """
        return await self.aio.gather(*responses, max_fetch = max_fetch)


    def amount(self, prefix: str, adapter: 'AsyncBaseAdapter') -> None:  # type: ignore[override]
        """Registers a connection adapter to a prefix.

        Adapters are sorted in descending order by prefix length.
        """
        return self.aio.mount(prefix, adapter)  # type: ignore[arg-type]
    
    def aget_adapter(self, url: str) -> 'AsyncBaseAdapter':  # type: ignore[override]
        """
        Returns the appropriate connection adapter for the given URL.
        """
        return self.aio.get_adapter(url)  # type: ignore[arg-type]
    

    """
    Client Class Methods
    """

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc, value, tb):
        await self.aclose()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()