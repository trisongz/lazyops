from lazyops.imports._k8s import (
    resolve_k8s,
)

resolve_k8s(
    is_async=True,
    is_sync=True,
    is_operator=True,
    required=True,
)

import kubernetes.client as SyncClient
import kubernetes.config as SyncConfig
import kubernetes.stream.ws_client as SyncStream
import kubernetes.stream.stream as SyncStreamFunc

import kubernetes.watch as SyncWatch
import kubernetes.utils as SyncUtils
import kubernetes.client.models as SyncType

import kubernetes_asyncio.client as AsyncClient
import kubernetes_asyncio.config as AsyncConfig
import kubernetes_asyncio.stream as AsyncStream
import kubernetes_asyncio.watch as AsyncWatch
import kubernetes_asyncio.utils as AsyncUtils
import kubernetes_asyncio.client.models as AsyncType

AsyncWSClient = AsyncStream.WsApiClient



# from lazyops.imports._k8s import (
#     AsyncClient,
#     AsyncConfig,
#     AsyncStream,
#     AsyncWatch,
#     AsyncUtils,
#     AsyncType,
#     AsyncWSClient,

#     SyncClient,
#     SyncConfig,
#     SyncStream,
#     SyncStreamFunc,

#     SyncWatch,
#     SyncUtils,
#     SyncType,

# )