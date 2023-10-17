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
from typing import List, Union, Set, Callable, Tuple

_server_tasks: Set[asyncio.Task] = set()
_server_task_index: List[Callable] = []


def register_server_task(func: Callable):
    """
    Register a server task
    """
    global _server_task_index
    from lazyops.libs.fastapi_utils.processes import GlobalContext
    if GlobalContext.is_leader_process:
        logger.info(f"Registered server task: {func.__name__}")
    _server_task_index.append(func)
    return func


async def start_bg_tasks():
    """
    Start background tasks
    """
    for task in _server_task_index:
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
