from __future__ import annotations

"""
Proxied Client
"""
import json
import asyncio
import contextlib
from lazyops.types.lazydict import LazyDict
from lazyops.utils.times import Timer
from lazyops.utils.logs import Logger
from lazyops.utils.helpers import create_timestamp, adeferred_task
from lazyops.utils.pooler import ThreadPooler
from proposalflow.utils.logs import logger, null_logger
from typing import Any, Dict, List, Optional, Type, TypeVar, Tuple, Union, Set, TYPE_CHECKING


if TYPE_CHECKING:
    from kvdb import KVDBSession, PersistentDict
    from lazyops.libs.logging import Logger
    from lazyops.libs.abcs.configs.base import AppSettings
    from lazyops.libs.abcs.types.api import BaseSchema
    from lazyops.libs.abcs.clients import ClientTypes
    from lazyops.utils.pooler import ThreadPooler, ThreadPool

class BaseProxyClient(LazyDict):
    """
    A Proxy Dictionary that lazily defers initialization of the 
    clients until they are called
    """
    name: Optional[str] = "proxy"
    kind: Optional[str] = "client"

    exclude_schema_attrs: Optional[bool] = True
    proxy_schema: Optional[Dict[str, str]] = None

    def __init__(self, **kwargs):
        """
        Handles the initialization of the proxy
        """
        self._dict = {}
        self.excluded_attrs = []
        self.excluded_attrs.extend(iter(dir(self)))
        if self.proxy_schema is None:
            self.proxy_schema = self.settings.ctx.get_client_registry_mapping()
        # if self.proxy_schema is not None:
        self.excluded_attrs.extend(self.proxy_schema.keys())
        self.excluded_attrs = list(set(self.excluded_attrs))
        self.logger.info(f"Initialized {self.name} Proxy Client: {self.excluded_attrs}")
        self.post_init(**kwargs)

    def post_init(self, **kwargs):
        """
        Post Initialization to be overwritten by the subclass
        """
        pass
    
    def get_or_init(self, name: str, default: Any = None) -> 'ClientTypes':
        """
        Gets the component
        """
        if name not in self._dict and name not in self.proxy_schema:
            raise ValueError(f"Invalid component {name} for {self.name}.{self.kind}")
        if name not in self._dict:
            self._dict[name] = self.settings.ctx.get_client(
                name = name,
            )
        return self._dict[name]


    @property
    def logger(self) -> 'Logger':
        """
        Gets the logger
        """
        return self.settings.logger
    
    @property
    def null_logger(self) -> 'Logger':
        """
        Gets the null logger
        """
        return self.settings.null_logger
    

    @property
    def autologger(self) -> 'Logger':
        """
        Automatic Logger that is enabled in devel mode
        """
        return self.settings.autologger

    
    @property
    def settings(self) -> 'AppSettings':
        """
        Gets the settings
        """
        if self._settings is None:
            from lazyops.libs.abcs.configs.lazy import get_module_settings
            self._settings = get_module_settings(self.__module__.__name__)
        return self._settings

    @property
    def kdb(self) -> 'KVDBSession':
        """
        Gets the keydb
        """
        if self._kdb is None:
            self._kdb = self.settings.ctx.get_kdb_session(self.name)
        return self._kdb
    
    @property
    def pooler(self) -> 'ThreadPool':
        """
        Gets the pooler
        """
        if self._pooler is None:
            from lazyops.libs.pooler import ThreadPooler
            self._pooler = ThreadPooler
        return self._pooler
    
    