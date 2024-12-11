
import ssl
import httpx
from http.cookiejar import CookieJar
from typing import (
    IO,
    AsyncIterable,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

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

PrimitiveData = Optional[Union[str, int, float, bool]]
RawURL = Tuple[bytes, bytes, Optional[int], bytes]
URLTypes = Union[httpx.URL, str]

QueryParamTypes = Union[
    httpx.QueryParams,
    Mapping[str, Union[PrimitiveData, Sequence[PrimitiveData]]],
    List[Tuple[str, PrimitiveData]],
    Tuple[Tuple[str, PrimitiveData], ...],
    str,
    bytes,
]

HeaderTypes = Union[
    httpx.Headers,
    Dict[str, str],
    Dict[bytes, bytes],
    Sequence[Tuple[str, str]],
    Sequence[Tuple[bytes, bytes]],
]

CookieTypes = Union[httpx.Cookies, CookieJar, Dict[str, str], List[Tuple[str, str]]]
CertTypes = Union[
    # certfile
    str,
    # (certfile, keyfile)
    Tuple[str, Optional[str]],
    # (certfile, keyfile, password)
    Tuple[str, Optional[str], Optional[str]],
]
VerifyTypes = Union[str, bool, ssl.SSLContext]
TimeoutTypes = Union[
    Optional[float],
    Tuple[Optional[float], Optional[float], Optional[float], Optional[float]],
    httpx.Timeout,
]
ProxiesTypes = Union[URLTypes, httpx.Proxy, Dict[URLTypes, Union[None, URLTypes, httpx.Proxy]]]

AuthTypes = Union[
    Tuple[Union[str, bytes], Union[str, bytes]],
    Callable[[httpx.Request], httpx.Request],
    httpx.Auth,
]

RequestContent = Union[str, bytes, Iterable[bytes], AsyncIterable[bytes]]
ResponseContent = Union[str, bytes, Iterable[bytes], AsyncIterable[bytes]]

RequestData = dict

FileContent = Union[IO[bytes], bytes]
FileTypes = Union[
    # file (or bytes)
    FileContent,
    # (filename, file (or bytes))
    Tuple[Optional[str], FileContent],
    # (filename, file (or bytes), content_type)
    Tuple[Optional[str], FileContent, Optional[str]],
    # (filename, file (or bytes), content_type, headers)
    Tuple[Optional[str], FileContent, Optional[str], Mapping[str, str]],
]
RequestFiles = Union[Mapping[str, FileTypes], Sequence[Tuple[str, FileTypes]]]

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


