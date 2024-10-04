from __future__ import annotations

"""
Postgres Configuration
"""

from ..base.config import (
    PostgresDsn,
    BaseDBConfig,
    BaseDBSettings,
    DatabaseConfig,
)
from lzl.types import eproperty
import typing as t

class BasePostgresConfig(BaseDBConfig):
    """
    The Base Postgres Config
    """
    url: t.Optional[PostgresDsn] = None
    readonly_url: t.Optional[PostgresDsn] = None
    superuser_url: t.Optional[PostgresDsn] = None

    @classmethod
    def get_adapter_prefix(cls) -> str:
        """
        Returns the adapter prefix
        """
        return 'postgresql'
    
    @eproperty
    def cli_connect_string(self) -> str:
        """
        Returns the cli connect string

        export PGPASSWORD=<password> psql -h <host> -p <port> -U <user> -d <database>
        """
        url = self.superuser_url or self.url
        url_data = url.hosts()[0]
        return f"export PGPASSWORD={url_data['password']} psql -h {url_data['host']} -p {url_data['port']} -U {url_data['username']} -d {url.path[1:]}"

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
        if superuser: url = self.superuser_url
        elif readonly: url = self.readonly_url
        else: url = self.url
        assert url, 'URL must be provided'
        url_data = url.hosts()[0]
        db = database or url.path[1:]
        return f"export PGPASSWORD={url_data['password']} psql -h {url_data['host']} -p {url_data['port']} -U {url_data['username']} -d {db}"
    
    def get_cli_debug_args(self) -> str:
        """
        Returns the cli debug args
        """
        return ' -v ON_ERROR_STOP=1 -a -b -e -E'
    
    def get_cli_safe_cmd(self, cmd: str) -> str:
        """
        Returns the cli safe cmd
        """
        return cmd.split("psql", 1)[-1]


class PostgresSettings(BasePostgresConfig, BaseDBSettings):
    """
    The Postgres Settings
    """

    class Config:
        env_prefix = "POSTGRES_"
        case_sensitive = False


class PostgresConfig(BasePostgresConfig, DatabaseConfig):
    """
    The Postgres Config
    """
    pass



