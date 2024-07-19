from __future__ import annotations

"""
Handler for Spawning Workflows
"""

import os
import time
import signal
import atexit
import contextlib
import asyncio
import multiprocessing as mp
from lazyops.libs.logging import logger
from typing import Any, Dict, List, Optional, Type, Literal, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .session import HatchetSession
    from .worker import Worker
    from .workflow import WorkflowT

_WorkflowTasks: Dict[str, Dict[str , asyncio.Task]] = {}
_WorkflowExitRegistered = False
_WorkflowLoop: Optional[asyncio.AbstractEventLoop] = None
_WorkflowEvent: Optional[asyncio.Event] = None

SIGNALS = [signal.SIGINT, signal.SIGTERM] if os.name != "nt" else [signal.SIGTERM]

def get_event_loop():
    """
    Returns the event loop
    """
    global _WorkflowLoop, _WorkflowEvent
    if not _WorkflowLoop:
        try:
            _WorkflowLoop = asyncio.get_running_loop()
        except RuntimeError as e:
            # logger.error(f"Error getting running loop: {e}")
            try:
                _WorkflowLoop = asyncio.get_event_loop()
            except RuntimeError as e:
                logger.error(f"Error getting event loop: {e}")
                _WorkflowLoop = asyncio.new_event_loop()
                asyncio.set_event_loop(_WorkflowLoop)
        
    if _WorkflowEvent is None:
        _WorkflowEvent = asyncio.Event()
        for signum in SIGNALS: _WorkflowLoop.add_signal_handler(signum, _WorkflowEvent.set)
    return _WorkflowLoop


"""
V2 - Async Based Spawning
"""

def aexit_workflow_workers(timeout: Optional[int] = 5.0, workflow_names: Optional[List[str]] = None):
    """
    Exits all registered task workflow workers
    """
    global _WorkflowTasks
    workflow_names = workflow_names or list(_WorkflowTasks.keys())
    for workflow_name, wkflow_ops in _WorkflowTasks.items():
        if workflow_name not in workflow_names: continue
        for op_name, task in wkflow_ops.items():
            if task is None: continue
            task.cancel()
            try:
                task.result()
            except Exception as e:
                logger.error(f'[{workflow_name} - {op_name}] Error Stopping process: {e}')
                
            finally:
                task = None
    for workflow_name in workflow_names:
        if workflow_name in _WorkflowTasks:
            del _WorkflowTasks[workflow_name]


async def astart_worker_task(
    worker: 'Worker',
    workflow_name: str
):
    """
    Starts the worker task
    """
    worker.start()
    while not _WorkflowEvent.is_set():
        try:
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f'Exiting {workflow_name}: {e}')
            _WorkflowEvent.set()



async def astart_workflow(
    instance: Optional[str] = None,
    worker_name: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    include_crontasks: Optional[bool] = None,
    only_crontasks: Optional[bool] = None,
    terminate_timeout: Optional[float] = 5.0,
    concurrency_limit: Optional[int] = None,
    extra_workflows: Optional[Dict[str, 'WorkflowT']] = None,
    **kwargs
    # method: str = 'v1',
):
    """
    Handles the start workflow
    """
    global _WorkflowExitRegistered, _WorkflowTasks
    from .client import HatchetClient
    hatchet = HatchetClient.get_session(instance = instance, **kwargs)
    if not worker_name: worker_name = f'{hatchet.instance}_workflows'
    if only_crontasks: worker_name += '.tasks'
    
    worker = hatchet.get_worker(worker_name, max_runs = concurrency_limit)
    workflows = hatchet.compile_workflows(include = include, exclude = exclude, extra_workflows = extra_workflows, include_crontasks = include_crontasks, only_crontasks = only_crontasks)
    logger.info(f'Compiled |g|{len(workflows)}|e| Workflows: {list(workflows.keys())}', colored = True, prefix = worker_name)
    for workflow in workflows.values():
        # logger.info(f'Starting Workflow: {workflow.op_name}: {workflow}', colored = True)
        worker.register_workflow(workflow)
    if not _WorkflowExitRegistered:
        atexit.register(aexit_workflow_workers, terminate_timeout)
        _WorkflowExitRegistered = True
    await worker.async_start()



async def run_workflow(
    instance: Optional[str] = None,
    worker_name: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    include_crontasks: Optional[bool] = None,
    only_crontasks: Optional[bool] = None,
    seperate_workflows: Optional[bool] = None,
    terminate_timeout: Optional[float] = 5.0,
    concurrency_limit: Optional[int] = None,
    workflows: Optional[Dict[str, 'WorkflowT']] = None,

    workflow_name: Optional[str] = None,
    workflow_obj: Optional[Union[str, Type['WorkflowT']]] = None,
    workflow_mapping: Optional[Dict[str, Union[str, Type['WorkflowT']]]] = None,
    **kwargs
):
    # sourcery skip: reintroduce-else, remove-redundant-continue, replace-dict-items-with-values
    """
    Handles the start workflow
    """
    global _WorkflowExitRegistered, _WorkflowTasks
    from .client import HatchetClient
    if workflow_mapping or worker_name or workflow_obj: HatchetClient.register_workflow(
        workflow_name = workflow_name,
        workflow_obj = workflow_obj,
        workflow_mapping = workflow_mapping,
        instance = instance,
        **kwargs,
    )

    hatchet = HatchetClient.get_session(instance = instance, **kwargs)
    if not worker_name: worker_name = f'{hatchet.instance}'
    loop = get_event_loop()
    workers: List['Worker'] = []
    worker = hatchet.get_worker(worker_name, max_runs = concurrency_limit)
    all_workflows: Dict[str, 'WorkflowT'] = {}
    if not only_crontasks:
        workflows = hatchet.compile_workflows(include = include, exclude = exclude, include_crontasks = False)
        logger.info(f'Compiled |g|{len(workflows)}|e| Workflows: {list(workflows.keys())}', colored = True, prefix = worker_name)
        for workflow_name, workflow in workflows.items():
            if workflow.is_disabled: continue
            worker.register_workflow(workflow)
            all_workflows[workflow_name] = workflow

        workers.append(worker)
    
    if include_crontasks or only_crontasks:
        if seperate_workflows:
            worker_name += '_tasks'
            task_worker = hatchet.get_worker(worker_name, max_runs = concurrency_limit)
        else:
            task_worker = worker
        task_workflows: Dict[str, 'WorkflowT'] = hatchet.compile_workflows(include = include, exclude = exclude, only_crontasks = True)
        logger.info(f'Compiled |g|{len(task_workflows)}|e| Cron Task Workflows: {list(task_workflows.keys())}', colored = True)
        for workflow_name, workflow in task_workflows.items():
            if workflow.is_disabled: continue
            if workflow.only_production_env and (
                not hatchet.settings.is_production_env
            ): 
                continue
            task_worker.register_workflow(workflow)
            all_workflows[workflow_name] = workflow
        if seperate_workflows:
            workers.append(task_worker)

    tasks: List[asyncio.Task] = [
        loop.create_task(worker.async_start()) for worker in workers
    ]

    async def exit_all_gracefully():
        exit_tasks = [loop.create_task(worker.exit_gracefully()) for worker in workers]
        await asyncio.gather(*exit_tasks)
        loop.stop()
    
    def exit_all_forcefully():
        for worker in workers:
            worker.exit_forcefully()

    loop.add_signal_handler(
        signal.SIGINT, lambda: asyncio.create_task(exit_all_gracefully())
    )
    loop.add_signal_handler(
        signal.SIGTERM, lambda: asyncio.create_task(exit_all_gracefully())
    )
    loop.add_signal_handler(signal.SIGQUIT, lambda: exit_all_forcefully())

    from hatchet_sdk.workflows_pb2 import CreateWorkflowVersionOpts
    for workflow_name, workflow in all_workflows.items():
        if workflow.workflow_overrides:
            hatchet.client.admin.put_workflow(
                f'{hatchet.settings.app_env.name}.{workflow_name}',
                workflow,
                overrides = CreateWorkflowVersionOpts(
                    **workflow.workflow_overrides
                ),
            )

    if not _WorkflowExitRegistered:
        atexit.register(aexit_workflow_workers, terminate_timeout)
        _WorkflowExitRegistered = True
    await asyncio.gather(*tasks)


