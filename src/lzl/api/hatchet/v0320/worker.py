from __future__ import annotations

"""
Base Hatchet Client with Modifications

Patched: 2024-08-08 19:02:25
Version: 0.32.0
Last Version: 0.31.0
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
from ..utils import new_session, json_serializer
from lzo.utils.logs import logger as _logger

if TYPE_CHECKING:
    from ..session import HatchetSession

class Worker(BaseWorker):
    """
    The Worker Object
    """
    SIGNALS = [signal.SIGINT, signal.SIGTERM] if os.name != "nt" else [signal.SIGTERM]

    

    def __init__(
        self,
        name: str,
        max_runs: int | None = None,
        debug=False,
        handle_kill=True,
        config: ClientConfig = {},
        labels: dict[str, str | int] = {},
        session: Optional['HatchetSession'] = None,
        context_class: Type[Context] = Context,

    ):
        if debug:
            logger.warn(
                "debug on worker is deprecated and will be removed in a future release, please set debug on the Hatchet client instead"
            )

        # We store the config so we can dynamically create clients for the dispatcher client.
        self.config = config
        self.session = session
        self.client = self.session.client if self.session else new_session(config)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._context_cls = context_class
        self.main_task = None

        self.name = self.client.config.namespace + name
        self.max_runs = max_runs
        self.tasks: Dict[str, asyncio.Task] = {}  # Store run ids and futures
        self.contexts: Dict[str, Context] = {}  # Store run ids and contexts
        self.action_registry: dict[str, Callable[..., Any]] = {}
        self.listener: ActionListenerImpl = None

        # The thread pool is used for synchronous functions which need to run concurrently
        self.thread_pool = ThreadPoolExecutor(max_workers=max_runs)
        self.threads: Dict[str, Thread] = {}  # Store run ids and threads

        self.killing = False
        self.handle_kill = handle_kill

        self._status = WorkerStatus.INITIALIZED

        self.worker_context = WorkerContext(labels=labels, config=config)


    async def handle_start_step_run(self, action: Action):
        logger.debug(f"Starting step run {action.step_run_id}")

        action_name = action.action_id
        context = self._context_cls(
            action,
            self.dispatcher_client,
            self.admin_client,
            self.client.event,
            self.client.workflow_listener,
            self.workflow_run_event_listener,
            self.worker_context,
            self.client.config.namespace,
        )
        self.contexts[action.step_run_id] = context

        # Find the corresponding action function from the registry
        action_func = self.action_registry.get(action_name)

        if action_func:
            # send an event that the step run has started
            try:
                event = self.get_step_action_event(action, STEP_EVENT_TYPE_STARTED)

                # Send the action event to the dispatcher
                asyncio.create_task(
                    self.dispatcher_client.send_step_action_event(event)
                )
            except Exception as e:
                logger.error(f"Could not send action event: {e}")

            task = self.loop.create_task(
                self.async_wrapped_action_func(
                    context, action_func, action, action.step_run_id
                )
            )

            task.add_done_callback(self.step_run_callback(action))
            self.tasks[action.step_run_id] = task

            try:
                await task
            except Exception as e:
                # do nothing, this should be caught in the callback
                pass

        logger.debug(f"Finished step run {action.step_run_id}")


    async def handle_start_group_key_run(self, action: Action):
        action_name = action.action_id
        context = self._context_cls(
            action,
            self.dispatcher_client,
            self.admin_client,
            self.client.event,
            self.client.workflow_listener,
            self.workflow_run_event_listener,
            self.worker_context,
            self.client.config.namespace,
        )
        self.contexts[action.get_group_key_run_id] = context

        # Find the corresponding action function from the registry
        action_func = self.action_registry.get(action_name)

        if action_func:
            # send an event that the group key run has started
            try:
                event = self.get_group_key_action_event(
                    action, GROUP_KEY_EVENT_TYPE_STARTED
                )

                # Send the action event to the dispatcher
                asyncio.create_task(
                    self.dispatcher_client.send_group_key_action_event(event)
                )
            except Exception as e:
                if "]:" in str(e) and "- 40" in str(e):
                    logger.error(f"[{action.step_run_id} - {action.job_name}] Error in action: {e}")
                    raise e
                logger.error(f"Could not send action event: {e}")

            task = self.loop.create_task(
                self.async_wrapped_action_func(
                    context, action_func, action, action.get_group_key_run_id
                )
            )

            task.add_done_callback(self.group_key_run_callback(action))
            self.tasks[action.get_group_key_run_id] = task

            try:
                await task
            except Exception as e:
                # do nothing, this should be caught in the callback
                pass


    async def async_wrapped_action_func(
        self, context: Context, action_func, action: Action, run_id: str
    ):
        wr.set(context.workflow_run_id())
        sr.set(context.step_run_id)

        try:
            if action_func._is_coroutine:
                return await action_func(context)
            else:
                pfunc = functools.partial(
                    # we must copy the context vars to the new thread, as only asyncio natively supports
                    # contextvars
                    copy_context_vars,
                    contextvars.copy_context().items(),
                    self.thread_action_func,
                    context,
                    action_func,
                    action,
                )
                res = await self.loop.run_in_executor(self.thread_pool, pfunc)

                return res
        except Exception as e:
            if "]:" in str(e) and "- 40" in str(e):
                logger.error(f"[{action.step_run_id} - {action.job_name}] Error in action: {e}")
                raise e
            logger.error(errorWithTraceback(f"Could not execute action: {e}", e))
            raise e
        finally:
            self.cleanup_run_id(run_id)


    def get_step_action_finished_event(
        self, action: Action, output: Any
    ) -> StepActionEvent:
        try:
            event = self.get_step_action_event(action, STEP_EVENT_TYPE_COMPLETED)
        except Exception as e:
            logger.error(f"Could not create action finished event: {e}")
            raise e

        output_bytes = ""

        if output is not None:
            output_bytes = json_serializer.dumps(output)

        event.eventPayload = output_bytes

        return event



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




