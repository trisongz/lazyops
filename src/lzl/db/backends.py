from __future__ import annotations

"""Convenience registries that map adapters to backend implementations."""

import typing as t

from .base.backend import BaseDatabaseBackend, BackendClassT
from .base.manager import DBBackendManager, DBManagerT
from .postgres import PostgresBackendManager, PostgresBackendMap, PostgresBackendClasses
from .sqlite import SqliteBackendManager, SqliteBackendMap, SqliteBackendClasses

ADAPTER_TO_BACKENDS: t.Dict[str, t.Dict[str, t.Type[BackendClassT]]] = {
    'postgres': PostgresBackendMap,
    'postgresql': PostgresBackendMap,
    'sqlite': SqliteBackendMap,
}

ADAPTER_TO_MANAGER: t.Dict[str, t.Type[DBManagerT]] = {
    'postgres': PostgresBackendManager,
    'postgresql': PostgresBackendManager,
    'sqlite': SqliteBackendManager,
}

DATABASE_MANAGER_CLASSES = t.Union[DBBackendManager, SqliteBackendManager, PostgresBackendManager]
DATABASE_BACKEND_CLASSES = t.Union[BaseDatabaseBackend, SqliteBackendClasses, PostgresBackendClasses]

__all__ = [
    "ADAPTER_TO_BACKENDS",
    "ADAPTER_TO_MANAGER",
    "DATABASE_MANAGER_CLASSES",
    "DATABASE_BACKEND_CLASSES",
]
