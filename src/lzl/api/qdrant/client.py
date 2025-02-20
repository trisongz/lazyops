from __future__ import annotations

"""
Qdrant Client with Unified Async / Sync 
"""

import abc
import typing as t
from lzl import load
from lzo.types import BaseModel, eproperty, Field
from lzl.logging import logger, null_logger, Logger
from .config import QdrantClientSettings, fastembed, settings as _settings

if t.TYPE_CHECKING:
    import qdrant_client
    from qdrant_client import grpc as grpc
    from qdrant_client.conversions import common_types as ct
    from qdrant_client.http import ApiClient, SyncApis
    from qdrant_client.http import AsyncApiClient, AsyncApis
    from qdrant_client import QdrantClient as SyncQdrantClient, AsyncQdrantClient
    from fastembed.common import OnnxProvider
else:
    qdrant_client = load.LazyLoad('qdrant_client', 'qdrant_client[fastembed]', install_missing = True)

class QdrantSharedConfig(BaseModel):
    """
    The sharded config for Qdrant
    """
    location: t.Optional[str] = None
    url: t.Optional[str] = None
    port: t.Optional[int] = None
    grpc_port: t.Optional[int] = None
    prefer_grpc: t.Optional[bool] = None
    https: t.Optional[bool] = None
    api_key: t.Optional[str] = None
    prefix: t.Optional[str] = None
    timeout: t.Optional[int] = None
    host: t.Optional[str] = None
    path: t.Optional[str] = None
    
    force_disable_check_same_thread: t.Optional[bool] = None
    auth_token_provider: t.Optional[
        t.Union[t.Callable[[], str], t.Callable[[], t.Awaitable[str]]]
    ] = None
    cloud_inference: t.Optional[bool] = None
    check_compatibility: t.Optional[bool] = None
    kwargs: t.Optional[t.Dict[str, t.Any]] = None

    set_model: t.Optional[str] = Field(None, exclude = True)
    set_model_config: t.Optional[t.Dict[str, t.Any]] = Field(default_factory=dict, exclude = True)
    set_sparse_model: t.Optional[str] = Field(None, exclude = True)
    set_sparse_model_config: t.Optional[t.Dict[str, t.Any]] = Field(default_factory=dict, exclude = True)


    @classmethod
    def build(
        cls, 
        c: 'QdrantClient',

        # These are shard with the config
        url: t.Optional[str] = None,
        port: t.Optional[int] = None,
        grpc_port: t.Optional[int] = None,
        prefer_grpc: t.Optional[bool] = None,
        https: t.Optional[bool] = None,
        api_key: t.Optional[str] = None,
        prefix: t.Optional[str] = None,
        timeout: t.Optional[int] = None,
        host: t.Optional[str] = None,
        path: t.Optional[str] = None,

        # These are from the client
        location: t.Optional[str] = None,
        force_disable_check_same_thread: t.Optional[bool] = None,
        grpc_options: t.Optional[t.Dict[str, t.Any]] = None,
        auth_token_provider: t.Optional[
            t.Union[t.Callable[[], str], t.Callable[[], t.Awaitable[str]]]
        ] = None,
        cloud_inference: t.Optional[bool] = None,
        check_compatibility: t.Optional[bool] = None,
        set_model: t.Optional[str] = None,
        set_sparse_model: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> 'QdrantSharedConfig':
        """
        Constructs a shared client config
        """
        new = {
            'url': url if url is not None else c.settings.url,
            'port': port or c.settings.port,
            'grpc_port': grpc_port or c.settings.grpc_port,
            'prefer_grpc': prefer_grpc if prefer_grpc is not None else c.settings.prefer_grpc,
            'https': https if https is not None else c.settings.https,
            'api_key': api_key if api_key is not None else c.settings.api_key,
            'prefix': prefix if prefix is not None else c.settings.prefix,
            'timeout': timeout if timeout is not None else c.settings.timeout,
            'host': host if host is not None else c.settings.host,
            'path': path if path is not None else c.settings.path,
            'location': location,
            'force_disable_check_same_thread': force_disable_check_same_thread,
            'grpc_options': grpc_options,
            'auth_token_provider': auth_token_provider,
            'cloud_inference': cloud_inference,
            'check_compatibility': check_compatibility,
            'set_model': set_model,
            'set_sparse_model': set_sparse_model,
            'kwargs': kwargs,
        }
        new = {k:v for k,v in new.items() if v is not None}
        return cls.model_validate(new, context = {'source': 'build', 'client': c})


ResponseT = t.TypeVar('ResponseT')

class QdrantClient(abc.ABC):
    """
    Entry point to communicate with Qdrant service via REST or gRPC API.

    It combines interface classes and endpoint implementation.
    Additionally, it provides custom implementations for frequently used methods like initial collection upload.

    All methods in QdrantClient accept both gRPC and REST structures as an input.
    Conversion will be performed automatically.

    .. note::
        This module methods are wrappers around generated client code for gRPC and REST methods.
        If you need lower-level access to generated clients, use following properties:

        - :py:attr:`QdrantClient.grpc_points`
        - :py:attr:`QdrantClient.grpc_collections`
        - :py:attr:`QdrantClient.rest`

    Args:
        location:
            If `":memory:"` - use in-memory Qdrant instance.
            If `str` - use it as a `url` parameter.
            If `None` - use default values for `host` and `port`.
        url: either host or str of "Optional[scheme], host, Optional[port], Optional[prefix]".
            Default: `None`
        port: Port of the REST API interface. Default: 6333
        grpc_port: Port of the gRPC interface. Default: 6334
        prefer_grpc: If `true` - use gPRC interface whenever possible in custom methods.
        https: If `true` - use HTTPS(SSL) protocol. Default: `None`
        api_key: API key for authentication in Qdrant Cloud. Default: `None`
        prefix:
            If not `None` - add `prefix` to the REST URL path.
            Example: `service/v1` will result in `http://localhost:6333/service/v1/{qdrant-endpoint}` for REST API.
            Default: `None`
        timeout:
            Timeout for REST and gRPC API requests.
            Default: 5 seconds for REST and unlimited for gRPC
        host: Host name of Qdrant service. If url and host are None, set to 'localhost'.
            Default: `None`
        path: Persistence path for QdrantLocal. Default: `None`
        force_disable_check_same_thread:
            For QdrantLocal, force disable check_same_thread. Default: `False`
            Only use this if you can guarantee that you can resolve the thread safety outside QdrantClient.
        auth_token_provider: Callback function to get Bearer access token. If given, the function will be called before each request to get the token.
        check_compatibility: If `true` - check compatibility with the server version. Default: `true`
        set_model: Name of the model to use for encoding documents and queries. Default: `None`
        set_sparse_model: Name of the model to use for hybrid search over documents in combination with dense embeddings. Default: `None`
        **kwargs: Additional arguments passed directly into REST client initialization
    """

    def __init__(
        self,
        location: t.Optional[str] = None,
        url: t.Optional[str] = None,
        port: t.Optional[int] = None,
        grpc_port: t.Optional[int] = None,
        prefer_grpc: t.Optional[bool] = None,
        https: t.Optional[bool] = None,
        api_key: t.Optional[str] = None,
        prefix: t.Optional[str] = None,
        timeout: t.Optional[int] = None,
        host: t.Optional[str] = None,
        path: t.Optional[str] = None,
        force_disable_check_same_thread: bool = False,
        grpc_options: t.Optional[t.Dict[str, t.Any]] = None,
        auth_token_provider: t.Optional[
            t.Union[t.Callable[[], str], t.Callable[[], t.Awaitable[str]]]
        ] = None,
        cloud_inference: bool = False,
        check_compatibility: bool = True,
        set_model: t.Optional[str] = None,
        set_sparse_model: t.Optional[str] = None,
        **kwargs: t.Any,
    ):
        self._extra: t.Dict[str, t.Any] = {}
        self.settings: QdrantClientSettings = _settings
        self.shared_config = QdrantSharedConfig.build(
            self,
            location = location,
            url = url,
            port = port,
            grpc_port = grpc_port,
            prefer_grpc = prefer_grpc,
            https = https,
            api_key = api_key,
            prefix = prefix,
            timeout = timeout,
            host = host,
            path = path,
            force_disable_check_same_thread = force_disable_check_same_thread,
            grpc_options = grpc_options,
            auth_token_provider = auth_token_provider,
            cloud_inference = cloud_inference,
            check_compatibility = check_compatibility,
            set_model = set_model,
            set_sparse_model = set_sparse_model,
            **kwargs,
        )

    """
    Implement interfaces
    """

    @eproperty
    def api(self) -> 'AsyncQdrantClient':
        """
        [Async] Qdrant API client
        """
        _api = qdrant_client.AsyncQdrantClient(
            **self.shared_config.model_dump(exclude_none = True, exclude = {'kwargs'}),
            **self.shared_config.kwargs, 
        )
        if self.shared_config.set_model is not None:
            _api.set_model(self.shared_config.set_model, **self.shared_config.set_model_config)
        if self.shared_config.set_sparse_model is not None:
            _api.set_sparse_model(self.shared_config.set_sparse_model, **self.shared_config.set_sparse_model_config)
        return _api
    
    @property
    def _api_loaded(self) -> bool:
        """
        Returns True if the API is loaded
        """
        return 'api' in self._extra

    @eproperty
    def sapi(self) -> 'SyncQdrantClient':
        """
        [Sync] Qdrant API client
        """
        _api = qdrant_client.QdrantClient(
            **self.shared_config.model_dump(exclude_none = True, exclude = {'kwargs'}),
            **self.shared_config.kwargs, 
        )
        if self.shared_config.set_model is not None:
            _api.set_model(self.shared_config.set_model, **self.shared_config.set_model_config)
        if self.shared_config.set_sparse_model is not None:
            _api.set_sparse_model(self.shared_config.set_sparse_model, **self.shared_config.set_sparse_model_config)
        return _api

    @property
    def _sapi_loaded(self) -> bool:
        """
        Returns True if the SAPI is loaded
        """
        return 'sapi' in self._extra
    
    @t.overload
    def set_model(
        self, 
        embedding_model_name: str,
        max_length: t.Optional[int] = None,
        cache_dir: t.Optional[str] = None,
        threads: t.Optional[int] = None,
        providers: t.Optional[t.Sequence["OnnxProvider"]] = None,
        cuda: bool = False,
        device_ids: t.Optional[t.List[int]] = None,
        lazy_load: bool = False,
        **kwargs: t.Any,
    ) -> None:
        """
        Set embedding model to use for encoding documents and queries.

        Args:
            embedding_model_name: One of the supported embedding models. See `SUPPORTED_EMBEDDING_MODELS` for details.
            max_length (int, optional): Deprecated. Defaults to None.
            cache_dir (str, optional): The path to the cache directory.
                Can be set using the `FASTEMBED_CACHE_PATH` env variable.
                Defaults to `fastembed_cache` in the system's temp directory.
            threads (int, optional): The number of threads single onnxruntime session can use. Defaults to None.
            providers: The list of onnx providers (with or without options) to use. Defaults to None.
                Example configuration:
                https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html#configuration-options
            cuda (bool, optional): Whether to use cuda for inference. Mutually exclusive with `providers`
                Defaults to False.
            device_ids (Optional[list[int]], optional): The list of device ids to use for data parallel processing in
                workers. Should be used with `cuda=True`, mutually exclusive with `providers`. Defaults to None.
            lazy_load (bool, optional): Whether to load the model during class initialization or on demand.
                Should be set to True when using multiple-gpu and parallel encoding. Defaults to False.
        Raises:
            ValueError: If embedding model is not supported.
            ImportError: If fastembed is not installed.
        """
        ...


    def set_model(
        self, 
        embedding_model_name: str,
        **kwargs: t.Any,
    ) -> None:
        self.shared_config.set_model = embedding_model_name
        self.shared_config.set_model_config.update(kwargs)
        if self._api_loaded:
            self.api.set_model(embedding_model_name, **kwargs)
        if self._sapi_loaded:
            self.sapi.set_model(embedding_model_name, **kwargs)
    
    @t.overload
    def set_sparse_model(
        self, 
        embedding_model_name: t.Optional[str] = None,
        cache_dir: t.Optional[str] = None,
        threads: t.Optional[int] = None,
        providers: t.Optional[t.Sequence["OnnxProvider"]] = None,
        cuda: bool = False,
        device_ids: t.Optional[t.List[int]] = None,
        lazy_load: bool = False,
        **kwargs: t.Any,
    ) -> None:
        """
        Set sparse embedding model to use for hybrid search over documents in combination with dense embeddings.

        Args:
            embedding_model_name: One of the supported sparse embedding models. See `SUPPORTED_SPARSE_EMBEDDING_MODELS` for details.
                        If None, sparse embeddings will not be used.
            cache_dir (str, optional): The path to the cache directory.
                                       Can be set using the `FASTEMBED_CACHE_PATH` env variable.
                                       Defaults to `fastembed_cache` in the system's temp directory.
            threads (int, optional): The number of threads single onnxruntime session can use. Defaults to None.
            providers: The list of onnx providers (with or without options) to use. Defaults to None.
                Example configuration:
                https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html#configuration-options
            cuda (bool, optional): Whether to use cuda for inference. Mutually exclusive with `providers`
                Defaults to False.
            device_ids (Optional[list[int]], optional): The list of device ids to use for data parallel processing in
                workers. Should be used with `cuda=True`, mutually exclusive with `providers`. Defaults to None.
            lazy_load (bool, optional): Whether to load the model during class initialization or on demand.
                Should be set to True when using multiple-gpu and parallel encoding. Defaults to False.
        Raises:
            ValueError: If embedding model is not supported.
            ImportError: If fastembed is not installed.

        Returns:
            None
        """
        ...


    def set_sparse_model(
        self, 
        embedding_model_name: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> None:
        if embedding_model_name is not None:
            self.shared_config.set_sparse_model = embedding_model_name
            self.shared_config.set_sparse_model_config.update(kwargs)
            if self._api_loaded:
                self.api.set_sparse_model(embedding_model_name, **kwargs)
            if self._sapi_loaded:
                self.sapi.set_sparse_model(embedding_model_name, **kwargs)
        


    def close(self, grpc_grace: t.Optional[float] = None, **kwargs: t.Any) -> None:
        """Closes the connection to Qdrant

        Args:
            grpc_grace: Grace period for gRPC connection close. Default: None
        """
        if 'sapi' in self._extra:
            self.sapi.close(grpc_grace = grpc_grace, **kwargs)
            del self._extra['sapi']
        
    async def aclose(self, grpc_grace: t.Optional[float] = None, **kwargs: t.Any) -> None:
        """Closes the connection to Qdrant

        Args:
            grpc_grace: Grace period for gRPC connection close. Default: None
        """
        if 'api' in self._extra:
            await self.api.close(grpc_grace = grpc_grace, **kwargs)
            del self._extra['api']
        self.close(grpc_grace = grpc_grace, **kwargs)


    """
    Sync Interfaces
    """

    @property
    def grpc_collections(self) -> 'grpc.CollectionsStub':
        """gRPC client for collections methods

        Returns:
            An instance of raw gRPC client, generated from Protobuf
        """
        return self.sapi.grpc_collections

    @property
    def grpc_points(self) -> 'grpc.PointsStub':
        """gRPC client for points methods

        Returns:
            An instance of raw gRPC client, generated from Protobuf
        """
        return self.sapi.grpc_points

    @property
    def rest(self) -> 'SyncApis[ApiClient]':
        """REST Client

        Returns:
            An instance of raw REST API client, generated from OpenAPI schema
        """
        return self.sapi.rest
    

    @property
    def http(self) -> 'SyncApis[ApiClient]':
        """REST Client

        Returns:
            An instance of raw REST API client, generated from OpenAPI schema
        """
        return self.sapi.http

    @property
    def init_options(self) -> t.Dict[str, t.Any]:
        """`__init__` Options

        Returns:
             A dictionary of options the client class was instantiated with
        """
        return self.sapi._init_options
    
    """
    Async Interfaces
    """

    @property
    def agrpc_collections(self) -> 'grpc.CollectionsStub':
        """gRPC client for collections methods

        Returns:
            An instance of raw gRPC client, generated from Protobuf
        """
        return self.api.grpc_collections

    @property
    def agrpc_points(self) -> 'grpc.PointsStub':
        """gRPC client for points methods

        Returns:
            An instance of raw gRPC client, generated from Protobuf
        """
        return self.api.grpc_points

    @property
    def arest(self) -> 'AsyncApis[AsyncApiClient]':
        """REST Client

        Returns:
            An instance of raw REST API client, generated from OpenAPI schema
        """
        return self.api.rest

    @property
    def ahttp(self) -> 'AsyncApis[AsyncApiClient]':
        """REST Client

        Returns:
            An instance of raw REST API client, generated from OpenAPI schema
        """
        return self.api.http

    @property
    def ainit_options(self) -> t.Dict[str, t.Any]:
        """`__init__` Options

        Returns:
             A dictionary of options the client class was instantiated with
        """
        return self.api._init_options
    

    

    # we'll probably want to do the same method as kvdb here later.

    """
    Class Wrap Methods
    """

    def _fx_(self, *args, _fx_: t.Optional[str] = None, **kwargs) -> ResponseT:
        """
        [Sync] Wraps the client function
        """
        return getattr(self.sapi, _fx_)(*args, **kwargs)
    
    def _afx_(self, *args, _fx_: t.Optional[str] = None, **kwargs) -> t.Awaitable[ResponseT]:
        """
        [Async] Wraps the client function
        """
        return getattr(self.api, _fx_)(*args, **kwargs)

    @classmethod
    def __init_client_fx__(cls):
        """
        Initializes the class methods
        and sets them based on both the async and sync methods
        """
        import functools
        import inspect
        from makefun import create_function

        excluded_attrs = {
            'DEFAULT_EMBEDDING_MODEL',
            'embedding_models',
            'embedding_model_name',
            'sparse_embedding_models',
            'sparse_embedding_model_name',
            'late_interaction_embedding_models',
            'image_embedding_models',
            'FASTEMBED_INSTALLED',
        }
        existing_methods = set(dir(cls))
        existing_methods.update(excluded_attrs)

        added_methods = set()
        
        # Sync Methods
        for name in dir(qdrant_client.QdrantClient):
            # print(f"Checking method: {name}")
            if name.startswith('_'): continue
            if name in existing_methods: continue
            # print(f"[Sync] Checking method: {name}")
            # if name in skip_methods: continue
            existing_func = getattr(qdrant_client.QdrantClient, name)
            # if not c
            # if not callable(existing_func): continue
            existing_sig = inspect.signature(existing_func)
            new_func = create_function(
                existing_sig,
                functools.partial(cls._fx_, _fx_ = name),
                func_name = name,
                module_name = cls.__module__,
            )
            setattr(cls, name, new_func)
            existing_methods.add(name)
            added_methods.add(name)
            # print(f"[Sync] Added method: {name}")

        # Async Methods
        for name in dir(qdrant_client.AsyncQdrantClient):
            # print(f"Checking async method: {name}")
            if name.startswith('_'): continue
            aname = f'a{name}'
            if aname in {
                'async', 'await'
            }: aname = f'{aname}_' 
            if aname in existing_methods or name in excluded_attrs: continue
            # print(f"[Async] Checking async method: {name}")
            existing_func = getattr(qdrant_client.AsyncQdrantClient, name)
            # if not callable(existing_func): continue
            existing_sig = inspect.signature(existing_func)
            try:
                new_func = create_function(
                    existing_sig,
                    functools.partial(cls._afx_, _fx_ = name),
                    func_name = aname,
                    module_name = cls.__module__,
                )
                setattr(cls, aname, new_func)
                existing_methods.add(aname)
                added_methods.add(aname)
                # print(f"[Async] Added async method: {name} -> {aname}")
            except Exception as e:
                # print(f"Error adding method: {name} -> {aname}")
                raise e
        
# stubgen --inspect-mode --include-private --include-docstrings client_v2.py 
# stubgen --inspect-mode --include-docstrings --include-private --ignore-errors -m lzl.api.qdrant.client
QdrantClient.__init_client_fx__()