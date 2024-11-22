from __future__ import annotations

import typing as t

from lzl.api import aioreq
from pydantic.networks import AnyHttpUrl
from pyrqlite.extensions import PARSE_DECLTYPES, PARSE_COLNAMES
from urllib.parse import urlparse
from .utils import parse_host, logger


class Connection(object):
    """
    Describes a synchronous description of a pool of nodes which
    make up a rqlite cluster. There is no actual connection in this
    class, however the name is chosed to signify its similarity to
    a Connection in a DBAPI 2.0 style api.
    """

    def __init__(
        self,
        url: t.Union[str, AnyHttpUrl],
        timeout: t.Optional[float] = None,
        detect_types: t.Optional[bool] = True,
        max_redirects: t.Optional[int] = -1,
        max_retries: t.Optional[int] = 10,
        read_consistency: t.Literal["none", "weak", "strong"] = "strong",
        freshness: t.Optional[str] = "0", 
        default_mode: t.Literal["sync", "async"] = "sync",
    ):
        """
        Initializes a new synchronous Connection. This is typically
        called with the alias aiorqlite.connect

        Args:
            url: The url of the rqlite cluster
        
            timeout (int): The number of seconds to wait for a response
                from a host before giving up.

            max_redirects (int): The maximum number of redirects to follow
                when executing a query.

            read_consistency (str): The read consistency to use for cursors
                by default.

            freshness (str): Default freshness value for none-consistency reads.
                Guarrantees the response is no more stale than the given duration,
                specified as a golang Duration string, e.g., "5m" for 5 minutes

            default_mode (Literal["sync", "async"]): The default mode to use for
                cursors.
        """
        self.messages = []
        self._ephemeral = None
        if url == ':memory:':
            from pyrqlite._ephemeral import EphemeralRqlited
            self._ephemeral = EphemeralRqlited().__enter__()
            host, port = self._ephemeral.http
            url = f'http://{host}:{port}'

        self.url = parse_host(url)
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.max_retries = max_retries
        self.read_consistency = read_consistency
        self.freshness = freshness
        self.default_mode = default_mode

        self.detect_types = detect_types
        self.parse_decltypes = detect_types & PARSE_DECLTYPES
        self.parse_colnames = detect_types & PARSE_COLNAMES
        self.io: aioreq.Client = self._init_connection()

    
    def _init_connection(self) -> aioreq.Client:
        """
        Initializes the Connection
        """
        kwargs = {
            'base_url': f'{self.url.scheme}://{self.url.host}',
            'timeout': None if self.timeout is None else float(self.timeout)
        }
        if self.url.port:
            kwargs['base_url'] += f':{self.url.port}'
        if self.url.username:
            from niquests.auth import HTTPBasicAuth
            kwargs['auth'] = HTTPBasicAuth(self.url.username, self.url.password)
        return aioreq.Client(**kwargs)


    def _retry_request(self, method: str, uri: str, body: t.Optional[t.Any] = None, headers: t.Optional[t.Dict[str, str]] = None) -> 'aioreq.Response':
        """
        [Sync] Retries a request
        """
        tries = self.max_retries
        headers = headers or None
        while tries:
            tries -= 1
            try:
                return self._connection.request(method, uri, data=body, headers=headers)
            except Exception as e:
                if not tries: raise e
                self._connection.close()
                self._connection = self._init_connection()

    async def _aretry_request(self, method: str, uri: str, body: t.Optional[t.Any] = None, headers: t.Optional[t.Dict[str, str]] = None) -> 'aioreq.Response':
        """
        [Async] Retries a request
        """
        tries = self.max_retries
        headers = headers or None
        while tries:
            tries -= 1
            try:
                return await self._aconnection.arequest(method, uri, data=body, headers=headers)
            except Exception as e:
                if not tries: raise e
                await self._aconnection.aclose()
                self._aconnection = self._init_connection()

    
    def _fetch_response(self, method: str, uri: str, body: t.Optional[t.Any] = None, headers: t.Optional[t.Dict[str, str]] = None) -> 'aioreq.Response':
        """
        [Sync] Fetch a response, handling redirection.
        """
        response = self._retry_request(method, uri, body=body, headers=headers)
        redirects = 0
        while response.status_code == 301 and \
                response.headers.get('Location') is not None and \
                (self.max_redirects == -1 or redirects < self.max_redirects):
            
            redirects += 1
            uri = response.headers.get('Location')
            location = urlparse(uri)
            logger.info(f'Status: {response.status_code} Reason: {response.reason} Location: {uri}')
            if self.url.host != location.hostname or self.url.port != location.port:
                self._connection.close()
                new_url = f'{location.scheme}://{self.url.username}:{self.url.password}@{location.hostname}:{location.port}' if self.url.password else f'{location.scheme}://{location.hostname}:{location.port}'
                self.url = parse_host(new_url)
                self._connection = self._init_connection()

            response = self._retry_request(method, uri, body=body, headers=headers)
        return response
    
    async def _afetch_response(self, method: str, uri: str, body: t.Optional[t.Any] = None, headers: t.Optional[t.Dict[str, str]] = None) -> 'aioreq.Response':
        """
        [Async] Fetch a response, handling redirection.
        """
        response = await self._aretry_request(method, uri, body=body, headers=headers)
        redirects = 0
        while response.status_code == 301 and \
                response.headers.get('Location') is not None and \
                (self.max_redirects == -1 or redirects < self.max_redirects):
            
            redirects += 1
            uri = response.headers.get('Location')
            location = urlparse(uri)
            logger.info(f'Status: {response.status_code} Reason: {response.reason} Location: {uri}')
            if self.url.host != location.hostname or self.url.port != location.port:
                self._connection.close()
                new_url = f'{location.scheme}://{self.url.username}:{self.url.password}@{location.hostname}:{location.port}' if self.url.password else f'{location.scheme}://{location.hostname}:{location.port}'
                self.url = parse_host(new_url)
                self._connection = self._init_connection()

            response = await self._aretry_request(method, uri, body=body, headers=headers)
        return response
    

    def close(self):
        """
        Close the connection now (rather than whenever .__del__() is
        called).

        The connection will be unusable from this point forward; an
        Error (or subclass) exception will be raised if any operation
        is attempted with the connection. The same applies to all
        cursor objects trying to use the connection. Note that closing
        a connection without committing the changes first will cause an
        implicit rollback to be performed."""
        self._connection.close()
        if self._ephemeral is not None:
            self._ephemeral.__exit__(None, None, None)
            self._ephemeral = None

    def __del__(self):
        self.close()

    def commit(self):
        """Database modules that do not support transactions should
        implement this method with void functionality."""
        pass

    def rollback(self):
        """This method is optional since not all databases provide
        transaction support. """
        pass

    def cursor(self, factory=None):
        """Return a new Cursor Object using the connection."""
        if factory:
            return factory(self)
        else:
            return Cursor(self)

    def execute(self, *args, **kwargs):
        return self.cursor().execute(*args, **kwargs)

    def ping(self, reconnect=True):
        if self._connection.sock is None:
            if reconnect:
                self._connection = self._init_connection()
            else:
                raise self.Error("Already closed")
        try: 
            self.execute("SELECT 1")
        except Exception:
            if reconnect:
                self._connection = self._init_connection()
                self.ping(False)
            else:
                raise