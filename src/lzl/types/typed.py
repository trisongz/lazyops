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
Advanced Type Hinting Definitions.

Provides sophisticated type aliases, `TypeVar` instances, `ParamSpec`,
and `Protocol` definitions for precise static analysis, particularly for
callables and asynchronous generators. Many concepts are inspired by or
adapted from libraries like `temporalio`.
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
    """Protocol for an asynchronous callable that takes no parameters."""

    def __call__(self) -> Awaitable[ProtocolReturnType]:
        """Type signature for the callable."""
        ...


class CallableSyncNoParam(Protocol[ProtocolReturnType]):
    """Protocol for a synchronous callable that takes no parameters."""

    def __call__(self) -> ProtocolReturnType:
        """Type signature for the callable."""
        ...


class CallableAsyncSingleParam(Protocol[ProtocolParamType, ProtocolReturnType]):
    """Protocol for an asynchronous callable that takes a single parameter."""

    def __call__(self, __arg: ProtocolParamType) -> Awaitable[ProtocolReturnType]:
        """Type signature for the callable."""
        ...


class CallableSyncSingleParam(Protocol[ProtocolParamType, ProtocolReturnType]):
    """Protocol for a synchronous callable that takes a single parameter."""

    def __call__(self, __arg: ProtocolParamType) -> ProtocolReturnType:
        """Type signature for the callable."""
        ...


class MethodAsyncNoParam(Protocol[ProtocolSelfType, ProtocolReturnType]):
    """Protocol for an asynchronous method that takes no parameters (besides self)."""

    def __call__(__self, self: ProtocolSelfType) -> Awaitable[ProtocolReturnType]:
        """Type signature for the method."""
        ...


class MethodSyncNoParam(Protocol[ProtocolSelfType, ProtocolReturnType]):
    """Protocol for a synchronous method that takes no parameters (besides self)."""

    def __call__(__self, self: ProtocolSelfType) -> ProtocolReturnType:
        """Type signature for the method."""
        ...


class MethodAsyncSingleParam(
    Protocol[ProtocolSelfType, ProtocolParamType, ProtocolReturnType]
):
    """Protocol for an asynchronous method that takes a single parameter (besides self)."""

    def __call__(
        self, __self: ProtocolSelfType, __arg: ProtocolParamType, /
    ) -> Awaitable[ProtocolReturnType]:
        """Type signature for the method."""
        ...


class MethodSyncSingleParam(
    Protocol[ProtocolSelfType, ProtocolParamType, ProtocolReturnType]
):
    """Protocol for a synchronous method that takes a single parameter (besides self)."""

    def __call__(
        self, __self: ProtocolSelfType, __arg: ProtocolParamType, /
    ) -> ProtocolReturnType:
        """Type signature for the method."""
        ...


class MethodSyncOrAsyncNoParam(Protocol[ProtocolSelfType, ProtocolReturnType]):
    """Protocol for a method (sync or async) that takes no parameters (besides self)."""

    def __call__(
        self, __self: ProtocolSelfType
    ) -> Union[ProtocolReturnType, Awaitable[ProtocolReturnType]]:
        """Type signature for the method."""
        ...


class MethodSyncOrAsyncSingleParam(
    Protocol[ProtocolSelfType, ProtocolParamType, ProtocolReturnType]
):
    """Protocol for a method (sync or async) that takes a single parameter (besides self)."""

    def __call__(
        self, __self: ProtocolSelfType, __param: ProtocolParamType, /
    ) -> Union[ProtocolReturnType, Awaitable[ProtocolReturnType]]:
        """Type signature for the method."""
        ...


TSend = TypeVar('TSend', contravariant=True)
TYield = TypeVar('TYield', covariant=True)

class AsyncGenerator(ABC, AsyncIterator[TYield], Generic[TYield, TSend]):
    """Abstract base class representing an asynchronous generator-iterator.

    This defines the interface for objects returned by functions defined with
    `async def` that use `yield`. It follows the protocol for asynchronous
    generators as defined in PEP 525.

    The lifecycle involves starting with `__anext__` or `asend(None)`, optionally
    sending values with `asend`, throwing exceptions with `athrow`, and closing
    with `aclose`.

    Generic Parameters:
        TYield: The type of values yielded by the generator.
        TSend: The type of values that can be sent into the generator via `asend`.
    """

    def __aiter__(self) -> AsyncIterator[TYield]:
        """Returns the asynchronous iterator itself."""
        return self

    async def __anext__(self) -> TYield:
        """Starts or resumes the generator, returning the next yielded value.

        Equivalent to `asend(None)`.

        Returns:
            TYield: The next value yielded by the generator.

        Raises:
            StopAsyncIteration: If the generator finishes or is already closed.
            Exception: Any exception raised uncaught within the generator.
                (StopIteration and StopAsyncIteration are converted to RuntimeError
                as per PEP 479).
        """
        # Implementation Note: PEP 525 states __anext__ should behave like asend(None).
        return await self.asend(None)

    async def asend(
        self,
        value: Optional[TSend] # Changed name from 'input' for clarity
    ) -> TYield:
        """Resumes the generator execution, sending a value into it.

        The sent value becomes the result of the `yield` expression where the
        generator was paused.

        Args:
            value: The value to send into the generator. Must be None if this
                is the first call to start the generator.

        Returns:
            TYield: The next value yielded by the generator after processing
                the sent value.

        Raises:
            StopAsyncIteration: If the generator finishes or is already closed.
            TypeError: If a non-None value is sent to a newly started generator.
            Exception: Any exception raised uncaught within the generator.
        """
        raise NotImplementedError

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