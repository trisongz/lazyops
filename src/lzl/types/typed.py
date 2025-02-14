from abc import ABC
from typing import (
    TypeVar,
    Generic,
    AsyncIterator,
    Optional,
    Type,
    Awaitable,
    Any,
    Callable,
    Union,
)
try:
    from types import TracebackType
except ImportError:
    from typing_extensions import TracebackType

from typing_extensions import ParamSpec, Protocol


"""
Borrowed from temporalio
"""
    
AnyType = TypeVar("AnyType")
ClassType = TypeVar("ClassType", bound=Type)
SelfType = TypeVar("SelfType")
ParamType = TypeVar("ParamType")
ReturnType = TypeVar("ReturnType", covariant=True)
LocalReturnType = TypeVar("LocalReturnType", covariant=True)
CallableType = TypeVar("CallableType", bound=Callable[..., Any])
CallableAsyncType = TypeVar("CallableAsyncType", bound=Callable[..., Awaitable[Any]])
CallableSyncOrAsyncType = TypeVar(
    "CallableSyncOrAsyncType",
    bound=Callable[..., Union[Any, Awaitable[Any]]],
)
CallableSyncOrAsyncReturnNoneType = TypeVar(
    "CallableSyncOrAsyncReturnNoneType",
    bound=Callable[..., Union[None, Awaitable[None]]],
)
MultiParamSpec = ParamSpec("MultiParamSpec")


ProtocolParamType = TypeVar("ProtocolParamType", contravariant=True)
ProtocolReturnType = TypeVar("ProtocolReturnType", covariant=True)
ProtocolSelfType = TypeVar("ProtocolSelfType", contravariant=True)


class CallableAsyncNoParam(Protocol[ProtocolReturnType]):
    """Generic callable type."""

    def __call__(self) -> Awaitable[ProtocolReturnType]:
        """Generic callable type callback."""
        ...


class CallableSyncNoParam(Protocol[ProtocolReturnType]):
    """Generic callable type."""

    def __call__(self) -> ProtocolReturnType:
        """Generic callable type callback."""
        ...


class CallableAsyncSingleParam(Protocol[ProtocolParamType, ProtocolReturnType]):
    """Generic callable type."""

    def __call__(self, __arg: ProtocolParamType) -> Awaitable[ProtocolReturnType]:
        """Generic callable type callback."""
        ...


class CallableSyncSingleParam(Protocol[ProtocolParamType, ProtocolReturnType]):
    """Generic callable type."""

    def __call__(self, __arg: ProtocolParamType) -> ProtocolReturnType:
        """Generic callable type callback."""
        ...


class MethodAsyncNoParam(Protocol[ProtocolSelfType, ProtocolReturnType]):
    """Generic callable type."""

    def __call__(__self, self: ProtocolSelfType) -> Awaitable[ProtocolReturnType]:
        """Generic callable type callback."""
        ...


class MethodSyncNoParam(Protocol[ProtocolSelfType, ProtocolReturnType]):
    """Generic callable type."""

    def __call__(__self, self: ProtocolSelfType) -> ProtocolReturnType:
        """Generic callable type callback."""
        ...


class MethodAsyncSingleParam(
    Protocol[ProtocolSelfType, ProtocolParamType, ProtocolReturnType]
):
    """Generic callable type."""

    def __call__(
        self, __self: ProtocolSelfType, __arg: ProtocolParamType, /
    ) -> Awaitable[ProtocolReturnType]:
        """Generic callable type callback."""
        ...


class MethodSyncSingleParam(
    Protocol[ProtocolSelfType, ProtocolParamType, ProtocolReturnType]
):
    """Generic callable type."""

    def __call__(
        self, __self: ProtocolSelfType, __arg: ProtocolParamType, /
    ) -> ProtocolReturnType:
        """Generic callable type callback."""
        ...


class MethodSyncOrAsyncNoParam(Protocol[ProtocolSelfType, ProtocolReturnType]):
    """Generic callable type."""

    def __call__(
        self, __self: ProtocolSelfType
    ) -> Union[ProtocolReturnType, Awaitable[ProtocolReturnType]]:
        """Generic callable type callback."""
        ...


class MethodSyncOrAsyncSingleParam(
    Protocol[ProtocolSelfType, ProtocolParamType, ProtocolReturnType]
):
    """Generic callable type."""

    def __call__(
        self, __self: ProtocolSelfType, __param: ProtocolParamType, /
    ) -> Union[ProtocolReturnType, Awaitable[ProtocolReturnType]]:
        """Generic callable type callback."""
        ...


TSend = TypeVar('TSend', contravariant=True)
TYield = TypeVar('TYield', covariant=True)

class AsyncGenerator(ABC, AsyncIterator[TYield], Generic[TYield, TSend]):
    """
    Represents a one-shot "asynchronous generator-iterator" (as it is
    referred to in the docs). The concept referred to as an "asynchronous
    generator _function_" is the function defined with `async def` that has a
    return type of AsyncGenerator.
    
    In other words, `fn` here is an asynchronous generator function:
    
        async def fn() -> AsyncGenerator[...]:
            ...
    
    And `agen` here is an asynchronous generator-iterator:
    
        agen = fn()
    
    The lifetime of an AsyncGenerator is as follows:
    
    1. The asynchronous generator-iterator is started by awaiting __anext__()
    or asend(None). This begins executing the asynchronous generator
    function.
    
    2. Once started, you may (but are not required to):
        
        2a. Call asend() with a TSend value and await the result, to continue
        executing the asynchronous generator function.
        
        2b. Await athrow() to raise an exception inside the asynchronous
        generator function, which may respond by yielding a value.
    
    3. You may repeat step 2 as long as the awaitable returned does not raise
    an exception.
    
    4. At any point, you may await aclose() to raise GeneratorExit inside the
    asynchronous generator function, requesting that it exit. This has no
    effect if an awaitable from step 2 already raised an exception, or if the
    asynchronous generator function never began executing, so it is always
    safe to invoke.
    
    5. Once the asynchronous generator function has exited (gracefully or
    through an exception), or the generator has been closed (even if the
    function was never started), the asynchronous generator-iterator instance
    may not be restarted. However, a new one can be obtained by calling the
    function again:
    
        agen = fn()
    """

    def __aiter__(self) -> AsyncIterator[TYield]:
        return self
    
    async def __anext__(self) -> TYield:  # throws: StopAsyncIteration, ...
        """
        Returns an awaitable which, when run, starts to execute the
        asynchronous generator, or resumes it from the last executed yield
        expression.
        
        If the generator has already exited (gracefully or through an
        exception) or been closed previously, nothing happens, and the
        awaitable returned by __anext__() will raise a StopAsyncIteration
        exception.
        
        If resuming from a yield expression, the expression will evaluate to
        None inside the generator, because no value is being provided (use
        asend() if you want that).
        
        The generator will run until the next yield expression or it exits
        (e.g., through a return statement).
        
        If the generator yields a value, the awaitable returned by
        __anext__() will return that value, and the generator's execution
        will be re-suspended. (Under the hood, this is implemented as the
        generator raising StopIteration, but you don't need to care about
        that.)
        
        If the generator raises an exception, the awaitable returned by
        __anext__() will raise the same exception. (Note that if a generator
        attempts to _explicitly_ raise StopIteration or StopAsyncIteration in
        its implementation, it will instead be converted into a RuntimeError,
        per PEP 479.)
        
        If the generator exits gracefully, the awaitable returned by
        __anext__() will raise a StopAsyncIteration exception.
        """
        return await self.asend(None)

    async def asend(
        self,
        input: Optional[TSend]
    ) -> TYield:  # throws: StopAsyncIteration, ...
        """
        Returns an awaitable which, when run, starts to execute the
        asynchronous generator, or resumes it from the last executed yield
        expression.
        
        If asend() is being called to start the generator, it must be called
        with None as the argument, because there is no yield expression that
        could receive the value. (This is the only reason `input` is typed as
        Optional[TSend].)
        
        If the generator has already exited (gracefully or through an
        exception) or been closed previously, nothing happens, and the
        awaitable returned by asend() will raise a StopAsyncIteration
        exception.
        
        If resuming from a yield expression, the expression will evaluate to
        `input` inside the generator.
        
        The generator will run until the next yield expression or it exits
        (e.g., through a return statement).
        
        If the generator yields a value, the awaitable returned by asend()
        will return that value, and the generator's execution will be
        re-suspended. (Under the hood, this is implemented as the generator
        raising StopIteration, but you don't need to consider that.)
        
        If the generator raises an exception, the awaitable returned by
        asend() will raise the same exception. (Note that if a generator
        attempts to _explicitly_ raise StopIteration or StopAsyncIteration in
        its implementation, it will instead be converted into a RuntimeError,
        per PEP 479.)
        
        If the generator exits gracefully, the awaitable returned by asend()
        will raise a StopAsyncIteration exception.
        """
        ...

    async def athrow(
        self,
        exc_type: Type[BaseException],
        exc_value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> Optional[TYield]:  # throws: exc_type, StopAsyncIteration, ...
        """
        Returns an awaitable which, when run, raises an exception _inside_
        the generator at the point of execution where it was last suspended.
        
        If the generator has not yet been started, the awaitable returned by
        athrow() will immediately raise the passed-in exception, and the
        generator will be closed. In other words, the generator is not given
        any opportunity to catch the exception, and it will not be able to be
        started afterward.
        
        If the generator has already exited (gracefully or through an
        exception) or been closed previously, nothing happens, and the
        awaitable returned by athrow() will return None.
        
        Otherwise, after raising the exception inside the generator, athrow()
        behaves exactly like __anext__().
        
        In other words:
        
        If the generator does not catch the passed-in exception, or raises a
        different exception, then the awaitable returned by athrow() will
        propagate that exception. (Note that if a generator attempts to
        _explicitly_ raise StopIteration or StopAsyncIteration in its
        implementation, it will instead be converted into a RuntimeError, per
        PEP 479.)
        
        If the generator catches the passed-in exception, then yields a
        value, the awaitable returned by athrow() will return that value, and
        the generator's execution will be re-suspended. (Under the hood, this
        is implemented as the generator raising StopIteration, but you don't
        need to consider that.)
        
        If the generator catches the passed-in exception, then exits
        gracefully, the awaitable returned by athrow() will raise a
        StopAsyncIteration exception.
        """
        ...
    
    async def aclose(
        self
    ) -> None:  # throws RuntimeError, ...
        """
        Returns an awaitable which, when run, raises a GeneratorExit
        exception _inside_ the generator at the point of execution where it
        was last suspended.
        
        If the generator has already exited (gracefully or through an
        exception) or been closed previously, or the generator was never
        started, nothing happens, and the awaitable returned by aclose() will
        return gracefully.
        
        If the generator does not catch the GeneratorExit exception, or
        catches GeneratorExit then exits gracefully, the awaitable returned
        by aclose() will return gracefully.
        
        If the generator raises a different exception, then the awaitable
        returned by aclose() will propagate that exception.
        
        The generator _must not_ yield a value. If the generator catches the
        GeneratorExit exception then yields a value, the awaitable returned
        by aclose() will raise a RuntimeError.
        """

        try:
            await self.athrow(GeneratorExit)
        except (GeneratorExit, StopAsyncIteration):
            pass
        else:
            raise RuntimeError("...")