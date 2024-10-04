from __future__ import annotations

"""
Unified API Client based on `niquests`
"""
import typing as t
from .client import Client, DEFAULT_RETRIES, DEFAULT_TIMEOUT
from .api import (
    request,
    arequest,
    get,
    aget,
    put,
    aput,
    patch,
    apatch,
    head,
    ahead,
    options,
    aoptions,
    delete,
    adelete,
    post,
    apost,   
)

if t.TYPE_CHECKING:
    from niquests import Response, AsyncResponse
    from niquests.sessions import HttpAuthenticationType, HttpMethodType, QueryParameterType, BodyType, HeadersType, CookiesType, MultiPartFilesType, MultiPartFilesAltType, TimeoutType, ProxyType, HookType, TLSVerifyType, TLSClientCertType
    from niquests.sessions import PreparedRequest
    from niquests._async import RetryType
    from niquests._typing import AsyncHttpAuthenticationType, AsyncBodyType
    from niquests.structures import QuicSharedCache
    from niquests._async import AsyncBaseAdapter
    from niquests.exceptions import (
        ConnectionError,
        ConnectTimeout,
        FileModeWarning,
        HTTPError,
        JSONDecodeError,
        ReadTimeout,
        RequestException,
        RequestsDependencyWarning,
        Timeout,
        TooManyRedirects,
        URLRequired,
    )
