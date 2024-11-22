from __future__ import annotations


"""
Middleware Utilities
"""

import os
import sys
import typing
from uuid import uuid4
from pathlib import Path
from starlette.datastructures import MutableHeaders, Secret
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from typing import Any, Dict, List, Optional, Union, Type, TYPE_CHECKING, Callable, Awaitable
from lzl.logging import logger
from lzl.types import Literal

if TYPE_CHECKING:
    from lzl.io import PersistentDict
    from lzl.pool import ThreadPool

try:
    import xxhash

    def hash_func(data: str) -> str:
        """
        Returns the hash of the data
        """
        return xxhash.xxh128_hexdigest(data)

except ImportError:
    import hashlib

    def hash_func(data: str) -> str:
        """
        Returns the hash of the data
        """
        return hashlib.sha256(data.encode()).hexdigest()

def create_session_key(*keys: str) -> str:
    """
    Creates a session key
    """
    joined_keys = ':'.join(keys)
    return hash_func(joined_keys)

def get_pdict(
    base_key: str,
    redis_url: Optional[str] = None,
    serializer: Optional[str] = 'json',
    serializer_kwargs: Optional[Dict[str, Any]] = None,
    expiration: Optional[int] = None,
    allow_local_fallback: bool = True,
    local_cache_file: Optional[Path] = None,
    session_name: Optional[str] = 'fastapi.session',
    **kwargs,
) -> 'PersistentDict':
    """
    Returns the Persistent Dict for data
    """
    try:
        from kvdb import KVDBClient
        sess = KVDBClient.get_session(
            name = session_name,
            url = redis_url,
        )
        from lzo.utils.helpers.base import fail_after
        fail_func = fail_after(5)(sess.ping)
        try:
            # with fail_after(5):
            #     sess.ping()
            fail_func()
        except Exception as e:
            if not allow_local_fallback: raise ValueError(f'KVDB Sesssion is not available and local fallback is not allowed: {e}') from e
            logger.warning(f'KVDB Sesssion is not available and local fallback is not allowed: {e}')
            sess = None
    except ImportError as e:
        if not allow_local_fallback: raise ImportError('Persistent Dict is not available and local fallback is not allowed') from e
    
    if sess is not None:
        return sess.create_persistence(
            base_key = base_key,
            serializer = serializer,
            expiration = expiration,
            serializer_kwargs = serializer_kwargs,
            **kwargs,
        )
    from lzl.io.persistence import PersistentDict
    return PersistentDict(
        base_key = base_key,
        serializer = serializer,
        expiration = expiration,
        serializer_kwargs = serializer_kwargs,
        file_path = local_cache_file,
        **kwargs,
    )


