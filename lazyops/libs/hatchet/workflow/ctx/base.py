from __future__ import annotations

"""
Base Workflow Context Object
"""

import abc
import tracemalloc
import contextlib
from .utils import capture_state, display_top
from typing import Any, Dict, List, Optional, TypeVar, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from kvdb import PersistentDict, AsyncLock, KVDBSession
    from lazyops.utils.logs import Logger
    from lazyops.libs.abcs.types.persistence import TemporaryData
    from lazyops.libs.hatchet.session import HatchetSession
    from lazyops.libs.hatchet.context import Context
    from ..base import WorkflowT


class BaseWorkflowContext(abc.ABC):
    """
    Base class for all Workflow Context
    """
    _extra: Dict[str, Any] = {}
    _clients: Optional[Dict[str, Any]] = {}
    _pdicts: Dict[str, 'PersistentDict'] = {}

    def __init__(
        self, 
        workflow: 'WorkflowT',
        **kwargs,
    ):
        """
        Initializes the Workflow Context Component
        """
        self.workflow = workflow
        self.hatchet_settings = workflow.hatchet_settings
        self.workflow_name = workflow.workflow_name
        self.hatchet = workflow.hatchet
        self.name = 'workflow'
        self.instance = workflow.instance
        # self.name = workflow.name

        self.configure_init(**kwargs)
        self.configure_pre_init(**kwargs)
        self.configure_post_init(**kwargs)

    @property
    def trace_started(self) -> bool:
        """
        Returns whether or not the trace started
        """
        if 'trace_started' not in self._extra:
            self._extra['trace_started'] = False
        return self._extra['trace_started']

    @trace_started.setter
    def trace_started(self, value: bool):
        """
        Sets the trace started
        """
        self._extra['trace_started'] = value

    @property
    def logger(self) -> 'Logger':
        """
        Gets the logger
        """
        return self.hatchet_settings.logger
    
    @property
    def autologger(self) -> 'Logger':
        """
        Gets the autologger
        """
        return self.hatchet_settings.autologger

    def configure_init(self, *args, **kwargs):
        """
        Configure the Workerflow Component
        """
        pass

    def configure_pre_init(self, *args, **kwargs):
        """
        Configure the Workerflow Component
        """
        pass

    def configure_post_init(self, *args, **kwargs):
        """
        Post Configure the Workerflow Component
        """
        pass

    def get_process_state(self, prefix: Optional[str] = None, as_str: bool = True) -> Union[str, Dict[str, Any]]:
        """
        Captures the state of the process
        """
        if prefix: prefix = f'[{prefix}] '
        return capture_state(as_str = as_str, prefix = prefix, in_k8s = self.hatchet_settings.in_k8s)

    def get_trace_state(self, prefix: str = 'Start', limit: int = 3) -> Optional[str]:
        """
        Gets the trace state
        """
        if prefix == 'Start': 
            if not self.trace_started:
                with contextlib.suppress(Exception):
                    tracemalloc.start()
                self.trace_started = True
            return
        s = display_top(tracemalloc.take_snapshot(), limit = limit)
        s = f'[{prefix}] {s}'
        return s


    @property
    def hatchet(self) -> 'HatchetSession':
        """
        Gets the Hatchet Client
        """
        self._set_client('hatchet')
        return self._clients['hatchet']
    
    @hatchet.setter
    def hatchet(self, value: 'HatchetSession'):
        """
        Sets the Hatchet Client
        """
        self._clients['hatchet'] = value
        if not self.instance: self.instance = value.instance


    async def on_workflow_error(self, context: 'Context', e: Exception, **kwargs):
        """
        Handles the workflow error
        """
        pass


    @contextlib.asynccontextmanager
    async def catch_workflow_error(
        self,
        context: 'Context',
        **kwargs,
    ):
        """
        Catches the workflow error and stores it in the cache
        """
        try:
            yield
        except Exception as e:
            await self.on_workflow_error(context, e)
            raise e
    

    def _set_client(self, name: str, key: Optional[str] = None) -> None:
        """
        Sets the client
        """
        key = key or name
        if key not in self._clients: self._clients[key] = self._get_client(name)

    def _get_client(self, name: str) -> Any:
        """
        Gets a client
        """
        raise NotImplementedError

    def _import(self, name: str) -> Any:
        """
        Imports a module
        """
        from lazyops.utils.lazy import lazy_import
        return lazy_import(name)
    
    def _get_kdb_session(self, name: str, **kwargs) -> 'KVDBSession':
        """
        Gets a KVDB Session
        """
        from kvdb import KVDBClient
        return KVDBClient.get_session(name = name, **kwargs)
    

    def _get_pdict(self, base_key: str, **kwargs) -> 'PersistentDict':
        """
        Gets a Persistent Dict
        """
        return self.pkdb.create_persistence(base_key = base_key, **kwargs)

    @property
    def kdb(self) -> 'KVDBSession':
        """
        Gets the KVDB Session
        """
        if 'kdb' not in self._clients:
            self._clients['kdb'] = self._get_kdb_session('workflow', serializer = 'json')
        return self._clients['kdb']

    @property
    def rkdb(self) -> 'KVDBSession':
        """
        Gets the Raw KVDB Session with Decoder Enabled
        """
        if 'rkvdb' not in self._clients:
            self._clients['rkvdb'] = self._get_kdb_session('workflow-raw', serializer = None, decode_responses = True)
        return self._clients['rkvdb']
    
    @property
    def pkdb(self) -> 'KVDBSession':
        """
        Gets the KVDB Session with no serialization for Persistence
        """
        if 'pkdb' not in self._clients:
            self._clients['pkdb'] = self._get_kdb_session('persistence', serializer = None)
        return self._clients['pkdb']

    @property
    def tmp_data(self) -> 'TemporaryData':
        """
        Gets the Temporary Data
        """
        return self.hatchet_settings.temp_data