from __future__ import annotations

"""
Some Temporal Patches
"""

import typing as t
from lzl.pool import ThreadPool
from temporalio import client

if t.TYPE_CHECKING:
    from temporalio.client import WorkflowHandle as _WorkflowHandle
    from temporalio.types import SelfType, ReturnType

    class WorkflowHandle(_WorkflowHandle[SelfType, ReturnType]):
        _validator: t.Optional[t.Callable[[t.Any], t.Any]] = None
        def set_validator(self, validator: t.Callable[[t.Any], t.Any]) -> None:
            """
            Sets the validator
            """
            ...
        
        async def until_complete(self) -> ReturnType: 
            """
            Waits until the workflow is complete
            """
            ...


def set_validator(self: '_WorkflowHandle[t.Any, t.Any]', validator: t.Callable[[t.Any], t.Any]) -> None:
    """
    Sets the validator
    """
    self._validator = validator

async def until_complete(self: '_WorkflowHandle[t.Any, t.Any]') -> None:
    """
    Waits until the workflow is complete
    """
    result = await self.result()
    if hasattr(self, '_validator'):
        if ThreadPool.is_coro(self._validator):
            return await self._validator(result)
        return self._validator(result)
    return result


client.WorkflowHandle.until_complete = until_complete
client.WorkflowHandle.set_validator = set_validator