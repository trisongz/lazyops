from __future__ import annotations

"""
Aggregate of all the DB Configs
"""

from typing import Optional, Dict, Any, Union, Type, TYPE_CHECKING
from .base.config import BaseDBConfig, BaseDBSettings, DBConfigT, DBSettingsT
# from .pg.config import PostgresConfig, PostgresSettings
from .postgres.config import PostgresConfig, PostgresSettings
from .sqlite.config import SqliteConfig, SqliteSettings

ADAPTER_TO_CONFIG: Dict[str, Type[DBConfigT]] = {
    'postgres': PostgresConfig,
    'postgresql': PostgresConfig,

    'sqlite': SqliteConfig,
}
ADAPTER_TO_SETTINGS: Dict[str, Type[DBSettingsT]] = {
    'postgres': PostgresSettings,
    'postgresql': PostgresSettings,

    'sqlite': SqliteSettings,
}

DATABASE_CONFIG_CLASSES = Union[PostgresConfig, SqliteConfig]