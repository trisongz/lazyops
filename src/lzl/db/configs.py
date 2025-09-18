from __future__ import annotations

"""Adapter-specific configuration registries for LazyOps databases."""

import typing as t
from .base.config import BaseDBConfig, BaseDBSettings, DBConfigT, DBSettingsT
# from .pg.config import PostgresConfig, PostgresSettings
from .postgres.config import PostgresConfig, PostgresSettings
from .sqlite.config import SqliteConfig, SqliteSettings

ADAPTER_TO_CONFIG: t.Dict[str, t.Type[DBConfigT]] = {
    'postgres': PostgresConfig,
    'postgresql': PostgresConfig,

    'sqlite': SqliteConfig,
}
ADAPTER_TO_SETTINGS: t.Dict[str, t.Type[DBSettingsT]] = {
    'postgres': PostgresSettings,
    'postgresql': PostgresSettings,

    'sqlite': SqliteSettings,
}

DATABASE_CONFIG_CLASSES = t.Union[PostgresConfig, SqliteConfig]

__all__ = [
    "ADAPTER_TO_CONFIG",
    "ADAPTER_TO_SETTINGS",
    "DATABASE_CONFIG_CLASSES",
]
