from __future__ import annotations

"""
Aggregate of all the DB Backends and Managers
"""

from typing import Optional, Dict, Any, Union, Type, TYPE_CHECKING
from .base.backend import BaseDatabaseBackend, BackendClassT
from .base.manager import DBBackendManager, DBManagerT
from .sqlite import SqliteBackendManager, SqliteBackendMap, SqliteBackendClasses
from .postgres import PostgresBackendManager, PostgresBackendMap, PostgresBackendClasses

ADAPTER_TO_BACKENDS: Dict[str, Dict[str, Type[BackendClassT]]] = {
    'postgres': PostgresBackendMap,
    'postgresql': PostgresBackendMap,
    'sqlite': SqliteBackendMap
}

ADAPTER_TO_MANAGER: Dict[str, Type[DBManagerT]] = {
    'postgres': PostgresBackendManager,
    'postgresql': PostgresBackendManager,

    'sqlite': SqliteBackendManager,
}


DATABASE_MANAGER_CLASSES = Union[DBBackendManager, SqliteBackendManager, PostgresBackendManager]
DATABASE_BACKEND_CLASSES = Union[BaseDatabaseBackend, SqliteBackendClasses, PostgresBackendClasses]