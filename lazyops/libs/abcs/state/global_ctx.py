from __future__ import annotations

import os
import abc
import signal
import contextlib
import multiprocessing
import pathlib
import asyncio

from typing import Optional, List, TypeVar, Callable, Dict, Any, overload, Type, Union, TYPE_CHECKING
from lazyops.utils.lazy import lazy_import
from lazyops.libs.proxyobj import ProxyObject, proxied
from lazyops.imports._psutil import _psutil_available

if _psutil_available:
    import psutil

if TYPE_CHECKING:
    from lazyops.utils.logs import Logger
    from ..configs.base import AppSettings
    from lazyops.types.models import BaseSettings
    from lazyops.libs.abcs.types.state import AppState

    from kvdb import TaskFunction, CronJob, TaskWorker, TaskQueue

    # with contextlib.suppress(ImportError):
    #     from kvdb import TaskWorker, TaskQueue
        # from aiokeydb.types.task_queue import TaskQueue
        # from aiokeydb.types.worker import Worker


# SettingsT = TypeVar('SettingsT', bound='AppSettings')


# class GlobalContextClass(abc.ABC):

@proxied
class GlobalContext(abc.ABC):
    """
    Global Context for FastAPI 
    """


    workers: Dict[str, Dict[str, Union[multiprocessing.Process, 'TaskWorker']]] = {}
    # queues: Dict[str, Dict[str, 'TaskQueue']] = {}
    server_processes: List['multiprocessing.Process'] = []
    # worker_processes: Dict[str, Dict[str, List['multiprocessing.Process']]] = {}

    asyncio_tasks: List[asyncio.Task] = []

    on_close_funcs: List[Callable] = []

    settings_func: Optional[Union[Callable, str]] = None # type: ignore
    settings_config_func: Optional[Union[Callable, str]] = None # type: ignore
    get_worker_func: Optional[Union[Callable, str, List[str]]] = None # type: ignore
    # get_num_worker_func: Optional[Union[Callable, str]] = None # type: ignore
    # get_worker_names_func: Optional[Union[Callable, str]] = None
    
    
    def __init__(self, **kwargs):
        """
        Creates the global context
        """
        self._settings: Optional['AppSettings'] = None
        self._state: Optional['AppState'] = None
        self._logger: Optional['Logger'] = None

    def configure(
        self,
        # queue_types: Optional[List[str]] = None,
        settings_func: Optional[Union[Callable, str]] = None, # type: ignore
        settings_config_func: Optional[Union[Callable, str]] = None, # type: ignore
        get_worker_func: Optional[Union[Callable, str, List[str]]] = None, # type: ignore
        # get_num_worker_func: Optional[Union[Callable, str]] = None, # type: ignore
        # get_worker_names_func: Optional[Union[Callable, str]] = None,
    ):
        """
        Configures the global context
        """
        # if queue_types is not None:
        #     for kind in queue_types:
        #         self.add_queue_type(kind)
        
        if settings_func is not None:
            if isinstance(settings_func, str):
                settings_func = lazy_import(settings_func)
            self.settings_func = settings_func
        
        if settings_config_func is not None:
            self.settings_config_func = settings_config_func
        
        if get_worker_func is not None:
            self.get_worker_func = get_worker_func
        
        # if get_num_worker_func is not None:
        #     self.get_num_worker_func = get_num_worker_func
        
        # if get_worker_names_func is not None:
        #     self.get_worker_names_func = get_worker_names_func
            

    @property
    def settings(self) -> 'AppSettings':
        """
        Returns the settings
        """
        if self._settings is None:
            if self.settings_func is None:
                raise RuntimeError("Settings not initialized. Set `GlobalContext.settings_func` to a function that returns the settings.")
            self._settings = self.settings_func()
        return self._settings
    
    @property
    def state(self) -> 'AppState':
        """
        Returns the state
        """
        if self._state is None:
            from lazyops.libs.abcs.types.state import AppState
            self._state = AppState()
            self._state.bind_settings(self.settings)
        return self._state
    
    @property
    def is_leader_process(self) -> bool:
        """
        Returns if this is the leader process
        """
        return self.state.is_leader_process or multiprocessing.parent_process() is None
    
    @property
    def is_primary_server_process(self) -> bool:
        """
        Returns if this is the primary server process
        """
        return self.state.is_primary_server_process or multiprocessing.parent_process() is None
    

    def get_settings_func(self, func: Union[Callable, str]) -> Callable:
        """
        Returns the settings func
        """
        if isinstance(func, str):
            func = getattr(self.settings, func)
        return func
    

    @property
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        if self._logger is None:
            from lazyops.utils.logs import logger as _logger
            self._logger = _logger
        return self._logger

    def get_child_process_ids(self, name: Optional[str] = None, kind: Optional[str] = None, process_id: Optional[int] = None, first: Optional[bool] = True) -> List[int]:
        """
        Returns the child process ids
        """
        if not _psutil_available:
            self.logger.warning("psutil not available. Cannot get child process ids")
            return []
        if not name and not process_id:
            raise ValueError("Must provide either name or process_id")
        if process_id:
            proc = psutil.Process(process_id)
            return [child.pid for child in proc.children(recursive=True)]
        if name in {'server', 'app'} and kind is None:
            procs = []
            for proc in self.server_processes:
                if proc._closed: continue
                parent = psutil.Process(proc.pid)
                procs.extend(child.pid for child in parent.children(recursive=True))
                if first: break
            return procs
        
        procs = []
        if name == 'worker':
            for worker_name, values in self.workers.items():
                process = values.get('process')
                if process is None or process._closed: continue
                parent = psutil.Process(process.pid)
                procs.extend(child.pid for child in parent.children(recursive=True))
                if first: break
        return procs
    
    @overload
    def start_task_workers(
        self,
        num_workers: Optional[int] = 1,
        start_index: Optional[int] = None,

        worker_name: Optional[str] = 'global',
        worker_name_sep: Optional[str] = '-',

        worker_imports: Optional[Union[str, List[str]]] = None,
        worker_cls: Optional[str] = None,
        worker_class: Optional[Type['TaskWorker']] = None,
        worker_config: Optional[Dict[str, Any]] = None,
        worker_queues: Optional[Union[str, List[str]]] = 'all',
        
        worker_functions: Optional[List['TaskFunction']] = None,
        worker_cron_jobs: Optional[List['CronJob']] = None,
        worker_startup: Optional[Union[List[Callable], Callable,]] = None,
        worker_shutdown: Optional[Union[List[Callable], Callable,]] = None,
        worker_before_process: Optional[Callable] = None,
        worker_after_process: Optional[Callable] = None,
        worker_attributes: Optional[Dict[str, Any]] = None,

        queue_names: Optional[Union[str, List[str]]] = None,
        queue_config: Optional[Dict[str, Any]] = None,
        queue_class: Optional[Type['TaskQueue']] = None,

        max_concurrency: Optional[int] = None,
        max_broadcast_concurrency: Optional[int] = None,

        debug_enabled: Optional[bool] = False,
        disable_env_name: Optional[bool] = False,
        method: Optional[str] = 'mp',
        use_new_event_loop: Optional[bool] = None,
        disable_worker_start: Optional[bool] = False,
        terminate_timeout: Optional[float] = 5.0,
        **kwargs,
    ):
        ...


    def start_task_workers(
        self,
        worker_name: Optional[str] = None,
        worker_imports: Optional[Union[str, List[str]]] = None,
        num_workers: Optional[int] = 1,
        worker_queues: Optional[Union[str, List[str]]] = 'all',
        debug_enabled: Optional[bool] = None,
        verbose: Optional[bool] = True,
        **kwargs,
    ):
        """
        Starts the task workers
        """
        
        if worker_name is None:
            worker_name = self.settings.module_name
        if worker_imports is None:
            worker_imports = self.get_worker_func
            if not isinstance(worker_imports, list):
                worker_imports = [worker_imports]
        if debug_enabled is None:
            debug_enabled = self.settings.debug_enabled or self.settings.is_development_env
        
        from kvdb import tasks
        workers = tasks.start_task_workers(
            worker_name = worker_name,
            worker_imports = worker_imports,
            num_workers = num_workers,
            worker_queues = worker_queues,
            debug_enabled = debug_enabled,
            **kwargs,
        )
        if verbose:
            self.logger.info(f"Started workers: {workers}")
        self.workers.update(workers)

    def stop_task_workers(
        self,
        worker_names: Optional[List[str]] = None,
        timeout: Optional[float] = 5.0,
        verbose: bool = True,
        **kwargs,
    ):
        """
        Stops the task workers
        """
        if worker_names is None:
            worker_names = list(self.workers.keys())
        from kvdb.tasks.spawn import exit_task_workers
        exit_task_workers(worker_names = worker_names, timeout = timeout)
        for worker_name in worker_names:
            if verbose: self.logger.info(f"Stopped worker: {worker_name}")
            _ = self.workers.pop(worker_name, None)

    
    def start_server_process(self, cmd: str, verbose: bool = True):
        """
        Starts the server process
        """
        if verbose: self.logger.info(f"Starting Server Process: {cmd}")
        context = multiprocessing.get_context('spawn')
        p = context.Process(target = os.system, args = (cmd,))
        p.start()
        self.state.add_leader_process_id(p.pid, 'server')
        self.server_processes.append(p)
        return p
    
    def add_server_process(self, name: str, cmd: str, verbose: bool = True):
        """
        Adds the server process
        """
        if verbose: self.logger.info(f"Adding Server Process: {cmd}", prefix = name)
        context = multiprocessing.get_context('spawn')
        p = context.Process(target = os.system, args = (cmd,))
        p.start()
        self.server_processes.append(p)
        return p

    def stop_server_processes(self, verbose: bool = True, timeout: float = 5.0):
        """
        Stops the server processes
        """
        curr_proc, n_procs = 0, len(self.server_processes)
        kind = 'Server'
        while self.server_processes:
            proc = self.server_processes.pop()
            if proc._closed: continue
            log_name = f'`|g|app-{curr_proc}|e|`'
            if verbose: 
                self.logger.info(f"- [|y|{kind:7s}|e|] Stopping: [ {curr_proc + 1}/{n_procs} ] {log_name:20s} (Process ID: {proc.pid})", colored = True)
            proc.join(timeout)
            proc.terminate()
            try:
                proc.close()
            except Exception as e:
                if verbose: self.logger.info(f"|y|[{kind:7s}]|e| Failed Stop: [ {curr_proc + 1}/{n_procs} ] {log_name:20s} (Error: |r|{e}|e|)", colored = True)
                try:
                    signal.pthread_kill(proc.ident, signal.SIGKILL)
                    proc.join(timeout)
                    proc.terminate()
                except Exception as e:
                    if verbose: self.logger.info(f"|r|[{kind:7s}]|e| Failed Kill: [ {curr_proc + 1}/{n_procs} ] {log_name:20s} (Error: |r|{e}|e|)", colored = True)
                with contextlib.suppress(Exception):
                    proc.kill()
                    proc.close()
            curr_proc += 1
        # if verbose: self.logger.info(f"Stopped all {curr_proc} server processes")

    def start_asyncio_task(
        self,
        func: Callable,
        *args,
        **kwargs,
    ):
        """
        Starts an asyncio task
        """
        self.asyncio_tasks.append(
            asyncio.create_task(func(*args, **kwargs))
        )
    
    def add_asyncio_task(
        self,
        task: asyncio.Task,
    ) -> None:
        """
        Adds an asyncio task
        """
        self.asyncio_tasks.append(task)

    def stop_all_asyncio_tasks(
        self,
        verbose: Optional[bool] = None,
    ):
        """
        Stops all asyncio tasks
        """
        if not self.asyncio_tasks: return
        for task in self.asyncio_tasks:
            if task.done(): continue
            if verbose: self.logger.info(f"Stopping Asyncio Task: {task}", colored = True)
            task.cancel()
        self.asyncio_tasks = []
    
    def end_all_processes(self, verbose: bool = True, timeout: float = 5.0):
        """
        Terminates all processes
        """
        # for kind, names in self.worker_processes.items():
        #     for name in names:
        #         self.stop_worker_processes(name = name, verbose = verbose, timeout = timeout, kind = kind)
        self.stop_task_workers(timeout = timeout, verbose = verbose)
        self.stop_server_processes(verbose = verbose, timeout = timeout)
        self.stop_all_asyncio_tasks(verbose = verbose)
        # self.logger.info("Terminated all processes")

    def register_on_close(self, func: Callable, *args, **kwargs):
        """
        Registers a function to be called on close
        """
        import functools
        _func = functools.partial(func, *args, **kwargs)
        self.on_close_funcs.append(_func)
        self.logger.info(f"Registered function {func.__name__} to be called on close")


    async def aclose_processes(self, verbose: bool = True, timeout: float = 5.0):
        """
        Handles closing all processes
        """
        import anyio
        for func in self.on_close_funcs:
            with anyio.fail_after(timeout):
                try:
                    await func()
                    if verbose: self.logger.info(f"Called function {func.__name__} on close")
                except TimeoutError as e:
                    self.logger.error(f"Timeout calling function {func.__name__} on close: {e}")
                except Exception as e:
                    self.logger.trace(f"Error calling function {func.__name__} on close", error = e)
    
    def start_debug_mode(self):
        """
        Enters Debug Mode
        """
        self.logger.warning('Entering Debug Mode. Sleeping Forever')
        import time
        import sys
        while True:
            try:
                time.sleep(900)
            except Exception as e:
                self.logger.error(e)
                break
        sys.exit(0)


    async def arun_until_complete(
        self,
        termination_file: str = None,
    ):
        """
        Runs the event loop until complete
        """

        if termination_file is None:
            termination_file = os.getenv('WORKER_TERMINATION_FILE')
        
        from .types import GracefulKiller
        watch = GracefulKiller()
        tmp_kill_file = pathlib.Path(termination_file) if termination_file is not None else None
        while not watch.kill_now:
            try: 
                await asyncio.sleep(1.0)
                if tmp_kill_file is not None and tmp_kill_file.exists():
                    self.logger.warning(f"Found termination file: {tmp_kill_file}")
                    break
            except KeyboardInterrupt:
                self.logger.warning("Keyboard Interrupt")
                break
            except Exception as e:
                self.logger.error(f"Error: {e}")
                break
        
        self.end_all_processes()
        await self.aclose_processes()



    



# GlobalContext: GlobalContextClass = ProxyObject(GlobalContextClass)
