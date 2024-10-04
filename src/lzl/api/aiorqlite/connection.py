from __future__ import annotations

import time
import secrets
import typing as t
from pydantic.networks import AnyHttpUrl
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    TypeVar,
    Union,
    Protocol,
    cast,
)

from . import logging

# import requests
from .cursor import Cursor
from .result import ResultItem
from .utils import parse_host
from .client import ConnectionClient, ConnURL

class SyncWritableIO(Protocol):
    def write(self, data: bytes, /) -> Any:
        ...


class AsyncWritableIO(Protocol):
    async def write(self, data: bytes, /) -> Any:
        ...


T = TypeVar("T")


class Connection:
    """Describes a synchronous description of a pool of nodes which
    make up a rqlite cluster. There is no actual connection in this
    class, however the name is chosed to signify its similarity to
    a Connection in a DBAPI 2.0 style api.
    """

    def __init__(
        self,
        hosts: Union[Union[str, AnyHttpUrl], List[Union[str, AnyHttpUrl]]],
        timeout: int = 5,
        max_redirects: int = 2,
        max_attempts_per_host: int = 2,
        read_consistency: Literal["none", "weak", "strong"] = "weak",
        freshness: str = "0",
        log: Union[logging.LogConfig, bool] = True,
        default_mode: Literal["sync", "async"] = "sync",
    ):
        """Initializes a new synchronous Connection. This is typically
        called with the alias rqlite.connect

        Args:
            hosts (list[str]): A list of hostnames or ip addresses where
                the rqlite cluster is running. Each address can be a
                host:port pair - if the port is omitted, the default
                port of 4001 is used. If the host is specified in ipv6
                format, then it should be surrounded in square brackets
                if the port is specified, i.e., [::1]:4001.

            timeout (int): The number of seconds to wait for a response
                from a host before giving up.

            max_redirects (int): The maximum number of redirects to follow
                when executing a query.

            max_attempts_per_host (int): The maximum number of attempts to
                make to a given host before giving up.

            read_consistency (str): The read consistency to use for cursors
                by default.

            freshness (str): Default freshness value for none-consistency reads.
                Guarrantees the response is no more stale than the given duration,
                specified as a golang Duration string, e.g., "5m" for 5 minutes

            log (bool or LogConfig): If True, logs will have the default settings.
                If False, logs will be disabled. If a LogConfig, the
                configuration of the logs.

            default_mode (Literal["sync", "async"]): The default mode to use for
        """
        if log is True:
            log_config = logging.LogConfig()
        elif log is False:
            log_config = logging.DISABLED_LOG_CONFIG
        else:
            log_config = log

        # self.hosts: List[Tuple[str, int]] = [parse_host(h) for h in hosts]
        if not isinstance(hosts, list): hosts = [hosts]
        self.hosts: List[ConnURL] = [ConnURL(host = parse_host(h)) for h in hosts]
        """The host addresses to connect to as a list of (hostname, port) pairs."""

        self.timeout: int = timeout
        """The number of seconds to wait for a response from a node."""

        self.max_redirects: int = max_redirects
        """The maximum number of redirects to follow when executing a query."""

        self.max_attempts_per_host: int = max_attempts_per_host
        """The maximum number of attempts to make to a node before giving up. We
        will attempt all nodes in a random order this many times per node before
        giving up.
        """

        self.read_consistency: Literal["none", "weak", "strong"] = read_consistency
        """The default read consistency when initializing cursors."""

        self.freshness: str = freshness
        """Default freshness value for none-consistency reads."""

        self.log_config = log_config
        """The log configuration for this connection and all cursors it creates."""
        self.io = ConnectionClient(
            hosts = self.hosts,
            log_config = self.log_config,
            timeout = self.timeout,
            max_redirects = self.max_redirects,
            max_attempts_per_host = self.max_attempts_per_host,
        )
        self.default_mode = default_mode
    
    @property
    def _is_async_default(self) -> bool:
        return self.default_mode == "async"

    def cursor(
        self,
        read_consistency: Optional[Literal["none", "weak", "strong"]] = None,
        freshness: Optional[str] = None,
        default_mode: Literal["sync", "async"] = None,
    ) -> "Cursor":
        """Creates a new cursor for this connection.

        Args:
            read_consistency: The read consistency to use for this cursor. If
                None, the default read consistency for this connection will be
                used.
            freshness: The freshness value to use for this cursor. If None, the
                default freshness value for this connection will be used.

        Returns:
            A new cursor for this connection.
        """
        if read_consistency is None: read_consistency = self.read_consistency
        if freshness is None: freshness = self.freshness
        if default_mode is None: default_mode = self.default_mode
        return Cursor(self, read_consistency, freshness, default_mode)

    def backup(self, file: SyncWritableIO, /, raw: bool = False) -> None:
        """Backup the database to a file.

        Args:
            file (file-like): The file to write the backup to.
            raw (bool): If true, the backup will be in raw SQL format. If false, the
                backup will be in the smaller sqlite format.
        """
        request_id = secrets.token_hex(4)
        logging.log(
            self.log_config.backup_start,
            lambda _: f"  [RQLITE BACKUP {{{request_id}}}] raw={raw}",
        )
        request_started_at = time.perf_counter()
        # It is much faster for us to discover the leader and fetch the backup
        # from the leader right now: https://github.com/rqlite/rqlite/issues/1551
        leader = self.io.discover_leader()

        if raw:
            resp = self.io.fetch_response(
                "GET", "/db/backup?fmt=sql", stream=True, initial_host=leader
            )
        else:
            resp = self.io.fetch_response(
                "GET", "/db/backup", stream=True, initial_host=leader
            )

        for chunk in resp.iter_content(chunk_size=4096):
            file.write(chunk)

        resp.close()
        time_taken = time.perf_counter() - request_started_at
        logging.log(
            self.log_config.backup_end,
            lambda _: f"    {{{request_id}}} in {time_taken:.3f}s ->> backup fully written",
        )

    async def abackup(self, file: AsyncWritableIO, /, raw: bool = False) -> None:
        """Backup the database to a file.
        Args:
            file (file-like): The file to write the backup to.
            raw (bool): If true, the backup will be in raw SQL format. If false, the
                backup will be in the smaller sqlite format.
        """
        request_id = secrets.token_hex(4)
        logging.log(
            self.log_config.backup_start,
            lambda _: f"  [RQLITE BACKUP {{{request_id}}}] raw={raw}",
        )
        request_started_at = time.perf_counter()
        # It is much faster for us to discover the leader and fetch the backup
        # from the leader right now: https://github.com/rqlite/rqlite/issues/1551
        leader = await self.io.adiscover_leader()

        if raw:
            resp = await self.io.afetch_response(
                "GET", "/db/backup?fmt=sql", stream=True, initial_host=leader
            )
        else:
            resp = await self.io.afetch_response(
                "GET", "/db/backup", stream=True, initial_host=leader
            )

        async for chunk in resp.iter_content(chunk_size=4096):
            await file.write(chunk)

        await resp.close()
        time_taken = time.perf_counter() - request_started_at
        logging.log(
            self.log_config.backup_end,
            lambda _: f"    {{{request_id}}} in {time_taken:.3f}s ->> backup fully written",
        )

    def execute(
        self,
        operation: str,
        parameters: t.Optional[t.Iterable[t.Any]] = None,
        raise_on_error: bool = True,
        read_consistency: t.Optional[t.Literal["none", "weak", "strong"]] = None,
        freshness: t.Optional[str] = None,
        is_async: bool = None,
    ) -> t.Union[ResultItem, t.Awaitable[ResultItem]]:
        """Executes a single query and returns the result. This will also
        update this object so that fetchone() and related functions can be used
        to fetch the results instead.

        Args:
            operation (str): The query to execute.
            parameters (iterable): The parameters to pass to the query.
            raise_on_error (bool): If True, raise an error if the query fails. If
                False, you can check the result item's error property to see if
                the query failed.
            read_consistency (Optional[Literal["none", "weak", "strong"]]):
                The read consistency to use when executing the query. If None,
                use the default read consistency for this cursor.
            freshness (Optional[str]): The freshness to use when executing
                none read consistency queries. If None, use the default freshness
                for this cursor.

        Returns:
            ResultItem: The result of the query.
        """
        if is_async is None: is_async = self._is_async_default
        return self.cursor(
            read_consistency = read_consistency, 
            freshness = freshness
        ).execute(
            operation = operation,
            parameters = parameters,
            raise_on_error = raise_on_error,
            is_async = is_async,
        )
