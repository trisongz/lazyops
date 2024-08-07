from __future__ import annotations

"""
Lazy Function Wrappers
"""
import functools
from lazyops.libs.pooler import is_coro_func, ThreadPooler
from typing import TypeVar, Callable, Any

WrappedFnReturnT = TypeVar("WrappedFnReturnT")
WrappedFn = TypeVar("WrappedFn", bound = Callable[..., Any])
ReturnT = TypeVar("ReturnT")


def lazy_function_wrapper(
    function: Callable[..., ReturnT],
    *function_args,
    **function_kwargs,
) -> Callable[..., ReturnT]:
    """
    Lazy Function Wrapper

    This function is used to handle lazily initializing a wrapper function (retry, etc)
    The execution of the function is deferred until the first call to the wrapper function

    If the returned function is None after initialization is called with arguments, then
    the initialized function will not be wrapped and the original function will be returned
    """
    _initialized = False
    _initialized_function = None

    def lazywrapped(func: Callable[..., ReturnT]) -> Callable[..., ReturnT]:
        """
        Wrapper Function
        """
        if is_coro_func(func):
            @functools.wraps(func)
            async def _wrapper(*args, **kwargs) -> ReturnT:
                """
                Wrapped Function
                """
                nonlocal _initialized_function, _initialized
                if not _initialized:
                    _initialized_function = await ThreadPooler.asyncish(function, *function_args, **function_kwargs)
                    _initialized = True
                if _initialized_function is None:
                    return await func(*args, **kwargs)
                return await _initialized_function(func)(*args, **kwargs)
            return _wrapper
        

        @functools.wraps(func)
        def _wrapper(*args, **kwargs) -> ReturnT:
            """
            Wrapped Function
            """
            nonlocal _initialized_function, _initialized
            if not _initialized:
                _initialized_function = function(*function_args, **function_kwargs)
                _initialized = True

            if _initialized_function is None:
                # If the function is None, return the original function
                return func(*args, **kwargs)
            
            return _initialized_function(func)(*args, **kwargs)
        return _wrapper
    
    return lazywrapped

