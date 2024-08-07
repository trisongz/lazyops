"""
Migrated from lazyops.utils.pooler to allow for non-dependent 3rd party libraries
"""

from .base import (
    set_concurrency_limit,
    get_concurrency_limit,
    is_coro_func,
    amap_iterable,
    ThreadPool,
    ensure_coro,
)

from .utils import is_in_async_loop