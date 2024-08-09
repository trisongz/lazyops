
from __future__ import annotations

from hatchet_sdk.worker import Worker as BaseWorker
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from hatchet_sdk.worker import *


class Worker(BaseWorker):
    
    def __init__(
        self,
        name: str,
        max_runs: int | None = None,
        debug=False,
        handle_kill=True,
        config: ClientConfig = {},
        session: Optional['HatchetSession'] = None,
        context_class: Type[Context] = Context,

    ):
        # We store the config so we can dynamically create clients for the dispatcher client.
        self.config = config
        self.session = session
        self.client = self.session.client if self.session else new_client(config)
        self._context_cls = context_class

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

