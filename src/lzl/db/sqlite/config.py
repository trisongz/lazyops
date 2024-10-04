from __future__ import annotations

"""
Sqlite Configuration
"""

from ..base.config import (
    SqliteDsn,
    BaseDBConfig,
    BaseDBSettings,
    DatabaseConfig,
)
from lzl.types import eproperty
import typing as t

class BaseSqliteConfig(BaseDBConfig):
    """
    The Base Sqlite Config
    """
    url: t.Optional[SqliteDsn] = None
    readonly_url: t.Optional[SqliteDsn] = None
    superuser_url: t.Optional[SqliteDsn] = None


    @classmethod
    def get_adapter_prefix(cls) -> str:
        """
        Returns the adapter prefix
        """
        return 'sqlite'
    

    @eproperty
    def cli_connect_string(self) -> str:
        """
        Returns the cli connect string

        export PGPASSWORD=<password> psql -h <host> -p <port> -U <user> -d <database>
        """
        raise NotImplementedError
    

    def get_cli_connect_string(
        self,
        superuser: t.Optional[bool] = None,
        readonly: t.Optional[bool] = None,
        database: t.Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Returns the cli connect string
        """
        raise NotImplementedError
    
    def get_cli_debug_args(self) -> str:
        """
        Returns the cli debug args
        """
        return ''
    
    def get_cli_safe_cmd(self, cmd: str) -> str:
        """
        Returns the cli safe cmd
        """
        raise NotImplementedError


class SqliteSettings(BaseSqliteConfig, BaseDBSettings):
    """
    The Sqlite Settings
    """

    class Config:
        env_prefix = "SQLITE_"
        case_sensitive = False


class SqliteConfig(BaseSqliteConfig, DatabaseConfig):
    """
    The Sqlite Config
    """
    pass



