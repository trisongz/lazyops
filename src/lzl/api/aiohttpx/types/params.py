from __future__ import annotations


import httpx
import typing as t
from lzl.types import BaseModel, ConfigDict
from . import typed as ht

class ClientParams(BaseModel):
    """
    Used to store the params for the Client class
    """
    auth: t.Optional[ht.AuthTypes] = None
    params: t.Optional[ht.QueryParamTypes] = None
    headers: t.Optional[ht.HeaderTypes] = None
    cookies: t.Optional[ht.CookieTypes] = None
    verify: t.Optional[ht.VerifyTypes] = None
    cert: t.Optional[ht.CertTypes] = None
    http1: t.Optional[bool] = None
    http2: t.Optional[bool] = None
    proxies: t.Optional[ht.ProxiesTypes] = None

    mounts: t.Optional[t.Mapping[str, httpx._client.BaseTransport]] = None
    async_mounts: t.Optional[t.Mapping[str, httpx._client.AsyncBaseTransport]] = None

    timeout: t.Optional[
        t.Union[t.Optional[float], t.Tuple[t.Optional[float], t.Optional[float], t.Optional[float], t.Optional[float]],
        httpx._client.Timeout,
    ]] = httpx._client.DEFAULT_TIMEOUT_CONFIG
    follow_redirects: t.Optional[bool] = None
    retries: t.Optional[int] = None
    limits: httpx._client.Limits = httpx._client.DEFAULT_LIMITS
    max_redirects: int = httpx._client.DEFAULT_MAX_REDIRECTS
    event_hooks: t.Optional[t.Mapping[str, t.List[t.Callable]]] = None
    async_event_hooks: t.Optional[t.Mapping[str, t.List[t.Callable]]] = None
    base_url: t.Optional[t.Union[str, httpx._client.URL]] = ""
    transport: t.Optional[httpx._client.BaseTransport] = None
    async_transport: t.Optional[httpx._client.AsyncBaseTransport] = None

    app: t.Optional[t.Callable] = None
    trust_env: t.Optional[bool] = None
    default_encoding: str = "utf-8"
    kwargs: t.Any = None
    debug: t.Optional[bool] = None
    soup_enabled: t.Optional[bool] = None

    model_config = ConfigDict(extra = 'allow', arbitrary_types_allowed = True)

    @property
    def sync_kwargs(self) -> t.Dict:
        """
        Returns the sync kwargs
        """
        data = self.model_dump(
            exclude_none = True, 
            exclude = {'async_transport', 'async_mounts', 'async_event_hooks', 'soup_enabled', 'debug', 'retries', 'proxies'}
        )
        if self.proxies: data['proxy'] = self.proxies
        kwargs = data.pop('kwargs', None)
        if kwargs: data.update(kwargs)
        return data
    
    @property
    def async_kwargs(self) -> t.Dict:
        """
        Returns the async kwargs
        """
        data = self.model_dump(
            exclude_none = True, 
            exclude = {'soup_enabled', 'debug', 'retries', 'proxies'}
        )
        if self.proxies: data['proxy'] = self.proxies
        if data.get('async_transport'):
            data['transport'] = data.pop('async_transport', None)
        if data.get('async_mounts'):
            data['mounts'] = data.pop('async_mounts', None)
        if data.get('async_event_hooks'):
            data['event_hooks'] = data.pop('async_event_hooks', None)
        kwargs = data.pop('kwargs', None)
        if kwargs: data.update(kwargs)
        return data
