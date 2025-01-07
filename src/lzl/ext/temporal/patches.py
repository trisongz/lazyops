from __future__ import annotations

"""
Some Temporal Patches
"""
import inspect
import functools
import typing as t
import contextlib
from lzl.pool import ThreadPool
from temporalio import client

if t.TYPE_CHECKING:
    from temporalio.client import WorkflowHandle as _WorkflowHandle, WorkflowExecutionDescription
    from temporalio.types import SelfType, ReturnType

    class WorkflowHandle(_WorkflowHandle[SelfType, ReturnType]):
        
        _validator: t.Optional[t.Callable[[t.Any], t.Any]] = None
        _callback: t.Optional[t.Callable[[t.Any], t.Any]] = None

        def set_validator(self, validator: t.Callable[[t.Any], t.Any]) -> None:
            """
            Sets the validator
            """
            ...

        def set_callback(self, callback: t.Callable[[t.Any], t.Any], *args, **kwargs) -> None:
            """
            Sets the callback
            """
            ...
        
        async def until_complete(self) -> ReturnType: 
            """
            Waits until the workflow is complete
            """
            ...

        @property
        def status(self) -> t.Optional[WorkflowExecutionDescription]:
            """
            Returns the status of the workflow
            """
            ...
        
        @property
        def exists(self) -> bool:
            """
            Checks if the workflow exists
            """
            ...
        
        @property
        def is_terminated(self) -> bool:
            """
            Checks if the workflow is terminated
            """
            ...

        @property
        def is_completed(self) -> bool:
            """
            Checks if the workflow is completed
            """
            ...

        @property
        def is_terminal(self) -> bool:
            """
            Checks if the workflow is terminal
            """
            ...

        async def refresh(self, force: t.Optional[bool] = None) -> None:
            """
            Refreshes the workflow
            """
            ...



def set_validator(self: 'WorkflowHandle[t.Any, t.Any]', validator: t.Callable[[t.Any], t.Any]) -> None:
    """
    Sets the validator
    """
    self._validator = validator

def set_callback(self: 'WorkflowHandle[t.Any, t.Any]', callback: t.Callable[[t.Any], t.Any], *args, **kwargs) -> None:
    """
    Sets the callback
    """
    if args or kwargs: callback = functools.partial(callback, *args, **kwargs)
    self._callback = callback

async def until_complete(self: 'WorkflowHandle[t.Any, t.Any]') -> None:
    """
    Waits until the workflow is complete
    """
    result = await self.result()
    if hasattr(self, '_validator'):
        if ThreadPool.is_coro(self._validator):
            result = await self._validator(result)
        else:
            result = self._validator(result)
        if inspect.isawaitable(result):
            result = await result
    if hasattr(self, '_callback'):
        if ThreadPool.is_coro(self._callback):
            cb = await self._callback(result)
        else:
            cb = self._callback(result)
        if inspect.isawaitable(cb):
            await cb
    return result

async def refresh(self: 'WorkflowHandle[t.Any, t.Any]', force: t.Optional[bool] = None) -> None:
    """
    Refreshes the workflow
    """
    if hasattr(self, 'is_terminated') and not force: return
    self.status = None
    self.exists = False
    self.is_terminated = False
    self.is_completed = False
    self.is_terminal = False
    with contextlib.suppress(Exception):
        self.status = await self.describe()
        self.exists = True
        self.is_terminated = self.status.status in {
            client.WorkflowExecutionStatus.TERMINATED,
            client.WorkflowExecutionStatus.FAILED,
            client.WorkflowExecutionStatus.CANCELED,
            client.WorkflowExecutionStatus.TIMED_OUT,
            # 'TERMINATED', 'FAILED', 'CANCELLED', 'TIMED_OUT'
        }
        self.is_completed = self.status.status in {
            client.WorkflowExecutionStatus.COMPLETED,
        }
        self.is_terminal = self.is_terminated or self.is_completed


client.WorkflowHandle.until_complete = until_complete
client.WorkflowHandle.set_validator = set_validator
client.WorkflowHandle.set_callback = set_callback
client.WorkflowHandle.refresh = refresh