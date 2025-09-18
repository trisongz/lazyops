from __future__ import annotations

"""Minimal asynchronous background queue primitives."""


import abc
import time
import asyncio
import functools
import typing as t
import dataclasses
from lzl.types import eproperty
from lzl.logging import logger
from lzo.utils import Timer

@dataclasses.dataclass
class Stats:
    """Aggregate counts for background task execution results."""
    successful: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        """Return the total number of processed items."""
        return self.successful + self.failed

class BackgroundTaskQueue(abc.ABC):
    """Abstract base class for cooperative background task queues."""

    _extra: t.Dict[str, t.Any] = {}

    def __init__(
        self,
        name: str,
        num_workers: int = 1,
        interval: float = 0.1,
        min_items: t.Optional[int] = None,
        max_items: int = 100,
        **kwargs: t.Any,
    ):
        """Initialise a background queue without starting any workers.

        Args:
            name: Human readable identifier used in log messages.
            num_workers: Number of concurrent worker tasks to spawn.
            interval: Delay (in seconds) between queue polling iterations.
            min_items: Optional lower bound before dispatching batched work.
            max_items: Hard cap on the number of items processed per cycle.
            **kwargs: Additional keyword arguments reserved for subclasses.
        """
        self.name = name
        self.num_workers = num_workers
        self.interval = interval
        self.min_items = min_items
        self.max_items = max_items

        self.stats = Stats()
        
        self._loop: t.Optional[asyncio.AbstractEventLoop] = None
        self.tasks: t.Optional[t.Set[asyncio.Task]] = set()
        self.main_task: t.Optional[asyncio.Task] = None


    @property
    def started(self) -> bool:
        """Return ``True`` when the main worker task has been created."""
        return self.main_task is not None

    @eproperty
    def lock(self) -> asyncio.Lock:
        """Create and memoise an asyncio lock guarding queue operations."""
        return asyncio.Lock()

    @eproperty
    def task_queue(self) -> asyncio.Queue:
        """Create the backing asyncio queue on first access."""
        return asyncio.Queue()
    

    def start_task_queue(self, num_workers: t.Optional[int] = None) -> None:
        """Spawn the background worker task if it is not already running."""

        if self.started:
            return
        num_workers = num_workers or self.num_workers
        logger.info(f'Starting {self.name} Queue with |g|{num_workers}|e| Workers', colored = True)
        self.started_time = Timer()
        self.event_queue = EventQueue()  # type: ignore[name-defined]
        self.main_task = asyncio.create_task(self.run_task_queue(num_workers = num_workers))
        
