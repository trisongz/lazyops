"""Shared typing primitives for :mod:`lzl.api.aiohttpx`."""

import ssl
from http.cookiejar import CookieJar
import typing as t

import httpx

__all__ = [
    "PrimitiveData",
    "RawURL",
    "URLTypes",
    "QueryParamTypes",
    "HeaderTypes",
    "CookieTypes",
    "CertTypes",
    "VerifyTypes",
    "TimeoutTypes",
    "ProxiesTypes",
    "AuthTypes",
    "RequestContent",
    "ResponseContent",
    "RequestData",
    "FileContent",
    "FileTypes",
    "RequestFiles",
    "UseClientDefault",
    "Request",
    "Response",
    "BaseTransport",
    "AsyncBaseTransport",
    "TracebackType",
    "Limits",
]

PrimitiveData = t.Optional[t.Union[str, int, float, bool]]
RawURL = t.Tuple[bytes, bytes, t.Optional[int], bytes]
URLTypes = t.Union[httpx.URL, str]

QueryParamTypes = t.Union[
    httpx.QueryParams,
    t.Mapping[str, t.Union[PrimitiveData, t.Sequence[PrimitiveData]]],
    t.List[t.Tuple[str, PrimitiveData]],
    t.Tuple[t.Tuple[str, PrimitiveData], ...],
    str,
    bytes,
]

HeaderTypes = t.Union[
    httpx.Headers,
    t.Dict[str, str],
    t.Dict[bytes, bytes],
    t.Sequence[t.Tuple[str, str]],
    t.Sequence[t.Tuple[bytes, bytes]],
]

CookieTypes = t.Union[httpx.Cookies, CookieJar, t.Dict[str, str], t.List[t.Tuple[str, str]]]
CertTypes = t.Union[
    # certfile
    str,
    # (certfile, keyfile)
    t.Tuple[str, t.Optional[str]],
    # (certfile, keyfile, password)
    t.Tuple[str, t.Optional[str], t.Optional[str]],
]
VerifyTypes = t.Union[str, bool, ssl.SSLContext]
TimeoutTypes = t.Union[
    t.Optional[float],
    t.Tuple[t.Optional[float], t.Optional[float], t.Optional[float], t.Optional[float]],
    httpx.Timeout,
]
ProxiesTypes = t.Union[URLTypes, httpx.Proxy, t.Dict[URLTypes, t.Union[None, URLTypes, httpx.Proxy]]]

AuthTypes = t.Union[
    t.Tuple[t.Union[str, bytes], t.Union[str, bytes]],
    t.Callable[[httpx.Request], httpx.Request],
    httpx.Auth,
]

RequestContent = t.Union[str, bytes, t.Iterable[bytes], t.AsyncIterable[bytes]]
ResponseContent = t.Union[str, bytes, t.Iterable[bytes], t.AsyncIterable[bytes]]

RequestData = t.Dict[str, t.Any]

FileContent = t.Union[t.IO[bytes], bytes]
FileTypes = t.Union[
    # file (or bytes)
    FileContent,
    # (filename, file (or bytes))
    t.Tuple[t.Optional[str], FileContent],
    # (filename, file (or bytes), content_type)
    t.Tuple[t.Optional[str], FileContent, t.Optional[str]],
    # (filename, file (or bytes), content_type, headers)
    t.Tuple[t.Optional[str], FileContent, t.Optional[str], t.Mapping[str, str]],
]
RequestFiles = t.Union[t.Mapping[str, FileTypes], t.Sequence[t.Tuple[str, FileTypes]]]

# Aliasing 

UseClientDefault = httpx._client.UseClientDefault
Response = httpx.Response
Request = httpx.Request

BaseTransport = httpx.BaseTransport
AsyncBaseTransport = httpx.AsyncBaseTransport
TracebackType = httpx._client.TracebackType
Limits = httpx.Limits

DEFAULT_TIMEOUT_CONFIG = httpx._client.DEFAULT_TIMEOUT_CONFIG
DEFAULT_LIMITS = httpx._client.DEFAULT_LIMITS
DEFAULT_MAX_REDIRECTS = httpx._client.DEFAULT_MAX_REDIRECTS
