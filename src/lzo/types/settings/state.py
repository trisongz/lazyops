from __future__ import annotations

"""
The Application State
"""
import os
import abc
import atexit
import contextlib
import pathlib
from lzl.logging import logger
from lzl.types import BaseModel, Field
from typing import Optional, Dict, Any, List, Union, Generator, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from lzo.types.base import RegisteredSettings as BaseSettings
    from lzl.io import TemporaryData as StateData


class AppState(BaseModel):
    """
    Holds the state of the current settings
    """
    configured: Set[str] = Field(default_factory=set)
    initialized: Set[str] = Field(default_factory=set)
    completed: bool = False

    app_entrypoint: Optional[str] = None
    worker_entrypoint: Optional[str] = None

    k8s_kubeconfigs: Optional[Dict[str, str]] = Field(default_factory=dict)
    k8s_active_ctx: Optional[str] = None

    app_module_name: Optional[str] = None
    data_path: Optional[pathlib.Path] = None
    
    ctx: Optional[Dict[str, Any]] = {}


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
            from lzo.utils.system import get_local_kubeconfig
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
        if hasattr(settings, 'data_path'):
            self.data_path = settings.data_path
        else:
            from lzo.utils.assets import get_module_path
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
            from lzl.io.persistence import TemporaryData as StateData
            stx = StateData(filepath = stx_filepath)
            self.ctx['stx'] = stx
            atexit.register(self.on_exit)

    def set_primary_process_id(self, process_id: int):
        # sourcery skip: class-extract-method
        """
        Sets the primary process id
        """
        self.stx['primary_process_id'] = process_id
    
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

    def has_logged(self, key: str) -> bool:
        """
        Returns whether the key has been logged
        """
        return self.stx.append('logged', key)
        