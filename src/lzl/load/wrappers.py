from __future__ import annotations

"""Helpers for lazily initialising higher-order function wrappers."""

import functools
import typing as t

ReturnT = t.TypeVar("ReturnT")


def lazy_function_wrapper(
    function: t.Callable[..., ReturnT],
    *function_args: t.Any,
    **function_kwargs: t.Any,
) -> t.Callable[[t.Callable[..., ReturnT]], t.Callable[..., ReturnT]]:
    """Defer wrapper creation until the wrapped function is first invoked.

    The initialiser ``function`` is executed at most once.  It may return a
    callable that itself accepts the original function and returns a wrapped
    version.  When ``function`` returns ``None`` the original callable is used
    as-is, preserving the legacy behaviour relied on by existing integrations.
    """

    _initialized = False
    _initialized_function: t.Optional[t.Callable[[t.Callable[..., ReturnT]], t.Callable[..., ReturnT]]] = None

    def lazywrapped(func: t.Callable[..., ReturnT]) -> t.Callable[..., ReturnT]:
        from lzl.pool import ThreadPool, is_coro_func

        if is_coro_func(func):
            @functools.wraps(func)
            async def _wrapper(*args: t.Any, **kwargs: t.Any) -> ReturnT:
                nonlocal _initialized, _initialized_function
                if not _initialized:
                    _initialized_function = await ThreadPool.asyncish(
                        function,
                        *function_args,
                        **function_kwargs,
                    )
                    _initialized = True
                if _initialized_function is None:
                    return await func(*args, **kwargs)
                return await _initialized_function(func)(*args, **kwargs)

            return _wrapper

        @functools.wraps(func)
        def _wrapper(*args: t.Any, **kwargs: t.Any) -> ReturnT:
            nonlocal _initialized, _initialized_function
            if not _initialized:
                _initialized_function = function(*function_args, **function_kwargs)
                _initialized = True
            if _initialized_function is None:
                return func(*args, **kwargs)
            return _initialized_function(func)(*args, **kwargs)

        return _wrapper

    return lazywrapped
