from __future__ import annotations

"""
A Background Task Queue
"""


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
    """
    The Task Queue Stats
    """
    successful: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        """
        Returns the total
        """
        return self.successful + self.failed

class BackgroundTaskQueue(abc.ABC):
    """
    The Background Task Queue
    """

    _extra: t.Dict[str, t.Any] = {}

    def __init__(
        self,
        name: str,
        num_workers: int = 1,
        interval: float = 0.1,
        min_items: t.Optional[int] = None,
        max_items: int = 100,
        **kwargs
    ):
        """
        A Background Task Queue

        - `name`: The name of the queue
        - `num_workers`: The number of workers to use for the queue
        - `interval`: The interval to check for tasks and send them
        - `min_items`: The minimum number of items to process before sending
        - `max_items`: The maximum number of items to process before sending
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
        """
        Returns True if the client is started
        """
        return self.main_task is not None

    @eproperty
    def lock(self) -> asyncio.Lock:
        """
        Returns the Lock
        """
        return asyncio.Lock()

    @eproperty
    def task_queue(self) -> asyncio.Queue:
        """
        Returns the Task Queue
        """
        return asyncio.Queue()
    

    def start_task_queue(self, num_workers: t.Optional[int] = None):
        """
        Starts the Task Queue
        """
        if self.started: return
        num_workers = num_workers or self.num_workers
        logger.info(f'Starting {self.name} Queue with |g|{num_workers}|e| Workers', colored = True)
        self.started_time = Timer()
        self.event_queue = EventQueue()
        self.main_task = asyncio.create_task(self.run_task_queue(num_workers = num_workers))
        