from __future__ import annotations

"""
Postgres Backends
"""

import typing as t
from lzl import load
from lzl.types import eproperty
from lzl.logging import logger
from ..base.backend import BaseDatabaseBackend, BackendType

if load.TYPE_CHECKING:
    import psqlpy
    from psqlpy import ConnectionPool
else:
    psqlpy = load.LazyLoad("psqlpy", install_missing=True)


class PostgresBackend(BaseDatabaseBackend):
    """
    Postgres Backend
    """

    """
    [psqlpy] Connection Pool Methods
    """

    if t.TYPE_CHECKING:
        from .config import PostgresConfig
        config: PostgresConfig

    def get_pgpool(
        self,
        readonly: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
        **kwargs,
    ) -> 'ConnectionPool':
        """
        Creates a New Connection Pool
        """
        dsn = self.config.adapterless_url
        if readonly and self.config.readonly_url:
            dsn = self.config.adapterless_ro_url
        elif superuser and self.config.superuser_url:
            dsn = self.config.adapterless_superuser_url
        config = self.config.connpool.model_dump(exclude_none = True)
        config['dsn'] = dsn
        if kwargs: config.update(kwargs)
        return psqlpy.ConnectionPool(**config)
    
    @eproperty
    def pgpool(self) -> 'ConnectionPool':
        """
        Returns the Connection Pool
        """
        return self.get_pgpool()
    
    @eproperty
    def pgpool_ro(self) -> 'ConnectionPool':
        """
        [Readonly] Returns the Connection Pool
        """
        return self.get_pgpool(readonly = True)
    
    @eproperty
    def pgpool_su(self) -> 'ConnectionPool':
        """
        [Superuser] Returns the Connection Pool
        """
        return self.get_pgpool(superuser = True)


class SQLAlchemyBackend(PostgresBackend):
    """
    SQLAlchemy Backend
    """
    backend: t.Optional[BackendType] = 'sqlalchemy'


class SQLModelBackend(PostgresBackend):
    """
    SQLModel Backend
    """
    backend: t.Optional[BackendType] = 'sqlmodel'

PostgresBackendClasses = t.Union[SQLAlchemyBackend, SQLModelBackend]
PostgresBackendMap = {
    'sqlalchemy': SQLAlchemyBackend,
    'sqlmodel': SQLModelBackend,
}

