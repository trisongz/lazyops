from __future__ import annotations

"""
Lazy Loading Utilities
"""

from lazyops.libs import lazyload
from lazyops.libs.pooler import ThreadPooler
from lazyops.utils.logs import logger
from typing import Any, Callable, Dict, List, Optional, Union

if lazyload.TYPE_CHECKING:
    from lazyops.libs.authzero.configs import AuthZeroSettings
    from kvdb import KVDBSession, PersistentDict, KVDBClient
else:
    KVDBClient = lazyload.LazyLoad("kvdb.KVDBClient", package = 'kvdb')


_az_sessions_configured: Optional[bool] = False
_az_kdbs: Dict[str, 'KVDBSession'] = {}
_az_pdicts: Dict[str, 'PersistentDict'] = {}
_az_pdict_aliases: Dict[str, str] = {}
_az_settings: Optional['AuthZeroSettings'] = None

def get_az_kdb(
    name: Optional[str] = None,
    serializer: Optional[str] = 'json',
    **kwargs,
) -> 'KVDBSession':
    """
    Returns the KVDB Session
    """
    global _az_kdbs
    if name is None: name = 'global'
    if name not in _az_kdbs:
        _az_kdbs[name] = KVDBClient.get_session(
            name = name,
            serializer = serializer,
            **kwargs,
        )
    return _az_kdbs[name]

def get_az_pdict(
    base_key: str,
    expiration: Optional[int] = None,
    aliases: Optional[List[str]] = None,
    hset_disabled: Optional[bool] = False,
    **kwargs,
) -> 'PersistentDict':
    """
    Lazily initializes the persistent dict
    """
    global _az_pdicts, _az_pdict_aliases
    if base_key not in _az_pdicts and base_key not in _az_pdict_aliases:
        sess = get_az_kdb(
            'persistence',
            serializer = None,
        )
        _az_pdicts[base_key] = sess.create_persistence(
            base_key = base_key,
            expiration = expiration,
            hset_disabled = hset_disabled,
            **kwargs,
        )
        if aliases:
            for alias in aliases:
                _az_pdict_aliases[alias] = base_key
    elif base_key in _az_pdict_aliases:
        base_key = _az_pdict_aliases[base_key]
    return _az_pdicts[base_key]




def get_az_settings() -> 'AuthZeroSettings':
    """
    Returns the AuthZero Settings
    """
    global _az_settings
    if _az_settings is None:
        from authzero.configs import AuthZeroSettings
        _az_settings = AuthZeroSettings()
    return _az_settings