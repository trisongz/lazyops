from __future__ import annotations

"""
Postgres Manager
"""

import typing as t
from lzl.logging import logger
from ..base.manager import DBBackendManager
from .backend import BackendType, PostgresBackendClasses


class PostgresBackendManager(DBBackendManager):
    """
    Postgres Backend Manager
    """

    db_type: t.Optional[str] = 'postgres'

    if t.TYPE_CHECKING:
        import pathlib
        from .config import PostgresConfig, PostgresSettings

        def initialize_backend(
            self,
            name: t.Optional[str] = None,
            backend: t.Optional[BackendType] = None,

            settings: t.Optional[PostgresSettings] = None,
            config: t.Optional[PostgresConfig] = None,
            
            filepath: t.Optional[t.Union[str, pathlib.Path]] = None, 
            env_var: t.Optional[str] = None,

            settings_app_name: t.Optional[str] = None,
            settings_filepath: t.Optional[t.Union[str, pathlib.Path]] = None,
            settings_env_var: t.Optional[str] = None,

            overrides: t.Optional[t.Dict[str, t.Any]] = None,
            **kwargs,
        ) -> PostgresBackendClasses:
            """
            [Postgres] Initializes the backend
            """
            ...


        def configure_backend(
            self,
            name: t.Optional[str] = None,
            backend: t.Optional[BackendType] = None,

            settings: t.Optional[PostgresSettings] = None,
            config: t.Optional[PostgresConfig] = None,
            
            filepath: t.Optional[t.Union[str, pathlib.Path]] = None, 
            env_var: t.Optional[str] = None,

            settings_app_name: t.Optional[str] = None,
            settings_filepath: t.Optional[t.Union[str, pathlib.Path]] = None,
            settings_env_var: t.Optional[str] = None,

            overrides: t.Optional[t.Dict[str, t.Any]] = None,
            set_as_current: t.Optional[bool] = None,
            **kwargs,
        ) -> PostgresBackendClasses:
            """
            [Postgres] Configures the backend
            """
            ...

        @property
        def bkend(self) -> 'PostgresBackendClasses':
            """
            Returns the backend
            """
            ...