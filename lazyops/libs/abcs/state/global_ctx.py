from __future__ import annotations

import os
import abc
import signal
import contextlib
import multiprocessing

from typing import Optional, List, TypeVar, Callable, Dict, Any, Union, TYPE_CHECKING
from lazyops.utils.lazy import lazy_import
from lazyops.libs.proxyobj import ProxyObject
from lazyops.imports._psutil import _psutil_available

if _psutil_available:
    import psutil

if TYPE_CHECKING:
    from lazyops.utils.logs import Logger
    from lazyops.types.models import BaseSettings
    from lazyops.libs.fastapi_utils.types.state import AppState

    with contextlib.suppress(ImportError):
        from kvdb import TaskWorker, TaskQueue
        # from aiokeydb.types.task_queue import TaskQueue
        # from aiokeydb.types.worker import Worker


SettingsT = TypeVar('SettingsT', bound='BaseSettings')


class GlobalContextClass(abc.ABC):
    """
    Global Context for FastAPI 
    """

    queues: Dict[str, Dict[str, 'TaskQueue']] = {}
    server_processes: List['multiprocessing.Process'] = []
    worker_processes: Dict[str, Dict[str, List['multiprocessing.Process']]] = {}

    on_close_funcs: List[Callable] = []

    settings_func: Optional[Union[Callable, str]] = None # type: ignore
    settings_config_func: Optional[Union[Callable, str]] = None # type: ignore
    get_worker_func: Optional[Union[Callable, str]] = None # type: ignore
    get_num_worker_func: Optional[Union[Callable, str]] = None # type: ignore
    get_worker_names_func: Optional[Union[Callable, str]] = None
    
    
    def __init__(self, **kwargs):
        """
        Creates the global context
        """
        self._settings: Optional[SettingsT] = None
        self._state: Optional['AppState'] = None
        self._logger: Optional['Logger'] = None

    def configure(
        self,
        queue_types: Optional[List[str]] = None,
        settings_func: Optional[Union[Callable, str]] = None, # type: ignore
        settings_config_func: Optional[Union[Callable, str]] = None, # type: ignore
        get_worker_func: Optional[Union[Callable, str]] = None, # type: ignore
        get_num_worker_func: Optional[Union[Callable, str]] = None, # type: ignore
        get_worker_names_func: Optional[Union[Callable, str]] = None,
    ):
        """
        Configures the global context
        """
        if queue_types is not None:
            for kind in queue_types:
                self.add_queue_type(kind)
        
        if settings_func is not None:
            if isinstance(settings_func, str):
                settings_func = lazy_import(settings_func)
            self.settings_func = settings_func
        
        if settings_config_func is not None:
            self.settings_config_func = settings_config_func
        
        if get_worker_func is not None:
            self.get_worker_func = get_worker_func
        
        if get_num_worker_func is not None:
            self.get_num_worker_func = get_num_worker_func
        
        if get_worker_names_func is not None:
            self.get_worker_names_func = get_worker_names_func
            

    @property
    def settings(self) -> SettingsT:
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
            from lazyops.libs.fastapi_utils.types.state import AppState
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
        if kind is None: kind = 'default'
        if kind not in self.worker_processes:
            self.logger.warning(f"No worker processes found for {kind}")
            return []
        if name not in self.worker_processes[kind]:
            self.logger.warning(f"No worker processes found for {kind}.{name}")
            return []
        procs = []
        for proc in self.worker_processes[kind][name]:
            if proc._closed: continue
            parent = psutil.Process(proc.pid)
            procs.extend(child.pid for child in parent.children(recursive=True))
            if first: break
        return procs
    
    def add_queue_type(self, kind: str):
        """
        Add a queue type
        """
        if kind not in self.queues:
            setattr(self, kind, {})
            self.queues[kind] = getattr(self, kind)
    
    def set_queue(self, name: str, queue: 'TaskQueue', kind: Optional[str] = None):
        """
        Set a queue
        """
        if kind is None: kind = 'default'
        if kind not in self.queues:
            self.add_queue_type(kind)
        self.queues[kind][name] = queue
    
    def add_worker_processes(self, name: str, procs: List['multiprocessing.Process'], kind: Optional[str] = None):
        """
        Adds worker processes
        """
        if kind is None: kind = 'default'
        if self.worker_processes.get(kind) is None: self.worker_processes[kind] = {}
        if self.worker_processes[kind].get(name) is None: self.worker_processes[kind][name] = []
        self.worker_processes[kind][name].extend(procs)

    def has_worker_processes(self, name: str, kind: Optional[str] = None) -> bool:
        """
        Checks if there are processes
        """
        if kind is None: kind = 'default'
        if kind not in self.worker_processes: self.worker_processes[kind] = {}
        if name not in self.worker_processes[kind]:
            self.worker_processes[kind][name] = []        
        return len(self.worker_processes[kind][name]) > 0
    
    def start_worker_processes(
        self, 
        name: str, 
        kind: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None, 
        num_workers: Optional[int] = 1, 
        verbose: Optional[bool] = True, 
        base_index: Optional[Union[int, str]] = 'auto',

        spawn_worker_func: Optional[Union[Callable, str]] = None,
        num_worker_func: Optional[Union[Callable, str]] = None,
        get_worker_func: Optional[Union[Callable, str]] = None,
        settings_config_func: Optional[Union[Callable, str]] = None,

        **kwargs
    ):  # sourcery skip: low-code-quality
        """
        Starts the worker processes
        """
        procs = []
        if kind is None: kind = 'default'
        if verbose: self.logger.info(f"[{kind.capitalize()}] Spawning Worker: {name} ({num_workers})")
        context = multiprocessing.get_context('spawn')
        if base_index == 'auto':
            from .utils import get_base_worker_index
            base_index = get_base_worker_index()
        if num_worker_func is None: num_worker_func = self.get_settings_func(self.get_num_worker_func)
        if get_worker_func is None: get_worker_func = self.get_settings_func(self.get_worker_func)
        if settings_config_func is None: 
            settings_config_func = self.get_settings_func(self.settings_config_func)
        if spawn_worker_func is None: 
            from .workers import spawn_new_worker
            spawn_worker_func = spawn_new_worker
        
        if num_worker_func:
            num_workers = num_worker_func(name = name, num_workers = num_workers, kind = kind)
        if not kwargs: kwargs = {}
        
        kwargs['kind'] = kind
        kwargs['config'] = config
        kwargs['verbose'] = verbose

        kwargs['settings_config_func'] = settings_config_func
        kwargs['get_worker_func'] = get_worker_func
        
        for n in range(num_workers):
            is_primary_worker = n == 0
            worker_index = (base_index * num_workers) + n
            kwargs['is_primary_worker'] = is_primary_worker
            kwargs['index'] = worker_index
            p = context.Process(target = spawn_worker_func, args = (name,), kwargs = kwargs)
            p.start()
            if verbose: 
                log_name = f'{name}-{worker_index}'
                self.logger.info(f"- |g|[{kind.capitalize()}]|e| Started: [ {n + 1}/{num_workers} ] `|g|{log_name:20s}|e|` (Process ID: {p.pid})", colored = True)
            procs.append(p)
        self.add_worker_processes(kind = kind, name = name, procs = procs)
        return procs
    
    def start_all_workers(
        self,
        worker_names: Optional[List[str]] = None,
        kind: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        num_workers: Optional[int] = 1,
        base_index: Optional[Union[int, str]] = 'auto',


        enabled_workers: Optional[List[str]] = None,
        disabled_workers: Optional[List[str]] = None,
        verbose: Optional[bool] = True,

        spawn_worker_func: Optional[Union[Callable, str]] = None,
        num_worker_func: Optional[Union[Callable, str]] = None,
        get_worker_func: Optional[Union[Callable, str]] = None,
        settings_config_func: Optional[Union[Callable, str]] = None,
        get_worker_names_func: Optional[Union[Callable, str]] = None,
        **kwargs
    ):  # sourcery skip: low-code-quality
        """
        Starts all the workers
        """
        procs = []
        if kind is None: kind = 'default'
        if not worker_names:
            if get_worker_names_func is None:
                get_worker_names_func = self.get_settings_func(self.get_worker_names_func)
            worker_names = get_worker_names_func(
                kind = kind,
                enabled_workers = enabled_workers,
                disabled_workers = disabled_workers,
            )
        if verbose: self.logger.info(f"[|g|{kind.capitalize()}|e|] Starting {len(worker_names)} Workers: {worker_names}", colored = True)
        context = multiprocessing.get_context('spawn')
        if base_index == 'auto': base_index = get_base_worker_index()
        if num_worker_func is None: num_worker_func = self.get_settings_func(self.get_num_worker_func)
        if get_worker_func is None: get_worker_func = self.get_settings_func(self.get_worker_func)
        if settings_config_func is None: 
            settings_config_func = self.get_settings_func(self.settings_config_func)
        if spawn_worker_func is None: 
            from .workers import spawn_new_worker
            spawn_worker_func = spawn_new_worker
        
        if not kwargs: kwargs = {}
        
        kwargs['kind'] = kind
        kwargs['config'] = config
        kwargs['verbose'] = verbose

        kwargs['settings_config_func'] = settings_config_func
        kwargs['get_worker_func'] = get_worker_func
        
        for name in worker_names:
            if num_worker_func: num_workers = num_worker_func(name = name, num_workers = num_workers, kind = kind)
            
            for n in range(num_workers):
                is_primary_worker = n == 0
                worker_index = (base_index * num_workers) + n
                kwargs['is_primary_worker'] = is_primary_worker
                kwargs['index'] = worker_index
                p = context.Process(target = spawn_new_worker, args = (name,), kwargs = kwargs)
                p.start()
                if verbose: 
                    log_name = f'`|g|{name}-{worker_index}|e|`'
                    self.logger.info(f"- [|g|{kind.capitalize():7s}|e|] Started: [ {n + 1}/{num_workers} ] {log_name:20s} (Process ID: {p.pid})", colored = True)
                if is_primary_worker:
                    self.state.add_leader_process_id(p.pid, kind)
                
                procs.append(p)
            self.add_worker_processes(kind = kind, name = name, procs = procs)
        return procs

    def stop_worker_processes(self,  name: str, verbose: bool = True, timeout: float = 5.0, kind: Optional[str] = None):
        # sourcery skip: low-code-quality
        """
        Stops the worker processes
        """
        if kind is None: kind = 'default'
        if self.worker_processes.get(kind) is None or self.worker_processes[kind].get(name) is None: 
            if verbose: self.logger.warning(f"[{kind.capitalize()}] No worker processes found for {name}")
            return
        curr_proc, n_procs = 0, len(self.worker_processes[kind][name])

        while self.worker_processes[kind][name]:
            proc = self.worker_processes[kind][name].pop()
            if proc._closed: continue
            log_name = f'`|g|{name}-{curr_proc}|e|`'
            if verbose: 
                self.logger.info(f"- [|y|{kind.capitalize():7s}|e|] Stopping: [ {curr_proc + 1}/{n_procs} ] {log_name:20s} (Process ID: {proc.pid})", colored = True)
            proc.join(timeout)
            proc.terminate()
            try:
                proc.close()
            except Exception as e:
                if verbose: self.logger.info(f"|y|[{kind.capitalize():7s}]|e| Failed Stop: [ {curr_proc + 1}/{n_procs} ] {log_name:20s} (Error: |r|{e}|e|)", colored = True)
                try:
                    signal.pthread_kill(proc.ident, signal.SIGKILL)
                    proc.join(timeout)
                    proc.terminate()
                except Exception as e:
                    if verbose: self.logger.info(f"|r|[{kind.capitalize():7s}]|e| Failed Kill: [ {curr_proc + 1}/{n_procs} ] {log_name:20s} (Error: |r|{e}|e|)", colored = True)
                with contextlib.suppress(Exception):
                    proc.kill()
                    proc.close()
            curr_proc += 1

    async def astop_worker_processes(self, name: str, verbose: bool = True, timeout: float = 5.0, kind: Optional[str] = None):
        """
        Stops the worker processes
        """
        if kind is None: kind = 'default'
        if self.worker_processes.get(kind) is None or self.worker_processes[kind].get(name) is None: 
            if verbose: self.logger.warning(f"[{kind.capitalize()}] No worker processes found for {name}")
            return
        from .workers import terminate_worker
        await terminate_worker(name = name, kind = kind)
        self.stop_worker_processes(name = name, verbose = verbose, timeout = timeout, kind = kind)
    
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
    
    def end_all_processes(self, verbose: bool = True, timeout: float = 5.0):
        """
        Terminates all processes
        """
        for kind, names in self.worker_processes.items():
            for name in names:
                self.stop_worker_processes(name = name, verbose = verbose, timeout = timeout, kind = kind)
        self.stop_server_processes(verbose = verbose, timeout = timeout)
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



GlobalContext: GlobalContextClass = ProxyObject(GlobalContextClass)
