from __future__ import annotations

"""Connection presets that provide ergonomic defaults for :class:`Client`."""

import os
import typing as t

import httpx

from .types import typed as ht

__all__ = ["PresetConfig", "Preset", "PresetMap", "get_preset"]

PresetConfig = t.Literal[
    'default', 
    'low', 
    'mid', 
    'high',
    'polling',
    'streaming',
    'scraping',
    'downloads',
]

_ncpu_cores = os.cpu_count()
_conn_unit = max(2, _ncpu_cores // 10)

class Preset(t.TypedDict):
    """Configuration blob describing httpx limits, timeouts, and retries."""
    name: str
    limits: ht.Limits
    timeout: ht.TimeoutTypes
    retries: t.Optional[int] = 2
    kwargs: t.Optional[t.Dict[str, t.Any]] = None

DefaultPreset = Preset(
    name = 'default',
    limits = ht.DEFAULT_LIMITS,
    timeout = ht.DEFAULT_TIMEOUT_CONFIG,
    retries = 2,
    kwargs = None,
)

LowPreset = Preset(
    name = 'low',
    limits = ht.Limits(
        max_connections = _conn_unit,
        max_keepalive_connections = _conn_unit,
        keepalive_expiry = _conn_unit * 2,
    ),
    timeout = ht.DEFAULT_TIMEOUT_CONFIG,
    retries = 2,
    kwargs = None,
)

MidPreset = Preset(
    name = 'mid',
    limits = ht.Limits(
        max_connections = _conn_unit * 2,
        max_keepalive_connections = _conn_unit * 2,
        keepalive_expiry = _conn_unit * 4,
    ),
    timeout = httpx.Timeout(timeout = 15.0),
    retries = 5,
    kwargs = {'follow_redirects': True},
)

HighPreset = Preset(
    name = 'high',
    limits = ht.Limits(
        max_connections = _conn_unit * 4,
        max_keepalive_connections = _conn_unit * 4,
        keepalive_expiry = _conn_unit * 8,
    ),
    timeout = httpx.Timeout(timeout = 60.0),
    retries = 10,
    kwargs = {'follow_redirects': True, 'disable_httpx_logger': True},
)

PollingPreset = Preset(
    name = 'polling',
    limits = ht.Limits(
        max_connections = _conn_unit * 4,
        max_keepalive_connections = _conn_unit * 4,
        keepalive_expiry = _conn_unit * 8,
    ),
    timeout = httpx.Timeout(timeout = 120.0),
    retries = 5,
    kwargs = {'follow_redirects': True, 'disable_httpx_logger': True},
)

StreamingPreset = Preset(
    name = 'streaming',
    limits = ht.Limits(
        max_connections = _conn_unit * 4,
        max_keepalive_connections = _conn_unit * 4,
        keepalive_expiry = _conn_unit * 8,
    ),
    timeout = httpx.Timeout(timeout = 240.0),
    retries = 5,
    kwargs = {'follow_redirects': True, 'disable_httpx_logger': True},
)

ScrapingPreset = Preset(
    name = 'scraping',
    limits = ht.Limits(
        max_connections = _conn_unit * 4,
        max_keepalive_connections = _conn_unit * 4,
        keepalive_expiry = _conn_unit * 8,
    ),
    timeout = httpx.Timeout(timeout = 300.0),
    retries = 10,
    kwargs = {'follow_redirects': True, 'verify': False, 'disable_httpx_logger': True},
)

DownloadsPreset = Preset(
    name = 'downloads',
    limits = ht.Limits(
        max_connections = _conn_unit * 4,
        max_keepalive_connections = _conn_unit * 4,
        keepalive_expiry = _conn_unit * 8,
    ),
    timeout = httpx.Timeout(timeout = 600.0),
    retries = 5,
    kwargs = {'follow_redirects': True, 'disable_httpx_logger': True},
)

PresetMap: t.Dict[str, Preset] = {
    'default': DefaultPreset,
    'low': LowPreset,
    'mid': MidPreset,
    'high': HighPreset,
    'polling': PollingPreset,
    'streaming': StreamingPreset,
    'scraping': ScrapingPreset,
    'downloads': DownloadsPreset,
}

def get_preset(name: PresetConfig) -> t.Optional[Preset]:
    """Return the preset definition for *name* if one is registered."""

    return PresetMap.get(name)
