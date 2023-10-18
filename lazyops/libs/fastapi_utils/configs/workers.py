"""
Preconfigured Worker Configurations
"""

import contextlib
from lazyops.types.models import BaseSettings
from lazyops.utils.helpers import import_function
from typing import List, Optional, Dict, Any, Callable, Union, TYPE_CHECKING


if TYPE_CHECKING:
    with contextlib.suppress(ImportError):
        from aiokeydb import Worker, TaskQueue



class WorkerSettings(BaseSettings):
    """
    Worker Queue Settings
    """
    enabled: bool = True

    queue_enabled: bool = True # if True, enables the queue
    queue_name: Optional[str] = None # the queue for the local worker. This will be set on init from main settings
    
    queue_shared_prefix: Optional[str] = "cluster"
    queue_db_id: Optional[int] = 3

    worker_cls: Optional[str] = None
    worker_serializer: Optional[str] = None

    socket_timeout: Optional[float] = 120.0
    socket_connect_timeout: Optional[float] = 120.0
    connection_timeout: Optional[int] = 600
    socket_keepalive: Optional[bool] = True
    retry_on_timeout: Optional[bool] = True
    health_check_interval: Optional[int] = 15
    is_leader_process: Optional[bool] = None


    class Config:
        case_sensitive = False
        env_prefix = "WORKER_"

    
    def get_queue(
        self, 
        name: str, 
        db_id: Optional[int] = None, 
        shared: Optional[bool] = False,
        serializer: Optional[str] = None,
        is_leader_process: Optional[bool] = None,
        **kwargs
    ) -> 'TaskQueue':
        """
        Returns a Task Queue

        Args:
            name (str): The name of the queue to use
            db_id (Optional[int]): The db id to use. If None, uses the default
            shared (Optional[bool]): If True, uses the shared prefix. If False, does not add a prefix
            kwargs: Any additional kwargs to pass to the TaskQueue

        """
        from aiokeydb import TaskQueue
        queue_name = f'{self.queue_shared_prefix}.{name}' if shared else name
        if serializer is not None: 
            from aiokeydb.serializers import SerializerType
            kwargs['serializer'] = SerializerType(serializer).get_serializer()
        
        is_leader_process = is_leader_process if is_leader_process is not None else self.is_leader_process
        return TaskQueue(
            queue_name = queue_name,
            db = db_id or self.queue_db_id,
            is_leader_process = is_leader_process,
            **kwargs
        )
    
    def get_worker(
        self, 
        worker_module: Union[str, Callable], 
        name: Optional[str] = None, 
        worker_name: Optional[str] = None,
        queue: Optional['TaskQueue'] = None,
        queue_kwargs: Optional[Dict[str, Any]] = None,
        is_leader_process: Optional[bool] = None,
        **kwargs,
    ) -> 'Worker':
        """
        Returns a Worker from a Task Queue

        Args:
            worker_module (Union[str, Callable]): The worker class to use. Imports the class
            name (Optional[str]): The name of the queue to use. If None, uses the first part of the worker_cls name
            worker_name (Optional[str], optional): The name of the worker. Defaults to None.
            queue (Optional['TaskQueue'], optional): The queue to use. Defaults to None.
            queue_kwargs (Optional[Dict[str, Any]], optional): The kwargs to pass to the queue. Defaults to None.
            **kwargs: The kwargs to pass to the worker

        """
        worker_cls: 'Worker' = import_function(worker_module)
        if name is None: name = worker_module.split('.')[0]
        queue_kwargs = queue_kwargs or {}
        is_leader_process = is_leader_process if is_leader_process is not None else self.is_leader_process
        try:
            return worker_cls(queue = queue or self.get_queue(name, **queue_kwargs), name = worker_name or name, is_leader_process = is_leader_process, **kwargs)
        except Exception:
            return worker_cls(queue = queue or self.get_queue(name, **queue_kwargs), name = worker_name or name, **kwargs)