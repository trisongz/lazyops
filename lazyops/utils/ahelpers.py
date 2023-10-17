"""
Async Helpers
"""
import sys
import asyncio
import functools

from typing import Optional, Any, Callable, Awaitable, Union, TypeVar, Coroutine, Iterable, AsyncIterable, AsyncIterator, AsyncGenerator
from lazyops.utils.system import get_cpu_count
from lazyops.utils.pooler import ThreadPooler
from lazyops.types.common import UpperStrEnum

if sys.version_info < (3, 10):
    # Add aiter and anext to asyncio
    def aiter(it: AsyncIterable) -> Any:
        return it.__aiter__()
    
    def anext(it: AsyncIterator) -> Any:
        return it.__anext__()
    

_concurrency_limit: Optional[int] = None
RT = TypeVar("RT")

def set_concurrency_limit(
    limit: Optional[int] = None
):
    """
    Set the concurrency limit
    """
    global _concurrency_limit
    if limit is None: limit = get_cpu_count() * 4
    _concurrency_limit = limit
    # asyncio.set_event_loop_policy(asyncio.BoundedSemaphore(limit))

def get_concurrency_limit() -> Optional[int]:
    """
    Get the concurrency limit
    """
    if _concurrency_limit is None: set_concurrency_limit()
    return _concurrency_limit

# ref
# https://death.andgravity.com/limit-concurrency

class ReturnWhenType(UpperStrEnum):
    """
    Return When Type
    """
    FIRST_COMPLETED = "FIRST_COMPLETED"
    FIRST_EXCEPTION = "FIRST_EXCEPTION"
    ALL_COMPLETED = "ALL_COMPLETED"

    @property
    def val(self) -> Union[asyncio.FIRST_COMPLETED, asyncio.FIRST_EXCEPTION, asyncio.ALL_COMPLETED]:
        """
        Get the value of the return when type
        """
        return getattr(asyncio, self.value)

async def limit_concurrency(
    mapped_iterable: Union[Callable[[], Awaitable[Any]], Awaitable[Any], Coroutine[Any, Any, Any], Callable[[], Any]],
    limit: Optional[int] = None,
    return_when: Optional[ReturnWhenType] = ReturnWhenType.FIRST_COMPLETED,
):
    """
    Limit the concurrency of an iterable

    Args:
        mapped_iterable (Union[Callable[[], Awaitable[Any]], Awaitable[Any], Coroutine[Any, Any, Any], Callable[[], Any]]): The iterable to limit the concurrency of
        limit (Optional[int], optional): The limit of the concurrency. Defaults to None.
        return_when (Optional[ReturnWhenType], optional): The return when type. Defaults to ReturnWhenType.FIRST_COMPLETED.
    
    Yields:
        [type]: [description]
    """
    try:
        iterable = aiter(mapped_iterable)
        is_async = True
    except (TypeError, AttributeError):
        iterable = iter(mapped_iterable)
        is_async = False
    
    iterable_ended: bool = False
    pending = set()
    limit = get_concurrency_limit() if limit is None else limit
    return_when = ReturnWhenType(return_when) if isinstance(return_when, str) else return_when

    while pending or not iterable_ended:
        while len(pending) < limit and not iterable_ended:
            try:
                iter_item = await anext(iterable) if is_async else next(iterable)
            except StopAsyncIteration if is_async else StopIteration:
                iterable_ended = True
            else:
                pending.add(asyncio.ensure_future(iter_item))

        if not pending: return
        done, pending = await asyncio.wait(
            pending, 
            return_when = return_when.val
        )
        while done: yield done.pop()

def ensure_coro(
    func: Callable[..., Any]
) -> Callable[..., Awaitable[Any]]:
    """
    Ensure that the function is a coroutine
    """
    if asyncio.iscoroutinefunction(func): return func
    @functools.wraps(func)
    async def inner(*args, **kwargs):
        return await ThreadPooler.asyncish(func, *args, **kwargs)
    return inner


async def amap(
    func: Callable[..., Awaitable[Any]],
    iterable: Iterable[Any], 
    *, 
    limit: Optional[int] = None,
    return_when: Optional[ReturnWhenType] = ReturnWhenType.FIRST_COMPLETED,
):
    """
    Async Map

    Args:
        func (Callable[..., Awaitable[Any]]): The function to map
        iterable (Iterable[Any]): The iterable to map
        limit (Optional[int], optional): The limit of the concurrency. Defaults to None.
        return_when (Optional[ReturnWhenType], optional): The return when type. Defaults to ReturnWhenType.FIRST_COMPLETED.
    
    Yields:
        [type]: [description]
    """
    func = ensure_coro(func)
    try:
        mapped_iterable = map(func, iterable)
    except TypeError:
        mapped_iterable = (func(x) async for x in iterable)
    async for task in limit_concurrency(mapped_iterable, limit = limit, return_when = return_when):
        yield await task

async def amap_unordered(
    func: Callable[..., Awaitable[Any]],
    iterable: Iterable[Any], 
    *, 
    limit: Optional[int] = None,
    return_when: Optional[ReturnWhenType] = ReturnWhenType.FIRST_COMPLETED,
):
    """
    Async Map Unordered

    Args:
        func (Callable[..., Awaitable[Any]]): The function to map
        iterable (Iterable[Any]): The iterable to map
        limit (Optional[int], optional): The limit of the concurrency. Defaults to None.
        return_when (Optional[ReturnWhenType], optional): The return when type. Defaults to ReturnWhenType.FIRST_COMPLETED.
    
    Yields:
        [type]: [description]
    """
    async for result in amap(func, iterable, limit = limit, return_when = return_when):
        yield result


async def amap_ordered(
    func: Callable[..., Awaitable[Any]],
    iterable: Iterable[Any], 
    *, 
    limit: Optional[int] = None,
    return_when: Optional[ReturnWhenType] = ReturnWhenType.ALL_COMPLETED,
):
    """
    Async Map Ordered

    Args:
        func (Callable[..., Awaitable[Any]]): The function to map
        iterable (Iterable[Any]): The iterable to map
        limit (Optional[int], optional): The limit of the concurrency. Defaults to None.
        return_when (Optional[ReturnWhenType], optional): The return when type. Defaults to ReturnWhenType.FIRST_COMPLETED.
    
    Yields:
        [type]: [description]
    """
    async for result in amap(func, iterable, limit = limit, return_when = return_when):
        yield result


async def amap_v2(
    func: Callable[..., Awaitable[Any]],
    iterable: Iterable[Any], 
    *args,
    limit: Optional[int] = None,
    return_when: Optional[ReturnWhenType] = ReturnWhenType.FIRST_COMPLETED,
    **kwargs,
):
    """
    Async Map

    Args:
        func (Callable[..., Awaitable[Any]]): The function to map
        iterable (Iterable[Any]): The iterable to map
        limit (Optional[int], optional): The limit of the concurrency. Defaults to None.
        return_when (Optional[ReturnWhenType], optional): The return when type. Defaults to ReturnWhenType.FIRST_COMPLETED.
    
    Yields:
        [type]: [description]
    """
    func = ensure_coro(func)
    # Deal with Tuples and Lists in the iterable
    # if isinstance(iterable, (tuple, list)):
    #     iterable = [func(x, *args, **kwargs) for x in iterable]
    # else:
    #     iterable = (func(x, *args, **kwargs) for x in iterable)
    partial = functools.partial(func, *args, **kwargs)
    try:
        mapped_iterable = map(partial, iterable)
    except TypeError:
        mapped_iterable = (partial(x) async for x in iterable)
    async for task in limit_concurrency(mapped_iterable, limit = limit, return_when = return_when):
        yield await task


async def async_map(
    func: Callable[..., Awaitable[Any]],
    iterable: Iterable[Any], 
    *args,
    limit: Optional[int] = None,
    return_when: Optional[ReturnWhenType] = ReturnWhenType.FIRST_COMPLETED,
    **kwargs,
) -> AsyncGenerator[RT, None]:
    """
    Async Map of a function with args and kwargs

    Args:
        func (Callable[..., Awaitable[Any]]): The function to map
        iterable (Iterable[Any]): The iterable to map
        limit (Optional[int], optional): The limit of the concurrency. Defaults to None.
        return_when (Optional[ReturnWhenType], optional): The return when type. Defaults to ReturnWhenType.FIRST_COMPLETED.
    
    Yields:
        [type]: [description]
    """
    func = ensure_coro(func)
    partial = functools.partial(func, *args, **kwargs)
    try:
        mapped_iterable = map(partial, iterable)
    except TypeError:
        mapped_iterable = (partial(x) async for x in iterable)
    async for task in limit_concurrency(mapped_iterable, limit = limit, return_when = return_when):
        yield await task