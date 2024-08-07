from __future__ import annotations

"""
FastAPI Helpers
"""
import functools
from lazyops.libs.proxyobj import ProxyObject
from typing import Optional, List, Dict, Any, Union, Type, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request
    from kvdb import PersistentDict, KVDBSession
    from kvdb.io.serializers import JsonSerializer
    from Cryptodome.Cipher import AES
    from Cryptodome.Cipher._mode_ecb import EcbMode


serializer: 'JsonSerializer' = ProxyObject(
    obj_getter = 'kvdb.io.serializers.get_serializer',
    obj_args = ('json',)
)


def get_app_endpoint(
    request: 'Request',
    valid_domains: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Returns the app endpoint
    """
    if valid_domains and not any(
        domain in request.url.hostname for 
        domain in valid_domains
    ): 
        return None
    scheme = 'https' if request.url.port == 443 else request.url.scheme
    endpoint = f'{scheme}://{request.url.hostname}'
    if request.url.port and request.url.port not in {80, 443}:
        endpoint += f':{request.url.port}'
    return endpoint

def create_aes_object(
    secret_key: str,
    access_key: str,
) -> Callable[..., 'EcbMode']:
    """
    Creates an AES Object that can be repeatedly used
    """
    from Cryptodome.Cipher import AES
    return functools.partial(AES.new, secret_key.encode(), AES.MODE_CFB, access_key.encode())

