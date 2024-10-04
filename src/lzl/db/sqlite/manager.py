from __future__ import annotations

"""
Sqlite Manager
"""

import typing as t
from lzl.logging import logger
from ..base.manager import DBBackendManager
from .backend import BackendType, SqliteBackendClasses


class SqliteBackendManager(DBBackendManager):
    """
    Sqlite Backend Manager
    """

    db_type: t.Optional[str] = 'sqlite'

    if t.TYPE_CHECKING:
        import pathlib
        from .config import SqliteConfig, SqliteSettings

        def initialize_backend(
            self,
            name: t.Optional[str] = None,
            backend: t.Optional[BackendType] = None,

            settings: t.Optional[SqliteSettings] = None,
            config: t.Optional[SqliteConfig] = None,
            
            filepath: t.Optional[t.Union[str, pathlib.Path]] = None, 
            env_var: t.Optional[str] = None,

            settings_app_name: t.Optional[str] = None,
            settings_filepath: t.Optional[t.Union[str, pathlib.Path]] = None,
            settings_env_var: t.Optional[str] = None,

            overrides: t.Optional[t.Dict[str, t.Any]] = None,
            **kwargs,
        ) -> SqliteBackendClasses:
            """
            [Sqlite] Initializes the backend
            """
            ...


        def configure_backend(
            self,
            name: t.Optional[str] = None,
            backend: t.Optional[BackendType] = None,

            settings: t.Optional[SqliteSettings] = None,
            config: t.Optional[SqliteConfig] = None,
            
            filepath: t.Optional[t.Union[str, pathlib.Path]] = None, 
            env_var: t.Optional[str] = None,

            settings_app_name: t.Optional[str] = None,
            settings_filepath: t.Optional[t.Union[str, pathlib.Path]] = None,
            settings_env_var: t.Optional[str] = None,

            overrides: t.Optional[t.Dict[str, t.Any]] = None,
            set_as_current: t.Optional[bool] = None,
            **kwargs,
        ) -> SqliteBackendClasses:
            """
            [Sqlite] Configures the backend
            """
            ...

        @property
        def bkend(self) -> 'SqliteBackendClasses':
            """
            Returns the backend
            """
            ...