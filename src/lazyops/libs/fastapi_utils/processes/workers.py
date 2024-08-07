from __future__ import annotations

import os
import signal
import asyncio
import contextlib

from typing import Optional, List, TypeVar, Callable, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    with contextlib.suppress(ImportError):
        from aiokeydb.types.worker import Worker


_WorkerCtx: Dict[str, Dict[str, List['Worker']]] = {}


async def stop_worker(
    loop: asyncio.BaseEventLoop,
    worker: 'Worker',
    signame: str,
    verbose: Optional[bool] = True,
):
    """
    Stops the worker
    """
    from lazyops.utils import logger
    await worker.stop()
    if verbose: logger.warning(f'Worker {worker.name}: Received exit signal {signame} for ...')
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    if verbose: logger.warning(f'Worker {worker.name}: Cancelling {len(tasks)} outstanding tasks')
    loop.stop()
    if verbose: logger.warning(f'Worker {worker.name}: Loop stopped')


def spawn_new_worker(
    name: str, 
    index: Optional[int] = None, 
    kind: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None, 
    verbose: Optional[bool] = True, 
    is_primary_worker: Optional[bool] = True, 
    settings_config_func: Optional[Callable] = None, # should configure the settings
    get_worker_func: Optional[Callable] = None,
    **kwargs
):
    """
    Spawns a new worker
    """
    global _WorkerCtx
    assert get_worker_func is not None, "get_worker_func must be defined"
    os.environ['IS_WORKER_PROCESS'] = 'True'
    
    if index is None: index = 0
    if kind is None: kind = 'default'
    if settings_config_func is not None:
        settings_config_func(
            name = name,
            index = index,
            kind = kind,
            config = config,
            verbose = verbose,
            is_primary_worker = is_primary_worker,
            **kwargs
        )
    
    worker: 'Worker' = get_worker_func(
        name = name,
        index = index,
        kind = kind,
        config = config,
        verbose = verbose,
        is_primary_worker = is_primary_worker,
        **kwargs
    )
    worker.name = f"{worker.name}-{index}"
    if worker.is_leader_process is None:
        worker.is_leader_process = is_primary_worker
    loop = asyncio.new_event_loop()
    for signame in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(getattr(signal, signame), lambda signame=signame: asyncio.create_task(stop_worker(loop, worker, signame, verbose = verbose)))
        
    if kind not in _WorkerCtx: _WorkerCtx[kind] = {}
    if name not in _WorkerCtx[kind]: _WorkerCtx[kind][name] = []
    _WorkerCtx[kind][name].append(worker)
    loop.run_until_complete(worker.start())

    

async def terminate_worker(name: str, kind: Optional[str] = None):
    """
    Terminates a worker
    """
    global _WorkerCtx
    if kind is None: kind = 'default'
    if kind not in _WorkerCtx: return
    if name not in _WorkerCtx[kind]: return
    for worker in _WorkerCtx[kind][name]:
        await worker.stop()
        _WorkerCtx[kind][name].remove(worker)
    


