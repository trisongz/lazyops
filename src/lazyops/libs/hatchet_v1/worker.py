from __future__ import annotations

"""
Base Hatchet Client with Modifications
"""

import signal
from threading import Thread
from concurrent.futures import Future, ThreadPoolExecutor
from hatchet_sdk.loader import ClientConfig
from hatchet_sdk.worker import Worker as BaseWorker, errorWithTraceback
from threading import Thread, current_thread
from hatchet_sdk.clients.dispatcher import Action
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
)
from hatchet_sdk.logger import logger
from typing import Any, Dict, Callable, Type


from .context import Context, ContextT
from .utils import new_client, json_serializer


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
        context_class: Type[Context] = Context,
    ):
        self.client = new_client(config)
        self.name = self.client.config.namespace + name
        self.threads: Dict[str, Thread] = {}  # Store step run ids and threads
        self.max_runs = max_runs
        self.thread_pool = ThreadPoolExecutor(max_workers=max_runs)
        self.futures: Dict[str, Future] = {}  # Store step run ids and futures
        self.contexts: Dict[str, ContextT] = {}  # Store step run ids and contexts
        self.action_registry: dict[str, Callable[..., Any]] = {}
        self._context_cls = context_class

        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        self.killing = False
        self.handle_kill = handle_kill


    def handle_start_step_run(self, action: Action):
        """
        Handles the start step run action
        """
        action_name = action.action_id
        context = self._context_cls(action, self.client)

        self.contexts[action.step_run_id] = context

        # Find the corresponding action function from the registry
        action_func = self.action_registry.get(action_name)

        if action_func:

            def callback(future: Future):
                errored = False

                # Get the output from the future
                try:
                    output = future.result()
                except Exception as e:
                    errored = True

                    # This except is coming from the application itself, so we want to send that to the Hatchet instance
                    event = self.get_step_action_event(action, STEP_EVENT_TYPE_FAILED)
                    event.eventPayload = str(errorWithTraceback(f"{e}", e))

                    try:
                        self.client.dispatcher.send_step_action_event(event)
                    except Exception as e:
                        logger.error(f"Could not send action event: {e}")

                if not errored:
                    # Create an action event
                    try:
                        event = self.get_step_action_finished_event(action, output)
                    except Exception as e:
                        logger.error(f"Could not get action finished event: {e}")
                        raise e

                    # Send the action event to the dispatcher
                    self.client.dispatcher.send_step_action_event(event)

                # Remove the future from the dictionary
                if action.step_run_id in self.futures:
                    del self.futures[action.step_run_id]

            # Submit the action to the thread pool
            def wrapped_action_func(context):
                # store the thread id
                self.threads[action.step_run_id] = current_thread()

                try:
                    res = action_func(context)
                    return res
                except Exception as e:
                    logger.error(
                        errorWithTraceback(f"Could not execute action: {e}", e)
                    )
                    raise e
                finally:
                    if action.step_run_id in self.threads:
                        # remove the thread id
                        logger.debug(
                            f"Removing step run id {action.step_run_id} from threads"
                        )

                        del self.threads[action.step_run_id]

            future = self.thread_pool.submit(wrapped_action_func, context)
            future.add_done_callback(callback)
            self.futures[action.step_run_id] = future

            # send an event that the step run has started
            try:
                event = self.get_step_action_event(action, STEP_EVENT_TYPE_STARTED)
            except Exception as e:
                logger.error(f"Could not create action event: {e}")

            # Send the action event to the dispatcher
            self.client.dispatcher.send_step_action_event(event)

    def handle_start_group_key_run(self, action: Action):
        """
        Handles the start group key run action
        """
        action_name = action.action_id
        context = self._context_cls(action, self.client)

        self.contexts[action.get_group_key_run_id] = context

        # Find the corresponding action function from the registry
        action_func = self.action_registry.get(action_name)

        if action_func:

            def callback(future: Future):
                errored = False

                # Get the output from the future
                try:
                    output = future.result()
                except Exception as e:
                    errored = True

                    # This except is coming from the application itself, so we want to send that to the Hatchet instance
                    event = self.get_group_key_action_event(
                        action, GROUP_KEY_EVENT_TYPE_FAILED
                    )
                    event.eventPayload = str(errorWithTraceback(f"{e}", e))

                    try:
                        self.client.dispatcher.send_group_key_action_event(event)
                    except Exception as e:
                        logger.error(f"Could not send action event: {e}")

                if not errored:
                    # Create an action event
                    try:
                        event = self.get_group_key_action_finished_event(action, output)
                    except Exception as e:
                        logger.error(f"Could not get action finished event: {e}")
                        raise e

                    # Send the action event to the dispatcher
                    self.client.dispatcher.send_group_key_action_event(event)

                # Remove the future from the dictionary
                if action.get_group_key_run_id in self.futures:
                    del self.futures[action.get_group_key_run_id]

            # Submit the action to the thread pool
            def wrapped_action_func(context):
                # store the thread id
                self.threads[action.get_group_key_run_id] = current_thread()

                try:
                    res = action_func(context)
                    return res
                except Exception as e:
                    logger.error(
                        errorWithTraceback(f"Could not execute action: {e}", e)
                    )
                    raise e
                finally:
                    if action.get_group_key_run_id in self.threads:
                        # remove the thread id
                        logger.debug(
                            f"Removing step run id {action.get_group_key_run_id} from threads"
                        )

                        del self.threads[action.get_group_key_run_id]

            future = self.thread_pool.submit(wrapped_action_func, context)
            future.add_done_callback(callback)
            self.futures[action.get_group_key_run_id] = future

            # send an event that the step run has started
            try:
                event = self.get_group_key_action_event(
                    action, GROUP_KEY_EVENT_TYPE_STARTED
                )
            except Exception as e:
                logger.error(f"Could not create action event: {e}")

            # Send the action event to the dispatcher
            self.client.dispatcher.send_group_key_action_event(event)



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