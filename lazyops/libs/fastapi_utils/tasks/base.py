"""
Server side tasks

Usage:

@register_server_task
async def task1():
    ...

@app.on_event("startup")
async def startup():
    spawn_server_tasks()

"""
import time
import asyncio
import threading

from lazyops.utils.logs import logger
from typing import List, Union, Set, Callable, Tuple, Optional

_server_tasks: Set[asyncio.Task] = set()
_server_task_index: List[Callable] = []
_server_primary_task_index: List[Callable] = []


def register_server_task(
    func: Callable, 
    name: Optional[str] = None,
    primary_process_only: Optional[bool] = None,
):
    """
    Register a server task
    """
    global _server_task_index, _server_primary_task_index
    from lazyops.libs.fastapi_utils.processes import GlobalContext
    if GlobalContext.is_leader_process:
        logger.info(f"Registered server task: {name or func.__name__} [Primary: {primary_process_only}]")
    if primary_process_only:
        _server_primary_task_index.append(func)
    else:
        _server_task_index.append(func)
    return func


def create_server_task(
    name: Optional[str] = None,
    primary_process_only: Optional[bool] = None,
    interval: Optional[float] = 60.0,
    stop_on_error: Optional[bool] = True,
):
    """
    Create a server task and register it with this wrapper
    """
    def decorator(func):
        """
        Inner wrapper
        """
        async def wrapper_func(*args, **kwargs):
            iterations = 0
            while True:
                try:
                    await func(*args, iterations = iterations, **kwargs)
                    iterations += 1
                except Exception as e:
                    logger.trace(f"Error in server task {name or func.__name__}", e)
                    if stop_on_error:
                        logger.info(f"Stopping server task {name or func.__name__}...")
                        break
                await asyncio.sleep(interval)
            
        register_server_task(
            func = wrapper_func, 
            name = name,
            primary_process_only = primary_process_only,
        )
        return wrapper_func
     
    return decorator


async def start_bg_tasks(
    primary_server_process_only: Optional[bool] = None,
):
    """
    Start background tasks
    """
    from lazyops.libs.fastapi_utils.processes import GlobalContext
    
    if primary_server_process_only and not GlobalContext.is_primary_server_process:
        return
    
    for task in _server_task_index:
        task = asyncio.create_task(task())
        _server_tasks.add(task)
        task.add_done_callback(_server_tasks.discard)
    
    if GlobalContext.is_primary_server_process:
        for task in _server_primary_task_index:
            task = asyncio.create_task(task())
            _server_tasks.add(task)
            task.add_done_callback(_server_tasks.discard)

def spawn_server_tasks():
    """
    Spawn server tasks
    """
    proc = threading.Thread(target = start_bg_tasks)
    proc.start()
    while True:
        try:
            time.sleep(5.0)
        except Exception as e:
            logger.info("Stopping server tasks...")
            for task in _server_tasks:
                task.cancel()
            break
    proc.join()
