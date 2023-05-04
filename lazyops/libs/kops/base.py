from lazyops.imports._k8s import (
    resolve_k8s,
)

resolve_k8s(
    is_async=True,
    is_sync=True,
    is_operator=True,
    required=True,
)

from lazyops.imports._k8s import (
    AsyncClient,
    AsyncConfig,
    AsyncStream,
    AsyncWatch,
    AsyncUtils,
    AsyncType,
    AsyncWSClient,

    SyncClient,
    SyncConfig,
    SyncStream,
    SyncStreamFunc,

    SyncWatch,
    SyncUtils,
    SyncType,

)