from __future__ import annotations

"""
ThreadPool Implementation

- v3: Transform into a singleton proxy object class
- this is now imported from `lazyops.libs.pooler`
"""

from lazyops.libs.pooler import (
    set_concurrency_limit,
    get_concurrency_limit,
    is_coro_func,
    ThreadPool,
    ThreadPoolV2,
    ThreadPooler,
    ensure_coro,
)
