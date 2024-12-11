from __future__ import annotations

"""
aiohttpx module. Formally from `growthengineai/aiohttpx`. No longer maintained there.

A Submodule for httpx that combines
the httpx.AsyncClient with the httpx.Client
to allow both async and sync requests

Usage:

```python

from lzl.api import aiohttpx

with aiohttpx.Client() as client:
    
    # Make an Async GET request
    response = await client.async_get("https://httpbin.org/get")
    print(response.json())

    # Make a Sync GET request
    response = client.get("https://httpbin.org/get")
    print(response.json())


base_url = "https://www.google.com"

async with aiohttpx.ProxyClient(base_url = base_url) as client:
    # Make an Async GET request
    response = await client.async_get(
        "/search", 
        params = {"q": "httpx"},
        soup_enabled = True
    )
    print(response.soup)
    print(response.soup.title.text)

    # Make a Sync GET request
    response = client.get(
        "/search", 
        params = {"q": "httpx"},
        soup_enabled = True
    )
    print(response.soup)
    print(response.soup.title.text)

```
"""


# import top level classes from httpx
# to allow for easy access
from lzl.load import lazy_load
h = lazy_load('httpx', install_missing = True)
h.__load__()

from httpx._api import delete, get, head, options, patch, post, put, request, stream
from httpx._auth import Auth, BasicAuth, DigestAuth
from httpx._client import USE_CLIENT_DEFAULT
from httpx._client import AsyncClient as hAsyncClient
from httpx._client import Client as hClient

from httpx._config import Limits, Proxy, Timeout, create_ssl_context
from httpx._content import ByteStream
from httpx._exceptions import (
    CloseError,
    ConnectError,
    ConnectTimeout,
    CookieConflict,
    DecodingError,
    HTTPError,
    HTTPStatusError,
    InvalidURL,
    LocalProtocolError,
    NetworkError,
    PoolTimeout,
    ProtocolError,
    ProxyError,
    ReadError,
    ReadTimeout,
    RemoteProtocolError,
    RequestError,
    RequestNotRead,
    ResponseNotRead,
    StreamClosed,
    StreamConsumed,
    StreamError,
    TimeoutException,
    TooManyRedirects,
    TransportError,
    UnsupportedProtocol,
    WriteError,
    WriteTimeout,
)

from httpx._models import Cookies, Headers, Request
from .client import Response
from httpx._status_codes import codes
from httpx._types import AsyncByteStream, SyncByteStream
try:
    from httpx._urls import URL, QueryParams
except ImportError:
    from httpx._models import URL, QueryParams
from urllib.parse import (
    urlparse, 
    urlunparse, 
    urljoin, 
    urldefrag,
    urlsplit, 
    urlunsplit, 
    urlencode, 
    parse_qs,
    parse_qsl, 
    quote, 
    quote_plus, 
    quote_from_bytes,
    unquote, 
    unquote_plus,
    unquote_to_bytes,
)

from .api import (
    async_delete, 
    async_get, 
    async_head, 
    async_options, 
    async_patch, 
    async_post, 
    async_put, 
    async_request, 
    async_stream,
    acreate_stream, 
    astream,
    aget, 
    ahead, 
    aoptions, 
    apatch, 
    apost, 
    aput, 
    arequest, 
    adelete,
    stream_iterator,
    astream_iterator,
)
from .client import Client
from .presets import PresetConfig, get_preset
from .types.params import ClientParams
from .utils.logs import mute_httpx_logger
from .utils.helpers import raise_for_status, http_retry_wrapper