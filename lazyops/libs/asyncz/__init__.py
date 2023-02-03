# Asyncz - Forked from [FastAsync](https://github.com/thebowenfeng/FastAsync/)


from .errors import AsyncTaskException
from .types import (
    WaitType,
    ErrorHandling,
    TaskStatus,
    AsyncTask, 
    global_task_manager
)
from .utils import (
    await_all,
    await_first,
    await_until
)

from typing import Callable

def asyncify(func: Callable):
    """
    Turn a function into an async task using asyncz task manager
    """
    def wrapper(*args, **kwargs):
        task = AsyncTask(func, *args, **kwargs)
        task.run()
        return task
    return wrapper


def set_max_threads(num : int):
    global_task_manager.max_threads(num)

