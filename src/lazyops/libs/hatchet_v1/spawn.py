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
from pflow.utils.logs import logger
from pflow.utils.lazy import get_client
from typing import Any, Dict, List, Optional, Type, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from pflow.clients.hatchet import Worker, HatchetClient
    from pflow.types.component.workflow.base import WorkflowT


_WorkflowWorkers: Dict[str, Dict[str , mp.Process]] = {}
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


def exit_workflow_workers(timeout: Optional[int] = 5.0, workflow_names: Optional[List[str]] = None):
    """
    Exits all registered task workflow workers
    """
    global _WorkflowWorkers
    workflow_names = workflow_names or list(_WorkflowWorkers.keys())
    for workflow_name, wkflow_ops in _WorkflowWorkers.items():
        if workflow_name not in workflow_names: continue
        for op_name, process in wkflow_ops.items():
            if process is None: continue
            if process._closed: continue
            process.join(timeout)
            try:
                process.terminate()
                process.close()
            except Exception as e:
                logger.error(f'[{workflow_name} - {op_name}] Error Stopping process: {e}')
                try:
                    signal.pthread_kill(process.ident, signal.SIGKILL)
                    process.join(timeout)
                    process.terminate()
                except Exception as e:
                    logger.error(f'[{workflow_name} - {op_name}] Error Killing process: {e}')
                    with contextlib.suppress(Exception):
                        process.kill()
                        process.close()
            finally:
                process = None

    for workflow_name in workflow_names:
        if workflow_name in _WorkflowWorkers:
            del _WorkflowWorkers[workflow_name]



def start_workflow_worker(
    source: str, 
    parent: str,
    op_name: str,
):
    """
    Starts the workflow with worker
    """
    hatchet = get_client('hatchet')
    src_workflow: Type['WorkflowT'] = hatchet._get_workflow(parent = parent, source = source)
    wkflows: Dict[str, Type['WorkflowT']] = src_workflow.compile_workflows(hatchet = hatchet) 
    target_workflow = wkflows[op_name]
    # logger.info('Starting Workflow', prefix = target_workflow.name, colored = True)
    wkflow = hatchet.compile_workflow(target_workflow)
    worker = hatchet.worker(target_workflow.name)
    worker.register_workflow(wkflow)
    worker.start()


def spawn_workflow(
    source: str, 
    parent: str,
    op_name: str,
) -> mp.Process:
    """
    Spawns the workflow with worker
    """
    global _WorkflowWorkers
    workflow_ref = f'{parent}.{source}'
    if workflow_ref not in _WorkflowWorkers:
        _WorkflowWorkers[workflow_ref] = {}
    # logger.info(f'[{workflow_ref}.{op_name}] Spawning Workflow')
    # ctx = mp.get_context('spawn')
    process = mp.Process(
        target = start_workflow_worker,
        name = f'{parent}.{source}.{op_name}',
        kwargs = {
            'source': source,
            'parent': parent,
            'op_name': op_name,
        }
    )
    _WorkflowWorkers[workflow_ref][op_name] = process
    process.start()
    return process


def start_workflow(
    source: str,
    parent: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    terminate_timeout: Optional[float] = 5.0,
):
    """
    Handles the start workflow
    """
    global _WorkflowExitRegistered
    # from gevent import monkey
    # monkey.patch_all()
    hatchet = get_client('hatchet')
    wkflow: Type['WorkflowT'] = hatchet._get_workflow(parent = parent, source = source)
    op_names = wkflow.gather_op_names(include = include, exclude = exclude)
    for op_name in op_names:
        spawn_workflow(source, parent, op_name)
    if not _WorkflowExitRegistered:
        atexit.register(exit_workflow_workers, terminate_timeout)
        _WorkflowExitRegistered = True


def run_workflow(
    source: str,
    parent: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    terminate_timeout: Optional[float] = 5.0,
):
    """
    Handles the start workflow
    """
    start_workflow(source = source, parent = parent, include = include, exclude = exclude, terminate_timeout = terminate_timeout)
    while True:
        try:
            time.sleep(1)
        except Exception as e:
            logger.error(f'[{parent}.{source}] Exiting Workflow: {e}')
            break



async def _run_workflow_v1(
    source: str,
    parent: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    terminate_timeout: Optional[float] = 5.0,
):
    """
    Handles the start workflow
    """
    start_workflow(source = source, parent = parent, include = include, exclude = exclude, terminate_timeout = terminate_timeout)
    # await _WorkflowEvent.wait()
    
    while True:
        try:
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f'[{parent}.{source}] Exiting Workflow: {e}')
            _WorkflowEvent.set()
            break


async def run_workflow_v1(
    source: str,
    parent: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    terminate_timeout: Optional[float] = 5.0,
):
    """
    Handles the start workflow
    """
    loop = get_event_loop()
    task = loop.create_task(_run_workflow_v1(
        source = source,
        parent = parent,
        include = include,
        exclude = exclude,
        terminate_timeout = terminate_timeout,
    ))
    try:
        await _WorkflowEvent.wait()
        # loop.run_until_complete(task)
    except Exception as e:
        logger.error(f'[{parent}.{source}] Exiting Workflow: {e}')
        # _WorkflowEvent.set()
        # loop.stop()
    # finally:
    #     loop.close()

    # task = asyncio.create_task(_run_workflow(source = source, parent = parent, include = include, exclude = exclude, terminate_timeout = terminate_timeout))
    # asyncio.get_event_loop().run_until_complete(task)


async def _run_workflows(
    sources: Optional[List[str]] = None,
    parents: Optional[List[str]] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    include_parent: Optional[bool] = False,
    terminate_timeout: Optional[float] = 5.0,
    
):
    """
    Runs the workflows
    """
    from pflow.utils.lazy import _pflow_source_components

    if parents is None: parents = list(_pflow_source_components.keys())
    if sources is None:
        for parent in parents:
            sources = list(_pflow_source_components[parent].keys())
            if not include_parent: sources.remove('solicitation')
    workflow_names = []
    for parent in parents:
        if parent not in _pflow_source_components: 
            logger.error(f'[{parent}] Parent not found')
            continue
        for source in sources:
            if source not in _pflow_source_components[parent]:
                logger.error(f'[{parent}.{source}] Source not found')
                continue
            start_workflow(source = source, parent = parent, include = include, exclude = exclude, terminate_timeout = terminate_timeout)
            workflow_names.append(f'{parent}.{source}')
    
    # try:

    # while not _WorkflowEvent.is_set():
    while True:
        try:
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f'Exiting {len(workflow_names)} Workflows: {e}\n{workflow_names}')
            break



async def run_workflows(
    sources: Optional[List[str]] = None,
    parents: Optional[List[str]] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    include_parent: Optional[bool] = False,
    terminate_timeout: Optional[float] = 5.0,
):
    """
    Runs the workflows
    """
    # loop = get_event_loop()
    # task = loop.create_task(_run_workflows(
    #     sources = sources,
    #     parents = parents,
    #     include = include,
    #     exclude = exclude,
    #     include_parent = include_parent,
    #     terminate_timeout = terminate_timeout,
    # ))
    # loop.run_until_complete(task)
    task = asyncio.create_task(_run_workflows(sources = sources, parents = parents, include = include, exclude = exclude, include_parent = include_parent, terminate_timeout = terminate_timeout))
    asyncio.get_event_loop().run_until_complete(task)


