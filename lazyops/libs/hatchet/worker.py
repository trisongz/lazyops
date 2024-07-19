from __future__ import annotations

"""
Base Hatchet Client with Modifications
"""

import signal
import asyncio
import functools
import contextvars
import grpc
from threading import Thread
from concurrent.futures import Future, ThreadPoolExecutor
from hatchet_sdk.loader import ClientConfig
from hatchet_sdk.worker import Worker as BaseWorker, WorkerStatus, errorWithTraceback, copy_context_vars
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

from lazyops.utils.serialization import Json
from typing import Any, Dict, Callable, Type, Optional, TYPE_CHECKING
from .context import Context, ContextT
from .utils import new_client, json_serializer
from lazyops.utils.logs import logger as _logger

if TYPE_CHECKING:
    from .session import HatchetSession


class Worker(BaseWorker):
    """
    The Worker Object
    """
    def __init__(
        self,
        name: str,
        max_runs: int | None = None,
        debug: bool = False,
        handle_kill: bool = True,
        config: ClientConfig = None,
        session: Optional['HatchetSession'] = None,
        context_class: Type[Context] = Context,
    ):
        self.config = config
        self.session = session
        # self.client = new_client_raw(config)
        # print(self.config.server_url)
        # print(self.config.host_port)
        # print(self.config.token)
        self.client = self.session.client if self.session else new_client(config)
        self.name = self.client.config.namespace + name
        self._context_cls = context_class
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


    async def handle_start_step_run(self, action: Action):
        """
        Handles the start step run action
        """
        action_name = action.action_id
        context = self._context_cls(
            action, 
            self.dispatcher_client,
            self.admin_client,
            self.client.event,
            self.client.workflow_listener,
            self.workflow_run_event_listener,
            self.client.config.namespace,
        )

        self.contexts[action.step_run_id] = context
        _logger.info(f'[{action.step_run_id}] Started Step Run', prefix = self.name, colored = True)

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

            # task = self.loop.create_task(self.async_wrapped_action_func(context, action_func, action))
            # task.add_done_callback(self.callback(action))
            # self.tasks[action.step_run_id] = task

            try:
                await task
            except Exception as e:
                # do nothing, this should be caught in the callback
                pass


    # We wrap all actions in an async func
    async def async_wrapped_action_func(self, context: Context, action_func, action: Action, run_id: str):
        # sourcery skip: remove-unnecessary-else
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
                return await self.loop.run_in_executor(self.thread_pool, pfunc)
        except Exception as e:
            if ']:' in str(e) and '- 40' in str(e):
                logger.error(f"[{action.step_run_id} - {action.job_name}] Error in action: {e}")
            else:
                logger.error(errorWithTraceback(f"Could not execute action: {e}", e))
            raise e
            # logger.error(errorWithTraceback(f"Could not execute action: {e}", e))
            # raise e
        finally:
            self.cleanup_run_id(run_id)


    async def handle_start_group_key_run(self, action: Action):
        # sourcery skip: use-contextlib-suppress
        """
        Handles the start group key run action
        """
        action_name = action.action_id
        context = self._context_cls(
            action,
            self.dispatcher_client,
            self.admin_client,
            self.client.event,
            self.client.workflow_listener,
            self.workflow_run_event_listener,
            self.client.config.namespace,
        )
        # _logger.info(f'[{action.get_group_key_run_id}] Started Group Key Run for {action.action_id}', prefix = self.name, colored = True)
        self.contexts[action.get_group_key_run_id] = context

        # Find the corresponding action function from the registry
        action_func = self.action_registry.get(action_name)

        if action_func:

            def callback(task: asyncio.Task):
                errored = False
                cancelled = task.cancelled()

                # Get the output from the future
                try:
                    if not cancelled:
                        output = task.result()
                except Exception as e:
                    errored = True

                    # This except is coming from the application itself, so we want to send that to the Hatchet instance
                    event = self.get_group_key_action_event(
                        action, GROUP_KEY_EVENT_TYPE_FAILED
                    )
                    event.eventPayload = str(errorWithTraceback(f"{e}", e))

                    try:
                        self.dispatcher_client.send_group_key_action_event(event)
                    except Exception as e:
                        logger.error(f"Could not send action event: {e}")

                if not errored and not cancelled:
                    # Create an action event
                    try:
                        event = self.get_group_key_action_finished_event(action, output)
                    except Exception as e:
                        logger.error(f"Could not get action finished event: {e}")
                        raise e

                    # Send the action event to the dispatcher
                    self.dispatcher_client.send_group_key_action_event(event)

                # Remove the future from the dictionary
                if action.get_group_key_run_id in self.tasks:
                    del self.tasks[action.get_group_key_run_id]

            def thread_action_func(context, action_func):
                self.threads[action.step_run_id] = current_thread()
                return action_func(context)

            # We wrap all actions in an async func
            async def async_wrapped_action_func(context):
                try:
                    if action_func._is_coroutine:
                        return await action_func(context)
                    pfunc = functools.partial(thread_action_func, context, action_func)
                    res = await self.loop.run_in_executor(self.thread_pool, pfunc)

                    if action.step_run_id in self.threads:
                        # remove the thread id
                        # logger.debug(f"Removing step run id {action.step_run_id} from threads")
                        del self.threads[action.step_run_id]

                    return res
                except Exception as e:
                    # str_error = str(e)
                    if ']:' in str(e) and '- 40' in str(e):
                        logger.error(f"[{action.step_run_id} - {action.job_name}] Error in action: {e}")
                    else:
                        logger.error(errorWithTraceback(f"Could not execute action: {e}", e))
                    raise e
                finally:
                    if action.step_run_id in self.tasks:
                        del self.tasks[action.step_run_id]

            task = self.loop.create_task(async_wrapped_action_func(context))
            task.add_done_callback(callback)
            self.tasks[action.get_group_key_run_id] = task

            # send an event that the step run has started
            try:
                event = self.get_group_key_action_event(action, GROUP_KEY_EVENT_TYPE_STARTED)
            except Exception as e:
                logger.error(f"Could not create action event: {e}")

            # Send the action event to the dispatcher
            self.dispatcher_client.send_group_key_action_event(event)

            try:
                await task
            except Exception as e:
                # do nothing, this should be caught in the callback
                pass


    def get_step_action_finished_event(
        self, action: Action, output: Any
    ) -> StepActionEvent:
        """
        Gets the step action finished event
        """
        try:
            event = self.get_step_action_event(action, STEP_EVENT_TYPE_COMPLETED)
        except Exception as e:
            logger.error(f"Could not create action finished event: {e}")
            raise e

        output_bytes = json_serializer.dumps(output) if output is not None else ""
        event.eventPayload = output_bytes
        return event

    
    async def exit_gracefully(self):
        if self.killing:
            self.exit_forcefully()
            return

        self.killing = True

        logger.info("Exiting gracefully...")

        try:
            self.listener.unregister()
        except Exception as e:
            logger.error(f"Could not unregister worker: {e}")

        try:
            logger.info("Waiting for tasks to finish...")

            await self.wait_for_tasks()
        except Exception as e:
            logger.error(f"Could not wait for tasks: {e}")

        # Wait for 1 second to allow last calls to flush. These are calls which have been
        # added to the event loop as callbacks to tasks, so we're not aware of them in the
        # task list.
        await asyncio.sleep(1)

    
    def exit_forcefully(self):
        self.killing = True
        logger.info("Forcefully exiting hatchet worker...")
        try:
            self.listener.unregister()
        except Exception as e:
            logger.error(f"Could not unregister worker: {e}")
