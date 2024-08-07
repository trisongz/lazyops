from __future__ import annotations


"""
Migrated from lazyops.libs.fastapi_utils.types.state
"""

import os
import abc
import atexit

import pathlib
import filelock
import contextlib
from lazyops.types import BaseModel, Field
from lazyops.utils.logs import logger
from lazyops.utils.serialization import Json
from typing import Optional, Dict, Any, Set, List, Union, Generator, Any, TYPE_CHECKING


if TYPE_CHECKING:
    from fastapi import FastAPI
    from lazyops.types.models import BaseSettings

# 3.12.4 -> 3.13.1
class StateData(abc.ABC):

    def __init__(self, filepath: Union[str, pathlib.Path], timeout: Optional[int] = 10):
        self.filepath = pathlib.Path(filepath)
        self.filelock_path = filepath.with_suffix('.lock')
        self.timeout = timeout
        self._filelock: Optional[filelock.SoftFileLock] = None

    @property
    def filelock(self) -> filelock.SoftFileLock:
        """
        Returns the filelock
        """
        if self._filelock is None:
            try:
                self._filelock = filelock.SoftFileLock(
                    self.filelock_path.as_posix(), 
                    timeout = self.timeout,
                    thread_local = False
                )
                with self._filelock.acquire():
                    if not self.filepath.exists():
                        self.filepath.write_text('{}')
            except Exception as e:
                from lazyops.libs.logging import logger
                logger.trace(f'Error creating filelock for {self.filepath}', e)
                raise e
        return self._filelock


    def _load_data(self) -> Dict[str, Any]:
        """
        Loads the data
        """
        # if not self.filepath.exists():
        #     self.filepath.write_text('{}')
        return Json.loads(self.filepath.read_text())

    @property
    def data(self) -> Dict[str, Any]:
        """
        Returns the data
        """
        try:
            with self.filelock.acquire():
                return self._load_data()
        except filelock.Timeout as e:
            from lazyops.libs.logging import logger
            logger.trace(f'Filelock timeout for {self.filepath}')
            raise e
        
    @contextlib.contextmanager
    def ctx(self) -> Generator[Dict[str, Union[List[Any], Dict[str, Any], Any]], None, None]:
        """
        Returns the context
        """
        try:
            with self.filelock.acquire():
                data = self._load_data()
                try:
                    yield data
                finally:
                    self.filepath.write_text(Json.dumps(data, indent = 2))
        except filelock.Timeout as e:
            from lazyops.libs.logging import logger
            logger.trace(f'Filelock timeout for {self.filepath}')
            raise e
    
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Returns the value for the given key
        """
        return self.data.get(key, default)
    
    def __contains__(self, key: str) -> bool:
        """
        Returns whether the key is in the data
        """
        return key in self.data
    
    def __getitem__(self, key: str) -> Any:
        """
        Returns the value for the given key
        """
        return self.data.get(key)
    
    def __setitem__(self, key: str, value: Any):
        """
        Sets the value for the given key
        """
        with self.ctx() as data:
            data[key] = value

    def __delitem__(self, key: str):
        """
        Deletes the value for the given key
        """
        with self.ctx() as data:
            del data[key]


    def __iter__(self):
        """
        Returns the iterator
        """
        return iter(self.data)
    
    def __len__(self) -> int:
        """
        Returns the length
        """
        return len(self.data)
    
    def __repr__(self) -> str:
        """
        Returns the representation
        """
        return repr(self.data)
    
    def __str__(self) -> str:
        """
        Returns the string representation
        """
        return str(self.data)
    
    def __bool__(self) -> bool:
        """
        Returns whether the data is empty
        """
        return bool(self.data)
    
    def __eq__(self, other: Any) -> bool:
        """
        Returns whether the data is equal to the other
        """
        return self.data == other
    
    def keys(self) -> Set[str]:
        """
        Returns the keys
        """
        return self.data.keys()
    
    def setdefault(self, key: str, default: Any) -> Any:
        """
        Sets the default value for the given key
        """
        with self.ctx() as data:
            value = data.setdefault(key, default)
        return value
        
    def close(self):
        """
        Closes the filelock
        """
        self.filelock.release()

    def append(self, key: str, value: Any) -> bool:
        """
        Appends the value to the list
        """
        with self.ctx() as data:
            if key not in data:
                data[key] = []
            if value not in data[key]:
                data[key].append(value)
                return False
        return True


StateData.register(dict)


class AppState(BaseModel):
    """
    Holds the state of the current settings
    """
    configured: Set[str] = Field(default_factory=set)
    initialized: Set[str] = Field(default_factory=set)
    completed: bool = False

    if TYPE_CHECKING:
        api_app: Optional["FastAPI"] = None
    else:
        api_app: Optional[Any] = None

    ctx: Optional[Dict[str, Any]] = {}

    app_entrypoint: Optional[str] = None
    worker_entrypoint: Optional[str] = None

    k8s_kubeconfigs: Optional[Dict[str, str]] = Field(default_factory=dict)
    k8s_active_ctx: Optional[str] = None

    app_module_name: Optional[str] = None
    data_path: Optional[pathlib.Path] = None

    class Config:
        extra = 'allow'
        arbitrary_types_allowed = True

    @property
    def is_silent(self) -> bool:
        """
        Returns whether the current state is silent
        """
        return self.ctx.get('silent', False)
    
    @property
    def settings(self) -> 'BaseSettings':
        """
        Returns the settings
        """
        return self.ctx.get('settings', None)

    @property
    def stx(self) -> Optional['StateData']:
        """
        Returns the StateData
        """
        return self.ctx.get('stx', None)

    @property
    def process_id(self) -> Optional[int]:
        """
        Returns the process id
        """
        return self.ctx.get('process_id', None)
    
    @property
    def is_primary_process(self) -> bool:
        """
        Returns whether this is the primary process
        """
        return self.process_id == self.stx.get('primary_process_id', 0)
    
    @property
    def is_primary_server_process(self) -> bool:
        """
        Returns whether this is the primary server process
        """
        return self.process_id == self.stx.get('primary_server_process_id', 0)

    @property
    def is_leader_process(self) -> bool:
        """
        Returns whether this is the leader process
        """
        return self.process_id in self.stx.get('leader_process_ids', []) or self.is_primary_process

    
    @property
    def server_process_id_path(self) -> pathlib.Path:
        """
        Returns the server process id path
        """
        return self.data_path.joinpath(f'{self.app_module_name}.pid')

    def configure_silent(self, _silent: Optional[bool] = None):
        """
        Configures the silent mode
        """
        if _silent is not None:
            self.ctx['silent'] = _silent

    def get_kubeconfig(
        self, 
        name: Optional[str] = None, 
        set_as_envval: Optional[bool] = True,
        set_active: Optional[bool] = False,
    ) -> str:
        """
        Returns the kubeconfig for the given context
        """
        name = name or self.k8s_active_ctx
        if name is not None and name in self.k8s_kubeconfigs:
            kconfig = self.k8s_kubeconfigs[name]
        else:
            from lazyops.utils.system import get_local_kubeconfig
            kconfig = get_local_kubeconfig(name = name, set_as_envval = False)
            if not name: name = pathlib.Path(kconfig).stem
            self.k8s_kubeconfigs[name] = kconfig
        if set_as_envval: os.environ['KUBECONFIG'] = kconfig
        if not self.k8s_active_ctx or set_active: self.k8s_active_ctx = name
        return kconfig

    def bind_settings(self, settings: 'BaseSettings'):
        """
        Binds the settings to this state
        """
        # puts it in here so that we avoid type checking at the module level.
        self.ctx['settings'] = settings
        self.ctx['process_id'] = os.getpid()
        if hasattr(settings, 'app_module_name'):
            self.app_module_name = settings.app_module_name
        else:
            self.app_module_name = settings.__class__.__module__.split(".")[0]
            # settings.app_module_name = settings.__class__.__module__.split(".")[0]
        if hasattr(settings, 'data_path'):
            self.data_path = settings.data_path
        else:
            from lazyops.utils.assets import get_module_path
            module_path = get_module_path(self.app_module_name)
            self.data_path = module_path.joinpath('.data')
        
        self.configure_stx()
    
    def on_exit(self):
        """
        Called on exit
        """
        if 'stx' in self.ctx and self.process_id == self.stx['primary_process_id']:
            logger.info(f"Removing AppState File: {self.ctx['stx_filepath']}", colored = True, prefix = f"|r|State: {self.app_module_name}|e|")
            with contextlib.suppress(FileNotFoundError):
                self.stx.close()
                os.unlink(self.ctx['stx_filepath'])
                os.unlink(self.stx.filelock_path.as_posix())


    def configure_stx(self):
        """
        Configures the stateful statefuldata
        """
        if 'stx' not in self.ctx:
            stx_filepath = self.data_path.joinpath(f'{self.app_module_name}.state.json')
            self.ctx['stx_filepath'] = stx_filepath.as_posix()
            stx = StateData(filepath = stx_filepath)
            self.ctx['stx'] = stx
            atexit.register(self.on_exit)

    def set_primary_process_id(self, process_id: int):
        # sourcery skip: class-extract-method
        """
        Sets the primary process id
        """
        self.stx['primary_process_id'] = process_id
        # logger.info(f"Primary Process ID: {process_id}", colored = True, prefix = "|g|State|e|")
    
    def set_primary_server_process_id(self, process_id: Optional[int] = None):
        """
        Sets the primary server process id
        """
        # Try to find it
        if 'primary_server_process_id' in self.stx.keys(): return
        if process_id is None and self.server_process_id_path.exists():
            with contextlib.suppress(Exception):
                process_id = int(self.server_process_id_path.read_text())
        if process_id is None:
            return
        
        self.stx['primary_server_process_id'] = process_id
        logger.info(f"Primary Server Process ID: {process_id}", colored = True, prefix = "|g|State|e|")
    
    def add_leader_process_id(self, process_id: int, kind: Optional[str] = None):
        """
        Adds a leader process id
        """
        self.stx.append('leader_process_ids', process_id)
        # logger.info(f"Leader Process ID: {process_id} ({kind})", colored = True, prefix = "|g|State|e|")

    def has_logged(self, key: str) -> bool:
        """
        Returns whether the key has been logged
        """
        return self.stx.append('logged', key)
        