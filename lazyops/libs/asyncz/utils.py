from typing import List
from .types import AsyncTask, TaskStatus, WaitType, ErrorHandling
from .errors import AsyncTaskException


def await_all(
    tasks: List[AsyncTask], 
    error_handling: ErrorHandling = ErrorHandling.RAISE
):
    """
    Await all tasks to complete

    :param tasks: List of tasks
    :param error_handling: Error handling strategy (raise or ignore)
    """
    result = []
    for task in tasks:
        if task.status == TaskStatus.PENDING:
            while not task.thread.is_alive(): pass
            task.thread.join()

    for task in tasks:
        if task.status == TaskStatus.SUCCESS:
            result.append(task.result)
        elif task.status == TaskStatus.FAILURE:
            if error_handling == ErrorHandling.RAISE:
                raise AsyncTaskException(str(task.exception), task.func.__name__)
    
    return result


def await_first(
    tasks: List[AsyncTask],
    error_handling: ErrorHandling = ErrorHandling.RAISE
):
    """
    Await first task to complete

    :param tasks: List of tasks
    :param error_handling: Error handling strategy (raise or ignore)
    """

    first_failed: AsyncTask = None
    while tasks:
        for i in range(len(tasks)):
            if tasks[i].status == TaskStatus.SUCCESS:
                return tasks[i].result
            elif tasks[i].status == TaskStatus.FAILURE:
                if first_failed is None: first_failed = tasks[i]
                tasks.pop(i)
                i -= 1
    if first_failed is not None and error_handling == ErrorHandling.RAISE:
        raise AsyncTaskException(str(first_failed.exception), first_failed.func.__name__)
    return None

def await_until(
    tasks: List[AsyncTask],
    wait_type: WaitType = WaitType.ALL,
    error_handling: ErrorHandling = ErrorHandling.RAISE
):
    """
    Await until tasks are completed based on wait_type

    :param tasks: List of tasks
    :param wait_type: Wait type (all or first)
    :param error_handling: Error handling strategy (raise or ignore)
    """
    if wait_type == WaitType.ALL:
        return await_all(tasks, error_handling)
    elif wait_type == WaitType.FIRST:
        return await_first(tasks, error_handling)
    else:
        raise ValueError(f"Invalid wait_type: {wait_type}")
