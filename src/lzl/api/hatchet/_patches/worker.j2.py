from __future__ import annotations

"""
Base Hatchet Client with Modifications

Patched: {{ timestamp }}
Version: {{ version }}
Last Version: {{ last_version }}
"""

import os
import signal
import asyncio
import functools
import contextvars
import grpc
from threading import Thread
from concurrent.futures import Future, ThreadPoolExecutor
from hatchet_sdk.loader import ClientConfig
from hatchet_sdk.worker import (
    Worker as BaseWorker, 
    WorkerStatus, 
    errorWithTraceback, 
    copy_context_vars,
    wr, sr,
    new_dispatcher, 
    new_admin,
    new_listener,
    PooledWorkflowRunListener,
    GetActionListenerRequest,
    WorkerContext
)
from hatchet_sdk.client import new_client_raw
from threading import Thread, current_thread
from hatchet_sdk.clients.dispatcher import Action, ActionListenerImpl
from hatchet_sdk.dispatcher_pb2 import (
    GROUP_KEY_EVENT_TYPE_COMPLETED,
    GROUP_KEY_EVENT_TYPE_FAILED,
    GROUP_KEY_EVENT_TYPE_STARTED,
    STEP_EVENT_TYPE_COMPLETED,
    STEP_EVENT_TYPE_FAILED,
    STEP_EVENT_TYPE_STARTED,
    ActionType,
    GroupKeyActionEvent,
    GroupKeyActionEventType,
    StepActionEvent,
    StepActionEventType,
    WorkerUnsubscribeRequest,
)
from hatchet_sdk.logger import logger
from hatchet_sdk.metadata import get_metadata
from typing import Any, Dict, Callable, Type, Optional, TYPE_CHECKING
from .context import Context, ContextT
from .utils import new_session, json_serializer
from lzo.utils.logs import logger as _logger

if TYPE_CHECKING:
    from .session import HatchetSession

class Worker(BaseWorker):
    """
    The Worker Object
    """
    SIGNALS = [signal.SIGINT, signal.SIGTERM] if os.name != "nt" else [signal.SIGTERM]

    
{% for name, func in new_funcs.items() %}
{{ func | replace("json.dumps", "json_serializer.dumps") }}
{% endfor %}

    # @property
    # def loop(self) -> asyncio.AbstractEventLoop:
    #     """
    #     Returns the event loop
    #     """
    #     if not self._loop: 
    #         try:
    #             self._loop = asyncio.get_running_loop()
    #         except RuntimeError as e:
    #             logger.error(f"Error getting running loop: {e}")
    #             try:
    #                 self._loop = asyncio.get_event_loop()
    #             except RuntimeError as e:
    #                 logger.error(f"Error getting event loop: {e}")
    #                 self._loop = asyncio.new_event_loop()
    #                 asyncio.set_event_loop(self._loop)
    #     return self._loop
    
    # @loop.setter
    # def loop(self, value: asyncio.AbstractEventLoop):
    #     """
    #     Sets the loop
    #     """
    #     self._loop = value

    # def run(self):
    #     """
    #     Run function
    #     """
    #     self.main_task = self.loop.create_task(self.async_run)
    #     try:
    #         self.loop.run_until_complete(self.main_task)
    #     except asyncio.CancelledError:  # pragma: no cover
    #         # happens on shutdown, fine
    #         pass
    #     finally:
    #         self.loop.run_until_complete(self.exit_gracefully)

    async def watch_for_termination(self):
        """
        Watches for termination
        """
        self.event = asyncio.Event()
        
        try:
            for signum in self.SIGNALS: self.loop.add_signal_handler(signum, self.event.set)
            await self.event.wait()
        # except asyncio.CancelledError:  # pragma: no cover
            # happens on shutdown, fine
            # self.event.set()
        except Exception as e:
            _logger.trace('Error in Watching', e)
            # self.event.set()
        finally:
            self.event.set()
            logger.warning(f'Exiting!')
            self.loop.run_until_complete(self.exit_gracefully)

    def run_watcher_event(self):
        """
        Starts the watcher event
        """
        asyncio.create_task(self.watch_for_termination())
    
    async def async_run(self, **kwargs):
        """
        Async Function to run the worker
        """
        self.event = asyncio.Event()
        for signum in self.SIGNALS: self.loop.add_signal_handler(signum, self.event.set)
        task = None
        try:
            task = self.loop.create_task(self.async_start)
            await self.event.wait()
        except Exception as e:
            logger.error(f'Shutdown: {e}')
            raise e
        finally:
            self.event.set()
            if task is not None:
                if not task.done(): task.cancel()
            if self.main_task: self.main_task.cancel()
            await asyncio.wait_for(asyncio.gather(task), timeout = 5.0)





