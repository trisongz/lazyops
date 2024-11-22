from __future__ import annotations

"""
FastAPI Helpers
"""

from lzl.proxied import ProxyObject
from typing import Optional, List, Dict, Any, Union, Type, Callable, TYPE_CHECKING


if TYPE_CHECKING:
    from lzl.io import JsonSerializer

serializer: 'JsonSerializer' = ProxyObject(
    obj_getter = 'lzl.io.ser.get_serializer',
    obj_args = ('json',)
)
