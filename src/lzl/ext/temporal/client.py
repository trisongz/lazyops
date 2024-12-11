from __future__ import annotations

import asyncio
import typing as t
from temporalio.converter import DataConverter
from temporalio.client import Client, KeepAliveConfig
from .utils import logger
from . import patches

if t.TYPE_CHECKING:
    from temporalio.common import QueryRejectCondition
    from temporalio.runtime import Runtime
    from temporalio.client import (
        TLSConfig,
        Interceptor,
        RetryConfig,
        HttpConnectProxyConfig,
        MethodAsyncSingleParam,
        ParamType,
        SelfType, ParamType, ReturnType,

    )
    from temporalio.worker import Worker
    from lzl.ext.temporal.configs import TemporalSettings


class TemporalClient(Client):

    
    # @staticmethod
    @classmethod
    async def connect(
        cls: t.Type['TemporalClient'],
        target_host: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        api_key: t.Optional[str] = None,
        data_converter: t.Optional['DataConverter'] = None,
        interceptors: t.Sequence['Interceptor'] = [],
        default_workflow_query_reject_condition: t.Optional[
            'QueryRejectCondition'
        ] = None,
        tls: t.Union[bool, 'TLSConfig'] = False,
        retry_config: t.Optional['RetryConfig'] = None,
        keep_alive_config: t.Optional['KeepAliveConfig'] = KeepAliveConfig.default,
        rpc_metadata: t.Mapping[str, str] = {},
        identity: t.Optional[str] = None,
        lazy: bool = False,
        runtime: t.Optional['Runtime'] = None,
        http_connect_proxy_config: t.Optional['HttpConnectProxyConfig'] = None,
        default_task_queue: t.Optional[str] = None,
        config: t.Optional['TemporalSettings'] = None,
        **kwargs,
    ) -> TemporalClient:  # sourcery skip: default-mutable-arg
        """Connect to a Temporal server.

        Args:
            target_host: ``host:port`` for the Temporal server. For local
                development, this is often "localhost:7233".
            namespace: Namespace to use for client calls.
            api_key: API key for Temporal. This becomes the "Authorization"
                HTTP header with "Bearer " prepended. This is only set if RPC
                metadata doesn't already have an "authorization" key.
            data_converter: Data converter to use for all data conversions
                to/from payloads.
            interceptors: Set of interceptors that are chained together to allow
                intercepting of client calls. The earlier interceptors wrap the
                later ones.

                Any interceptors that also implement
                :py:class:`temporalio.worker.Interceptor` will be used as worker
                interceptors too so they should not be given when creating a
                worker.
            default_workflow_query_reject_condition: The default rejection
                condition for workflow queries if not set during query. See
                :py:meth:`WorkflowHandle.query` for details on the rejection
                condition.
            tls: If false, the default, do not use TLS. If true, use system
                default TLS configuration. If TLS configuration present, that
                TLS configuration will be used.
            retry_config: Retry configuration for direct service calls (when
                opted in) or all high-level calls made by this client (which all
                opt-in to retries by default). If unset, a default retry
                configuration is used.
            keep_alive_config: Keep-alive configuration for the client
                connection. Default is to check every 30s and kill the
                connection if a response doesn't come back in 15s. Can be set to
                ``None`` to disable.
            rpc_metadata: Headers to use for all calls to the server. Keys here
                can be overriden by per-call RPC metadata keys.
            identity: Identity for this client. If unset, a default is created
                based on the version of the SDK.
            lazy: If true, the client will not connect until the first call is
                attempted or a worker is created with it. Lazy clients cannot be
                used for workers.
            runtime: The runtime for this client, or the default if unset.
            http_connect_proxy_config: Configuration for HTTP CONNECT proxy.
            default_task_queue: The default task queue to use for this client.
            config: The configuration for this client.
        """
        if config is None:
            from lzl.ext.temporal.configs import get_temporal_settings
            config = get_temporal_settings()
        
        if not target_host: target_host = config.host
        # print('target_host: ', target_host)
        if not namespace and config.namespace: namespace = config.namespace
        if not api_key and config.api_key: api_key = config.api_key
        if not default_task_queue and config.default_task_queue: default_task_queue = config.default_task_queue
        if not tls and config.tls is not None: tls = config.tls
        if not identity and config.identity: identity = config.identity
        if not lazy and config.lazy is not None: lazy = config.lazy
        if data_converter is None: data_converter = config.data_converter

        from temporalio.service import ServiceClient, ConnectConfig
        connect_config = ConnectConfig(
            target_host=target_host,
            api_key=api_key,
            tls=tls,
            retry_config=retry_config,
            keep_alive_config=keep_alive_config,
            rpc_metadata=rpc_metadata,
            identity=identity or "",
            lazy=lazy,
            runtime=runtime,
            http_connect_proxy_config=http_connect_proxy_config,
        )
        new = cls(
            await ServiceClient.connect(connect_config),
            namespace=namespace,
            data_converter=data_converter,
            interceptors=interceptors,
            default_workflow_query_reject_condition=default_workflow_query_reject_condition,
        )
        new._postinit_config_(config = config, **kwargs)
        return new

    def _postinit_config_(self, config: t.Optional['TemporalSettings'] = None, **kwargs) -> None:
        """
        Some post-init config
        """
        if config is None:
            from lzl.ext.temporal.configs import get_temporal_settings
            config = get_temporal_settings()
        self.tmprl_config = config
        self.tmprl_registry = self.tmprl_config.registry
        self._extra: t.Dict[str, t.Any] = {}
        self.tmprl_registry.register_client(self)
        # self.tmprl_registry.clients[self.namespace] = self
        # self.tmprl_registry.client = self
    
    async def run_worker(
        self,
        worker: 'Worker',
        event: asyncio.Event,
        **kwargs,
    ):
        """
        Runs a Temporal Worker
        """
        from lzo.utils import Timer
        ts = Timer(format_short = 1)
        extra = f'|g|NS|e|: `{self.namespace}`' if self.namespace else ''
        if worker.task_queue: extra += f', |g|TQ|e|: `{worker.task_queue}`'
        extra = f' ({extra.strip()})' if extra else ''
        logger.info(f'Starting Temporal Worker{extra}', colored = True)
        await worker.run()
        try:
            await event.wait()
        finally:
            logger.info(f'Shutting Down Temporal Worker. (|g|TTL|e|: {ts.total_s})', prefix = worker.task_queue, colored = True)
        
    # def run_worker(
    #     self,
    #     worker: 'Worker',
    #     event: t.Optional[asyncio.Event] = None,
    #     **kwargs,
    # ):
    #     """
    #     Runs a Temporal Worker
    #     """
    #     if event is None: event = asyncio.Event()
    #     loop = asyncio.get_running_loop()
    #     try:

    #         loop.run_until_complete(self._run_worker(worker, event, **kwargs))
    #     except Exception as e:
    #         logger.error(f'Error Running Temporal Worker: {e}')
    #         raise e
    #     finally:
    #         event.set()
    #         loop.run_until_complete(loop.shutdown_asyncgens())
    # if t.TYPE_CHECKING:


        

    if not t.TYPE_CHECKING:
        # async def start_workflow(
        #     self,
        #     workflow: t.Callable[
        #         t.Concatenate['SelfType', 'MultiParamSpec'], t.Awaitable['ReturnType']
        #     ],
        #     arg: t.Any, 
        #     *,
        #     args: t.Sequence[t.Any] = [], 
        #     id: str,
        #     task_queue: t.Optional[str] = None,
        #     **kwargs,
        # ):
        #     if task_queue is None and self._tconf.default_task_queue: task_queue = self._tconf.default_task_queue
        #     return await super().start_workflow(workflow, arg, args = args, task_queue = task_queue, id = id, **kwargs)

        async def execute_workflow(
            self,
            workflow: 'MethodAsyncSingleParam[SelfType, ParamType, ReturnType]',
            arg: t.Any, 
            *,
            args: t.Sequence[t.Any] = [], 
            id: str,
            task_queue: t.Optional[str] = None,
            **kwargs,
        ):
            if task_queue is None and self.tmprl_config.default_task_queue: task_queue = self.tmprl_config.default_task_queue
            return await super().execute_workflow(workflow, arg, args = args,  task_queue = task_queue, id = id, **kwargs)
        



