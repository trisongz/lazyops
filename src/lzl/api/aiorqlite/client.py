from __future__ import annotations

import time
import random
import urllib.parse
import typing as t
from lzl.types import BaseModel, PrivateAttr, eproperty
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
    Awaitable,
    cast,
)
from .errors import (
    ConnectError,
    MaxAttemptsError,
    MaxRedirectsError,
    UnexpectedResponse,
)
from . import logging

# import requests
from lzl.api import aioreq
from .utils import parse_host


T = TypeVar("T")


if t.TYPE_CHECKING:
    from lzl.api.aioreq import Response, AsyncResponse

class ConnURL(BaseModel):
    host: AnyHttpUrl
    _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)

    @eproperty
    def safe_url(self) -> str:
        """
        Returns the url
        """
        base = f'{self.host.scheme}://'
        if self.host.username and self.host.password:
            base += f'{self.host.username}:****@'
        elif self.host.password:
            base += ':****@'
        base += self.host.host
        if self.host.port:
            base += f':{self.host.port}'
        return base

    @eproperty
    def url(self) -> str:
        """
        Returns the url
        """
        base = f'{self.host.scheme}://'
        if self.host.username and self.host.password:
            base += f'{self.host.username}:{self.host.password}@'
        elif self.host.password:
            base += f':{self.host.password}@'
        base += self.host.host
        if self.host.port:
            base += f':{self.host.port}'
        return base

    @eproperty
    def bare(self) -> str:
        """
        Returns the url
        """
        base = f'{self.host.scheme}://{self.host.host}'
        if self.host.port:
            base += f':{self.host.port}'
        return base


    def with_uri(self, uri: str) -> str:
        """
        Returns the url
        """
        return urllib.parse.urljoin(self.url, uri)

class ConnectionClient:
    def __init__(
        self, 
        hosts: List[ConnURL],
        log_config: logging.LogConfig,
        timeout: int = 5,
        max_redirects: int = 2,
        max_attempts_per_host: int = 2,
        
    ):
        self.hosts: List[ConnURL] = hosts
        self.log_config = log_config
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.max_attempts_per_host = max_attempts_per_host
        from lzl.api.aioreq import Client, exceptions
        self._excs = exceptions
        self.io = Client(
            timeout = timeout,
            retries = max_attempts_per_host,
        )
        self.timeout = timeout

    def fetch_response_with_host(
        self,
        host: ConnURL,
        method: Literal["GET", "POST"],
        uri: str,
        json: Any = None,
        headers: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> 'Response':
        """Fetches a response from a particular host, and returns the status
        code and headers. The response body is written to the given destination.

        This will follow up to the maximum number of redirects.

        Args:
            host (str): The host to fetch the response from.
            port (int): The port to use when connecting to the host.
            method (str): The HTTP method to use.
            uri (str): The URI to fetch.
            json (dict): The JSON to send in the request body.
            headers (dict): The headers to send in the request in addition to the content type.
                The dictionary should be accessed only using lowercase keys.

        Returns:
            requests.Response: The response from the server.

        Raises:
            ConnectTimeout: If the connection times out.
            MaxRedirectsError: If the maximum number of redirects is exceeded.
            UnexpectedResponse: If the server returns a response we didn't expect.
        """
        redirect_path = []
        original_host = host.with_uri(uri)
        current_host = original_host
        while len(redirect_path) < self.max_redirects:
            try:
                response = self.io.request(
                    method,
                    current_host,
                    json = json,
                    headers = headers,
                    timeout = self.timeout,
                    allow_redirects = False,
                    stream = stream,
                )
                if response.is_redirect:
                    redirected_to = response.headers["Location"]
                    if stream: response.close()
                    current_host = redirected_to
                    redirect_path.append(redirected_to)
                    continue

                if response.status_code < 200 or response.status_code > 299:
                    raise UnexpectedResponse(
                        current_host,
                        f"Unexpected response from {current_host}: {response.status_code} {response.reason}",
                    )

                return response
            except self._excs.ConnectTimeout as e:
                raise ConnectError(
                    f"Connection to {host.safe_url} timed out", current_host
                ) from e
            except self._excs.ConnectionError as e:
                raise ConnectError(
                    f"Connection to {host.safe_url} was refused", current_host
                ) from e
        raise MaxRedirectsError(original_host, redirect_path)


    async def afetch_response_with_host(
        self,
        host: ConnURL,
        method: Literal["GET", "POST"],
        uri: str,
        json: Any = None,
        headers: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> 'Response':
        """Fetches a response from a particular host, and returns the status
        code and headers. The response body is written to the given destination.

        This will follow up to the maximum number of redirects.

        Args:
            host (str): The host to fetch the response from.
            port (int): The port to use when connecting to the host.
            method (str): The HTTP method to use.
            uri (str): The URI to fetch.
            json (dict): The JSON to send in the request body.
            headers (dict): The headers to send in the request in addition to the content type.
                The dictionary should be accessed only using lowercase keys.

        Returns:
            requests.Response: The response from the server.

        Raises:
            ConnectTimeout: If the connection times out.
            MaxRedirectsError: If the maximum number of redirects is exceeded.
            UnexpectedResponse: If the server returns a response we didn't expect.
        """
        redirect_path = []
        original_host = host.with_uri(uri)
        current_host = original_host
        while len(redirect_path) < self.max_redirects:
            try:
                response: 'Response' = await self.io.arequest(
                    method,
                    current_host,
                    json = json,
                    headers = headers,
                    timeout = self.timeout,
                    allow_redirects = False,
                    stream = stream,
                )
                if response.is_redirect:
                    redirected_to = response.headers["Location"]
                    if stream: response.close()
                    current_host = redirected_to
                    redirect_path.append(redirected_to)
                    continue

                if response.status_code < 200 or response.status_code > 299:
                    raise UnexpectedResponse(
                        current_host,
                        f"Unexpected response from {current_host}: {response.status_code} {response.reason}",
                    )

                return response
            except self._excs.ConnectTimeout as e:
                raise ConnectError(
                    f"Connection to {host.safe_url} timed out", current_host
                ) from e
            except self._excs.ConnectionError as e:
                raise ConnectError(
                    f"Connection to {host.safe_url} was refused", current_host
                ) from e
        raise MaxRedirectsError(original_host, redirect_path)
    
    def fetch_response(
        self,
        method: Literal["GET", "POST"],
        uri: str,
        json: Any = None,
        headers: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        initial_host: Optional[ConnURL] = None,
        query_info: Optional[logging.QueryInfoLazy] = None,
    ) -> 'Response':
        """Fetches a response from the server by requesting it from a random node. If
        a connection error occurs, this method will retry the request on a different
        node until it succeeds or the maximum number of attempts is reached.

        Args:
            method (str): The HTTP method to use for the request.
            uri (str): The URI of the request.
            json (dict): The json data to send with the request.
            headers (dict): The headers to send with the request.
            stream (bool): If True, the response will be streamed.
            initial_host (Optional[ConnURL]): The host to try first. If None,
                a random host will be chosen.
            query_info (Optional[logging.QueryInfo]): The query info for slow
                query logging, or None to disable slow query logging regardless of
                the log configuration.

        Returns:
            requests.Response: If a successful response is received, it is returned.

        Raises:
            MaxAttemptsError: If the maximum number of attempts is reached before
                we get a successful response.
            UnexpectedResponse: If one of the rqlite nodes returns a response
                we didn't expect
        """
        
        def attempt_host(
            host: ConnURL, 
            node_path: List[Tuple[str, Exception]]
        ) -> Optional['Response']:
            try:
                started_at_wall = time.time()
                started_at_perf = time.perf_counter()
                result = self.fetch_response_with_host(
                    host, method, uri, json = json, headers = headers, stream = stream
                )
                request_time_perf = time.perf_counter() - started_at_perf
                ended_at_wall = time.time()

                if (
                    query_info is not None
                    and self.log_config.slow_query is not None
                    and self.log_config.slow_query.get("enabled", True)
                ):
                    config = cast(
                        logging.SlowQueryLogMessageConfig,
                        self.log_config.slow_query,
                    )
                    if request_time_perf >= config.get("threshold_seconds", 5):
                        config["method"](
                            logging.QueryInfo(
                                operations=(
                                    query_info.operations() if callable(query_info.operations) else query_info.operations
                                ),
                                params=(
                                    query_info.params() if callable(query_info.params) else query_info.params
                                ),
                                request_type=(
                                    query_info.request_type() if callable(query_info.request_type) else query_info.request_type
                                ),
                                consistency=query_info.consistency,
                                freshness=query_info.freshness,
                            ),
                            duration_seconds=request_time_perf,
                            host = host.bare,
                            response_size_bytes = int(result.headers.get("Content-Length", "0")),
                            started_at = started_at_wall,
                            ended_at = ended_at_wall,
                        )

                return result
            
            except ConnectError as e:
                def msg_supplier(max_length: Optional[int]) -> str:
                    str_error = str(e)
                    if max_length is not None and len(str_error) > max_length: str_error = f"{str_error[:max_length]}..."
                    return f"Failed to connect to node {e.host} - {str_error}"
                logging.log(self.log_config.connect_timeout, msg_supplier, exc_info=True)
                node_path.append((e.host, e))
            
            except MaxRedirectsError as e:
                def msg_supplier(max_length: Optional[int]) -> str:
                    str_redirect_path = str(e.redirect_path)
                    if max_length is not None and len(str_redirect_path) > max_length:
                        str_redirect_path = f"{str_redirect_path[:max_length]}..."
                    return f"Max redirects reached for node {e.host} (redirect path: {str_redirect_path})"

                logging.log(self.log_config.non_ok_response, msg_supplier, exc_info=True)
                node_path.append((e.host, e))
            
            except UnexpectedResponse as e:
                def msg_supplier(max_length: Optional[int]) -> str:
                    str_error = str(e)
                    if max_length is not None and len(str_error) > max_length: str_error = f"{str_error[:max_length]}..."
                    return f"Unexpected response from node {e.host}: {str_error}"

                logging.log(self.log_config.non_ok_response, msg_supplier, exc_info=True)
                raise
        return self.try_hosts(attempt_host, initial_host=initial_host)

    @t.overload
    async def afetch_response(
        self,
        method: Literal["GET", "POST"],
        uri: str,
        json: Any = None,
        headers: Optional[Dict[str, Any]] = None,
        stream: t.Literal[False] = False,
        initial_host: Optional[ConnURL] = None,
        query_info: Optional[logging.QueryInfoLazy] = None,
    ) -> 'Response':
        """Fetches a response from the server by requesting it from a random node. If
        a connection error occurs, this method will retry the request on a different
        node until it succeeds or the maximum number of attempts is reached.

        Args:
            method (str): The HTTP method to use for the request.
            uri (str): The URI of the request.
            json (dict): The json data to send with the request.
            headers (dict): The headers to send with the request.
            stream (bool): If True, the response will be streamed.
            initial_host (Optional[ConnURL]): The host to try first. If None,
                a random host will be chosen.
            query_info (Optional[logging.QueryInfo]): The query info for slow
                query logging, or None to disable slow query logging regardless of
                the log configuration.

        Returns:
            requests.Response: If a successful response is received, it is returned.

        Raises:
            MaxAttemptsError: If the maximum number of attempts is reached before
                we get a successful response.
            UnexpectedResponse: If one of the rqlite nodes returns a response
                we didn't expect
        """
        ...

    @t.overload
    async def afetch_response(
        self,
        method: Literal["GET", "POST"],
        uri: str,
        json: Any = None,
        headers: Optional[Dict[str, Any]] = None,
        stream: t.Literal[True] = True,
        initial_host: Optional[ConnURL] = None,
        query_info: Optional[logging.QueryInfoLazy] = None,
    ) -> 'AsyncResponse':
        """Fetches a response from the server by requesting it from a random node. If
        a connection error occurs, this method will retry the request on a different
        node until it succeeds or the maximum number of attempts is reached.

        Args:
            method (str): The HTTP method to use for the request.
            uri (str): The URI of the request.
            json (dict): The json data to send with the request.
            headers (dict): The headers to send with the request.
            stream (bool): If True, the response will be streamed.
            initial_host (Optional[ConnURL]): The host to try first. If None,
                a random host will be chosen.
            query_info (Optional[logging.QueryInfo]): The query info for slow
                query logging, or None to disable slow query logging regardless of
                the log configuration.

        Returns:
            requests.Response: If a successful response is received, it is returned.

        Raises:
            MaxAttemptsError: If the maximum number of attempts is reached before
                we get a successful response.
            UnexpectedResponse: If one of the rqlite nodes returns a response
                we didn't expect
        """
        ...

    async def afetch_response(
        self,
        method: Literal["GET", "POST"],
        uri: str,
        json: Any = None,
        headers: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        initial_host: Optional[ConnURL] = None,
        query_info: Optional[logging.QueryInfoLazy] = None,
    ) -> 'Response':
        """Fetches a response from the server by requesting it from a random node. If
        a connection error occurs, this method will retry the request on a different
        node until it succeeds or the maximum number of attempts is reached.

        Args:
            method (str): The HTTP method to use for the request.
            uri (str): The URI of the request.
            json (dict): The json data to send with the request.
            headers (dict): The headers to send with the request.
            stream (bool): If True, the response will be streamed.
            initial_host (Optional[ConnURL]): The host to try first. If None,
                a random host will be chosen.
            query_info (Optional[logging.QueryInfo]): The query info for slow
                query logging, or None to disable slow query logging regardless of
                the log configuration.

        Returns:
            requests.Response: If a successful response is received, it is returned.

        Raises:
            MaxAttemptsError: If the maximum number of attempts is reached before
                we get a successful response.
            UnexpectedResponse: If one of the rqlite nodes returns a response
                we didn't expect
        """
        
        async def attempt_host(
            host: ConnURL, 
            node_path: List[Tuple[str, Exception]]
        ) -> Optional['Response']:
            try:
                started_at_wall = time.time()
                started_at_perf = time.perf_counter()
                result = await self.afetch_response_with_host(
                    host, method, uri, json = json, headers = headers, stream = stream
                )
                request_time_perf = time.perf_counter() - started_at_perf
                ended_at_wall = time.time()

                if (
                    query_info is not None
                    and self.log_config.slow_query is not None
                    and self.log_config.slow_query.get("enabled", True)
                ):
                    config = cast(
                        logging.SlowQueryLogMessageConfig,
                        self.log_config.slow_query,
                    )
                    if request_time_perf >= config.get("threshold_seconds", 5):
                        config["method"](
                            logging.QueryInfo(
                                operations=(
                                    query_info.operations() if callable(query_info.operations) else query_info.operations
                                ),
                                params=(
                                    query_info.params() if callable(query_info.params) else query_info.params
                                ),
                                request_type=(
                                    query_info.request_type() if callable(query_info.request_type) else query_info.request_type
                                ),
                                consistency=query_info.consistency,
                                freshness=query_info.freshness,
                            ),
                            duration_seconds=request_time_perf,
                            host = host.bare,
                            response_size_bytes = int(result.headers.get("Content-Length", "0")),
                            started_at = started_at_wall,
                            ended_at = ended_at_wall,
                        )

                return result
            
            except ConnectError as e:
                def msg_supplier(max_length: Optional[int]) -> str:
                    str_error = str(e)
                    if max_length is not None and len(str_error) > max_length: str_error = f"{str_error[:max_length]}..."
                    return f"Failed to connect to node {e.host} - {str_error}"
                logging.log(self.log_config.connect_timeout, msg_supplier, exc_info=True)
                node_path.append((e.host, e))
            
            except MaxRedirectsError as e:
                def msg_supplier(max_length: Optional[int]) -> str:
                    str_redirect_path = str(e.redirect_path)
                    if max_length is not None and len(str_redirect_path) > max_length:
                        str_redirect_path = f"{str_redirect_path[:max_length]}..."
                    return f"Max redirects reached for node {e.host} (redirect path: {str_redirect_path})"

                logging.log(self.log_config.non_ok_response, msg_supplier, exc_info=True)
                node_path.append((e.host, e))
            
            except UnexpectedResponse as e:
                def msg_supplier(max_length: Optional[int]) -> str:
                    str_error = str(e)
                    if max_length is not None and len(str_error) > max_length: str_error = f"{str_error[:max_length]}..."
                    return f"Unexpected response from node {e.host}: {str_error}"

                logging.log(self.log_config.non_ok_response, msg_supplier, exc_info=True)
                raise
        
        return await self.atry_hosts(attempt_host, initial_host=initial_host)

    def try_hosts(
        self,
        attempt_host: Callable[
            [ConnURL, List[Tuple[str, Exception]]], Optional[T]
        ],
        /,
        *,
        initial_host: Optional[ConnURL] = None,
    ) -> T:
        """Given a function like

        ```py
        def attempt_host(host: ConnURL, node_path: List[Tuple[str, Exception]]) -> Optional[str]:
            try:
                # do something with the host
                return 'result'
            except Exception as e: # only catch exceptions that should continue to the next host
                node_path.append((host, e))
                return None
        ```

        This will call `attempt_host` on each host in the connection in a random
        order until a non-None value is returned or the maximum number of attempts
        per host is reached.

        Args:
            attempt_host: The function to call on each host. It should return None
                if the host failed but we should continue to the next host, or a
                non-None value if the host succeeded. It should raise an exception if
                the host failed and we should not continue to the next host.
            initial_host: The host to try first. If None, a random host will be chosen.
                This does not need to be a host in self.hosts, but if it is not, it
                will not be included in the count for the maximum number of attempts
        Raises:
            MaxAttemptsError: If the maximum number of attempts is reached before
                we get a successful response.
            Exception: any errors raised by `attempt_host`
        """
        node_path: List[Tuple[str, Exception]] = []
        first_node_idx: Optional[int] = None
        if initial_host is not None:
            try:
                first_node_idx = self.hosts.index(initial_host)
            except ValueError:
                if resp := attempt_host(initial_host, node_path):
                    return resp

        if first_node_idx is None: first_node_idx = random.randrange(0, len(self.hosts))
        if resp := attempt_host(self.hosts[first_node_idx], node_path): return resp
        remaining_nodes = [
            h for idx, h in enumerate(self.hosts) if idx != first_node_idx
        ]
        random.shuffle(remaining_nodes)
        node_ordering = [self.hosts[first_node_idx]] + remaining_nodes
        index, attempt = 0, 1

        while index < len(self.hosts) or attempt < self.max_attempts_per_host:
            if index + 1 < len(self.hosts):
                index += 1
            else:
                index = 0
                attempt += 1

            if resp := attempt_host(node_ordering[index], node_path): return resp
        raise MaxAttemptsError(node_path)
    

    async def atry_hosts(
        self,
        attempt_host: Callable[
            [ConnURL, List[Tuple[str, Exception]]], Awaitable[Optional[T]]
        ],
        /,
        *,
        initial_host: Optional[ConnURL] = None,
    ) -> T:
        """Given a function like

        ```py
        def attempt_host(host: ConnURL, node_path: List[Tuple[str, Exception]]) -> Optional[str]:
            try:
                # do something with the host
                return 'result'
            except Exception as e: # only catch exceptions that should continue to the next host
                node_path.append((host, e))
                return None
        ```

        This will call `attempt_host` on each host in the connection in a random
        order until a non-None value is returned or the maximum number of attempts
        per host is reached.

        Args:
            attempt_host: The function to call on each host. It should return None
                if the host failed but we should continue to the next host, or a
                non-None value if the host succeeded. It should raise an exception if
                the host failed and we should not continue to the next host.
            initial_host: The host to try first. If None, a random host will be chosen.
                This does not need to be a host in self.hosts, but if it is not, it
                will not be included in the count for the maximum number of attempts
        Raises:
            MaxAttemptsError: If the maximum number of attempts is reached before
                we get a successful response.
            Exception: any errors raised by `attempt_host`
        """
        node_path: List[Tuple[str, Exception]] = []
        first_node_idx: Optional[int] = None
        if initial_host is not None:
            try:
                first_node_idx = self.hosts.index(initial_host)
            except ValueError:
                if resp := await attempt_host(initial_host, node_path):
                    return resp

        if first_node_idx is None: first_node_idx = random.randrange(0, len(self.hosts))
        if resp := await attempt_host(self.hosts[first_node_idx], node_path): return resp
        remaining_nodes = [
            h for idx, h in enumerate(self.hosts) if idx != first_node_idx
        ]
        random.shuffle(remaining_nodes)
        node_ordering = [self.hosts[first_node_idx]] + remaining_nodes
        index, attempt = 0, 1

        while index < len(self.hosts) or attempt < self.max_attempts_per_host:
            if index + 1 < len(self.hosts):
                index += 1
            else:
                index = 0
                attempt += 1

            if resp := await attempt_host(node_ordering[index], node_path): return resp
        raise MaxAttemptsError(node_path)
    
    def discover_leader(self) -> ConnURL:
        """Discovers the current leader for the cluster

        Returns:
            A tuple of (leader_host, leader_port)

        Raises:
            MaxAttemptsError: If the maximum number of attempts is reached before
                we get a successful response.
            UnexpectedResponse: If one of the rqlite nodes returns a response
                we didn't expect
        """

        def attempt_host(
                host: ConnURL, 
                node_path: List[Tuple[str, Exception]]
            ) -> Optional[ConnURL]:
            try:
                return self.discover_leader_with_host(host)
            
            except ConnectError as e:
                def msg_supplier(max_length: Optional[int]) -> str:
                    str_error = str(e)
                    if max_length is not None and len(str_error) > max_length: str_error = f"{str_error[:max_length]}..."
                    return f"Failed to connect to node {e.host} - {str_error}"
                logging.log(self.log_config.connect_timeout, msg_supplier, exc_info=True)
                node_path.append((e.host, e))
            
            except UnexpectedResponse as e:
                def msg_supplier(max_length: Optional[int]) -> str:
                    str_error = str(e)
                    if max_length is not None and len(str_error) > max_length: str_error = f"{str_error[:max_length]}..."
                    return f"Unexpected response from node {e.host}: {str_error}"

                logging.log(self.log_config.non_ok_response, msg_supplier, exc_info=True)
                raise

        return self.try_hosts(attempt_host)
    

    async def adiscover_leader(self) -> ConnURL:
        """Discovers the current leader for the cluster

        Returns:
            A tuple of (leader_host, leader_port)

        Raises:
            MaxAttemptsError: If the maximum number of attempts is reached before
                we get a successful response.
            UnexpectedResponse: If one of the rqlite nodes returns a response
                we didn't expect
        """

        async def attempt_host(
                host: ConnURL, 
                node_path: List[Tuple[str, Exception]]
            ) -> Optional[ConnURL]:
            try:
                return await self.adiscover_leader_with_host(host)
            
            except ConnectError as e:
                def msg_supplier(max_length: Optional[int]) -> str:
                    str_error = str(e)
                    if max_length is not None and len(str_error) > max_length: str_error = f"{str_error[:max_length]}..."
                    return f"Failed to connect to node {e.host} - {str_error}"
                logging.log(self.log_config.connect_timeout, msg_supplier, exc_info=True)
                node_path.append((e.host, e))
            
            except UnexpectedResponse as e:
                def msg_supplier(max_length: Optional[int]) -> str:
                    str_error = str(e)
                    if max_length is not None and len(str_error) > max_length: str_error = f"{str_error[:max_length]}..."
                    return f"Unexpected response from node {e.host}: {str_error}"

                logging.log(self.log_config.non_ok_response, msg_supplier, exc_info=True)
                raise

        return self.try_hosts(attempt_host)

    def discover_leader_with_host(self, host: ConnURL) -> ConnURL:
        """Uses the given node in the cluster to discover the current leader
        for the cluster.

        Returns:
            A tuple of (leader_host, leader_port)

        Raises:
            ConnectTimeout: If the connection times out.
            UnexpectedResponse: If the server returns a response we didn't expect.
        """
        response = None
        try:
            response = aioreq.request(
                "POST",
                host.with_uri("/db/query?level=weak&redirect"),
                json = [["SELECT 1"]],
                headers = {"Content-Type": "application/json; charset=UTF-8"},
                timeout = self.timeout,
                allow_redirects = False,
            )

            if response.is_redirect:
                redirected_to = response.headers["Location"]
                parsed_url = urllib.parse.urlparse(redirected_to)
                return ConnURL(host = parse_host(
                    parsed_url.netloc,
                    # default_port = 443 if parsed_url.scheme == "https" else 80,
                ))

            if response.status_code < 200 or response.status_code > 299:
                raise UnexpectedResponse(
                    host.safe_url,
                    f"Unexpected response from {host.bare}: {response.status_code} {response.reason}",
                )

            return host
        except self._excs.ConnectTimeout as e:
            raise ConnectError(
                f"Connection to {host.bare} timed out", host.bare
            ) from e
        except self._excs.ConnectionError as e:
            raise ConnectError(
                f"Connection to {host.bare} was refused", f"{host.bare}"
            ) from e
        

    async def adiscover_leader_with_host(self, host: ConnURL) -> ConnURL:
        """Uses the given node in the cluster to discover the current leader
        for the cluster.

        Returns:
            A tuple of (leader_host, leader_port)

        Raises:
            ConnectTimeout: If the connection times out.
            UnexpectedResponse: If the server returns a response we didn't expect.
        """
        response = None
        try:
            response = await aioreq.arequest(
                "POST",
                host.with_uri("/db/query?level=weak&redirect"),
                json = [["SELECT 1"]],
                headers = {"Content-Type": "application/json; charset=UTF-8"},
                timeout = self.timeout,
                allow_redirects = False,
            )

            if response.is_redirect:
                redirected_to = response.headers["Location"]
                parsed_url = urllib.parse.urlparse(redirected_to)
                return ConnURL(host = parse_host(
                    parsed_url.netloc,
                    # default_port = 443 if parsed_url.scheme == "https" else 80,
                ))

            if response.status_code < 200 or response.status_code > 299:
                raise UnexpectedResponse(
                    host.safe_url,
                    f"Unexpected response from {host.bare}: {response.status_code} {response.reason}",
                )

            return host
        except self._excs.ConnectTimeout as e:
            raise ConnectError(
                f"Connection to {host.bare} timed out", host.bare
            ) from e
        except self._excs.ConnectionError as e:
            raise ConnectError(
                f"Connection to {host.bare} was refused", f"{host.bare}"
            ) from e