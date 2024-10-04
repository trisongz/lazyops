from __future__ import annotations

"""
Sqlite Backends
"""

import typing as t
from lzl.logging import logger
from ..base.backend import BaseDatabaseBackend, BackendType

class SqliteBackend(BaseDatabaseBackend):
    """
    Sqlite Backend
    """

    if t.TYPE_CHECKING:
        from .config import SqliteConfig
        config: SqliteConfig

    def index_exists(
        self,
        index_name: str,
    ) -> bool:
        """
        [Sqlite] Checks if the Index Exists
        """
        statement = self.sql.text(
            """
            SELECT EXISTS (
                SELECT FROM sqlite_master WHERE type = 'index' AND name = :index_name
            );
            """
        )
        return self._execute_scalar(statement, {'index_name': index_name})
    
    async def aindex_exists(
        self,
        index_name: str,
    ) -> bool:
        """
        [Sqlite] Checks if the Index Exists
        """
        statement = self.sql.text(
            """
            SELECT EXISTS (
                SELECT FROM sqlite_master WHERE type = 'index' AND name = :index_name
            );
            """
        )
        return await self._aexecute_scalar(statement, {'index_name': index_name})

    def database_exists(
        self,
        db_name: str,
        verbose: t.Optional[bool] = True,
    ) -> bool:
        """
        [Sqlite] Checks if the database exists
        """
        statement = self.sql.text(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :db_name;"
        )
        result = self._execute_scalar(statement, {'db_name': db_name})
        if verbose: logger.info(f'Database {db_name} Exists: {result}')
        return result
        
    async def adatabase_exists(
        self,
        db_name: str,
        verbose: t.Optional[bool] = True,
    ) -> bool:
        """
        [Sqlite] Checks if the database exists
        """
        statement = self.sql.text(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :db_name;"
        )
        result = await self._aexecute_scalar(statement, {'db_name': db_name})
        if verbose: logger.info(f'Database {db_name} Exists: {result}')
        return result

    def get_table_column_size(
        self,
        table: str,
        column: str,
        schema: t.Optional[str] = None,
        verbose: t.Optional[bool] = False,
    ) -> t.Dict[str, t.Union[str, float]]:
        """
        [Sqlite] Returns the table column size
        """
        pass

    def get_table_column_names(
        self,
        table: str,
        schema: t.Optional[str] = None,
    ) -> t.List[str]:
        """
        [Sqlite] Returns the table column names
        """
        pass


class SQLAlchemyBackend(SqliteBackend):
    """
    SQLAlchemy Backend
    """
    backend: t.Optional[BackendType] = 'sqlalchemy'


class SQLModelBackend(SqliteBackend):
    """
    SQLModel Backend
    """
    backend: t.Optional[BackendType] = 'sqlmodel'

SqliteBackendClasses = t.Union[SQLAlchemyBackend, SQLModelBackend]
SqliteBackendMap = {
    'sqlalchemy': SQLAlchemyBackend,
    'sqlmodel': SQLModelBackend,
}

