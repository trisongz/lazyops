from __future__ import annotations

"""Convenience façade for LazyOps thread/async pooling utilities."""

from .base import (
    ThreadPool,
    amap_iterable,
    ensure_coro,
    get_concurrency_limit,
    is_coro_func,
    set_concurrency_limit,
)
from .utils import is_in_async_loop

__all__: list[str] = [
    "ThreadPool",
    "amap_iterable",
    "ensure_coro",
    "get_concurrency_limit",
    "is_coro_func",
    "is_in_async_loop",
    "set_concurrency_limit",
]
