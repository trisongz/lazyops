from __future__ import annotations

"""
RQLite Backend Dict-Like Persistence
"""

import copy
import typing as t
from lzl import load
from pydantic.networks import HttpUrl
from .sqlite.db import SqliteDB, Optimization
from .sqlite.main import SqliteStatefulBackend

if load.TYPE_CHECKING:
    import pyrqlite.dbapi2
    from pyrqlite.dbapi2 import Connection
else:
    pyrqlite = load.LazyLoad("pyrqlite")


class RqliteDB(SqliteDB):
    """
    The RqliteDB
    """
    _db_kind: t.Optional[str] = 'RQLite'
    
    def __init__(
        self, 
        conn_uri: t.Union[str, HttpUrl],
        table: str, 
        optimization: t.Optional[Optimization] = None, 
        timeout: t.Optional[float] = None,
        is_remote: t.Optional[bool] = True,
        **kwargs
    ):
        """
        Initializes the Rqlite Database
        """
        if t.TYPE_CHECKING:
            self.conn_uri: HttpUrl
        if isinstance(conn_uri, str): conn_uri = HttpUrl(conn_uri)
        super().__init__(
            conn_uri = conn_uri,
            table = table,
            optimization = optimization,
            timeout = timeout,
            is_remote = is_remote,
            **kwargs
        )


    def _get_io_(self, timeout: t.Optional[float] = None) -> 'Connection':
        """
        Returns the IO Connection
        """
        new = pyrqlite.dbapi2.Connection(
            host = self.conn_uri.host,
            port = self.conn_uri.port,
            user = self.conn_uri.username,
            password = self.conn_uri.password,
            scheme = self.conn_uri.scheme,
            timeout = timeout or (self.timeout if self.configured else 0.0),
        )
        self._spawned['io'].append(new)
        return new
    
