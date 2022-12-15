"""
Import Handler for `kubernetes`, `kubernetes_asyncio`, `kopf`
"""

try:

    import kubernetes.client as SyncClient
    import kubernetes.config as SyncConfig
    import kubernetes.stream.ws_client as SyncStream
    import kubernetes.stream.stream as SyncStreamFunc
    
    import kubernetes.watch as SyncWatch
    import kubernetes.utils as SyncUtils
    import kubernetes.client.models as SyncType

    _k8_available = True

except ImportError:
    SyncClient = object
    SyncConfig = object
    SyncStream = object
    SyncStreamFunc = object

    SyncWatch = object
    SyncUtils = object
    SyncType = object

    _k8_available = False

try:
    import kubernetes_asyncio.client as AsyncClient
    import kubernetes_asyncio.config as AsyncConfig
    import kubernetes_asyncio.stream as AsyncStream
    import kubernetes_asyncio.watch as AsyncWatch
    import kubernetes_asyncio.utils as AsyncUtils
    import kubernetes_asyncio.client.models as AsyncType

    AsyncWSClient = AsyncStream.WsApiClient

    _async_k8_available = True

except ImportError:
    AsyncClient = object
    AsyncConfig = object
    AsyncStream = object
    AsyncWatch = object
    AsyncUtils = object
    AsyncType = object
    AsyncWSClient = object

    _async_k8_available = False

try:
    import kopf
    _kopf_available = True

except ImportError:
    kopf = object
    _kopf_available = False


from gexai.libs.imports.base import resolve_missing, require_missing_wrapper

def resolve_sync_k8s(
    required: bool = True,
):
    """
    Ensures that `kubernetes` is availableable
    """
    global _k8_available
    global SyncClient, SyncConfig, SyncStream, SyncWatch, SyncUtils, SyncType, SyncStreamFunc

    if not _k8_available:
        resolve_missing('kubernetes', required = required)
        import kubernetes.client as SyncClient
        import kubernetes.config as SyncConfig
        import kubernetes.stream.ws_client as SyncStream
        import kubernetes.stream.stream as SyncStreamFunc
        import kubernetes.watch as SyncWatch
        import kubernetes.utils as SyncUtils
        import kubernetes.client.models as SyncType        

        _k8_available = True

def resolve_async_k8s(
    required: bool = True,
):
    """
    Ensures that `kubernetes_asyncio` is availableable
    """
    global _async_k8_available
    global AsyncClient, AsyncConfig, AsyncStream, AsyncWatch, AsyncUtils, AsyncType, AsyncWSClient
    if not _async_k8_available:
        resolve_missing('kubernetes_asyncio', required = required)
        import kubernetes_asyncio.client as AsyncClient
        import kubernetes_asyncio.config as AsyncConfig
        import kubernetes_asyncio.stream as AsyncStream
        import kubernetes_asyncio.watch as AsyncWatch
        import kubernetes_asyncio.utils as AsyncUtils
        import kubernetes_asyncio.client.models as AsyncType
        AsyncWSClient = AsyncStream.WsApiClient

        _async_k8_available = True

def resolve_kopf(
    required: bool = True,
):
    """
    Ensures that `kopf`
    """
    global _kopf_available
    global kopf

    if not _kopf_available:
        resolve_missing('kopf', required = required)
        import kopf
        _kopf_available = True

def resolve_k8s(
    is_sync: bool = False,
    is_async: bool = True,
    is_operator: bool = False,
    required: bool = True,
):
    """
    Ensures that `kubernetes`, `kubernetes_asyncio`, `kopf` are availableable
    """
    if is_operator:
        resolve_kopf(required = required)
    if is_async:
        resolve_async_k8s(required = required)
    if is_sync or not is_async:
        resolve_sync_k8s(required = required)


def require_k8s(
    is_sync: bool = False,
    is_async: bool = True,
    is_operator: bool = False,
    required: bool = True,
):
    """
    Wrapper for `resolve_k8s` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_k8s, 
            func = func, 
            is_sync = is_sync,
            is_async = is_async, 
            is_operator = is_operator,
            required = required
        )
    return decorator