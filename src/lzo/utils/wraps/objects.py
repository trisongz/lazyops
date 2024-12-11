from __future__ import annotations

"""
Class Object Wrappers
"""
import copy
import inspect
import functools
import contextlib
import typing as t
try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

SelfT = t.TypeVar("SelfT")
ParamT = ParamSpec("ParamT")
ReturnType = t.TypeVar("ReturnType", covariant=True)
# https://stackoverflow.com/questions/77540153/type-hinting-decorator-which-injects-the-value-but-also-supports-passing-the-va?noredirect=1&lq=1

_is_async_default: t.Optional[bool] = None
_curr_async_default: t.Optional[bool] = None

def set_default_is_async(
    default: t.Optional[bool] = None,
):
    """
    Sets the default value for the `is_async` kwarg
    """
    global _is_async_default
    _is_async_default = default

@contextlib.contextmanager
def syncoro_ctx(
    is_async: t.Optional[bool] = None,
):
    """
    Context Manager that allows setting the `is_async` kwarg
    """
    global _curr_async_default
    old_is_async = _curr_async_default
    if is_async is not None: _curr_async_default = is_async
    yield
    _curr_async_default = old_is_async

def get_default_is_async(
    _is_async: t.Optional[bool] = None,
    _default: t.Optional[bool] = None,
) -> bool:
    """
    Returns the default value for the `is_async` kwarg
    """
    if _curr_async_default is not None: return _curr_async_default
    if _is_async is not None: return _is_async
    return _default if _default is not None else _is_async_default

def syncoro_cls(
    fn: t.Callable[ParamT, ReturnType],
    async_fn: t.Callable[ParamT, t.Awaitable[ReturnType]],
    _default: t.Optional[bool] = None,
):
    """
    Creates a classmethod Wrapper that allows for both sync and async calls
    based on the presence of the `is_async` kwarg
    """
    
    fn = fn.__func__ if isinstance(fn, classmethod) else fn
    async_fn = async_fn.__func__ if isinstance(async_fn, classmethod) else async_fn
    def inner(func: t.Callable[ParamT, ReturnType]) -> t.Callable[ParamT, ReturnType | t.Awaitable[ReturnType]]:
        """
        Inner Wrapper
        """
        # _default = _is_async_default if _default is None else _default

        @functools.wraps(func)
        def wrapper(cls, *args: ParamT.args, is_async: t.Optional[bool] = None, **kwargs: ParamT.kwargs) -> ReturnType | t.Awaitable[ReturnType]:
            is_async = get_default_is_async(is_async, _default)
            # if is_async is None: is_async = _default if _default is not None else _is_async_default
            return async_fn(cls, *args, **kwargs) if is_async else fn(cls, *args, **kwargs)
        return classmethod(wrapper)
    return inner


class Syncoro(t.Protocol):
    def __call__(self, *args: ParamT.args, is_async: t.Optional[bool] = None, **kwargs: ParamT.kwargs) -> ReturnType | t.Awaitable[ReturnType]:
        ...
        
def syncoro(
    fn: t.Callable[ParamT, ReturnType],
    async_fn: t.Callable[ParamT, t.Awaitable[ReturnType]],
    _default: t.Optional[bool] = None,
    _is_classmethod: t.Optional[bool] = None,
# ) -> t.Callable[[t.Callable[..., ReturnType]], t.Callable[ParamT, ReturnType]]:
):
    """
    Creates a Wrapper that allows for both sync and async calls
    based on the presence of the `is_async` kwarg
    """
    if _is_classmethod: return syncoro_cls(fn, async_fn, _default)
    
    def inner(func: t.Callable[ParamT, ReturnType]) -> t.Callable[ParamT, ReturnType | t.Awaitable[ReturnType]]:
    # def inner(func: t.Callable[ParamT, ReturnType]) -> t.Callable[t.Concatenate[ParamT, (bool | None, "is_async")], ReturnType | t.Awaitable[ReturnType]]:
    # def inner(func: t.Callable[ParamT, ReturnType]):
        """
        Inner Wrapper
        """

        @functools.wraps(func)
        def wrapper(*args: ParamT.args, is_async: t.Optional[bool] = None, **kwargs: ParamT.kwargs) -> ReturnType | t.Awaitable[ReturnType]:
            is_async = get_default_is_async(is_async, _default)
            # if is_async is None: is_async = _default if _default is not None else _is_async_default
            return async_fn(*args, **kwargs) if is_async else fn(*args, **kwargs)
        
        # is_async_param = inspect.Parameter('is_async', inspect.Parameter.KEYWORD_ONLY, default = _default, annotation = t.Optional[bool])
        # sig = inspect.signature(func)
        # params = list(sig.parameters.values())
        # params.append(is_async_param)
        
        # # params.insert(len(params) - 1, is_async_param)
        # # wrapper: Syncoro
        # wrapper.__signature__ = sig.replace(parameters = params)
        # wrapper.__annotations__ = copy.deepcopy(func.__annotations__)
        # rt = wrapper.__annotations__.pop('return')
        # wrapper.__annotations__['is_async'] = bool
        # wrapper.__annotations__['return'] = rt
        return wrapper
    return inner
