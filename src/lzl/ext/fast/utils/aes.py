from __future__ import annotations

"""
FastAPI Helpers
"""

import functools
from lzl.proxied import ProxyObject
from typing import Optional, List, Dict, Any, Union, Type, Callable, TYPE_CHECKING


if TYPE_CHECKING:
    from Cryptodome.Cipher import AES
    from Cryptodome.Cipher._mode_ecb import EcbMode
    from lzl.io import JsonSerializer

serializer: 'JsonSerializer' = ProxyObject(
    obj_getter = 'lzl.io.ser.get_serializer',
    obj_args = ('json',)
)


def create_aes_object(
    secret_key: str,
    access_key: str,
) -> Callable[..., 'EcbMode']:
    """
    Creates an AES Object that can be repeatedly used
    """
    from Cryptodome.Cipher import AES
    return functools.partial(AES.new, secret_key.encode(), AES.MODE_CFB, access_key.encode())

