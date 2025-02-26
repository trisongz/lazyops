from __future__ import annotations

"""
Qdrant Client with Unified Async / Sync 
"""

import abc
import typing as t
from lzl import load
from lzo.types import BaseModel, eproperty, Field
from lzl.logging import logger, null_logger, Logger
from .config import QdrantSharedConfig, QdrantClientSettings, fastembed, settings as _settings

if t.TYPE_CHECKING:
    import httpx
    import stamina
    import qdrant_client
    import qdrant_client.http.exceptions
    from qdrant_client import grpc as grpc
    from qdrant_client.conversions import common_types as ct
    from qdrant_client.http import ApiClient, SyncApis, models
    from qdrant_client.http import AsyncApiClient, AsyncApis
    from qdrant_client.http.api_client import SendAsync, Send
    from qdrant_client import QdrantClient as SyncQdrantClient, AsyncQdrantClient
    from qdrant_client.fastembed_common import QueryResponse
    from fastembed.common import OnnxProvider
else:
    httpx = load.LazyLoad('httpx', install_missing = True)
    stamina = load.LazyLoad('stamina', install_missing = True)
    qdrant_client = load.LazyLoad('qdrant_client', 'qdrant_client[fastembed]', install_missing = True)


def retry_context_maker(
    retries: int,
    is_async: bool,
    **kwargs,
):
    """
    Creates a context manager for retrying an asynchronous function.
    """
    def is_retryable_error(exc: Exception | 'httpx.HTTPError' | 'qdrant_client.http.exceptions.ResponseHandlingException'):
        """
        Checks if the error is retryable.
        """
        if isinstance(exc, httpx.ReadTimeout): return True
        if 'nodename nor servname provided, or not known' in str(exc): return True
        return isinstance(exc, qdrant_client.http.exceptions.ResponseHandlingException)
        

    if is_async:
        async def retry_middleware(request: 'httpx.Request', call_next: 'SendAsync') -> 'httpx.Response':
            """
            Middleware that retries requests if they are being rate limited.
            """
            async for attempt in stamina.retry_context(
                attempts = retries,
                on = is_retryable_error,
            ):
                with attempt:
                    response = await call_next(request)
                    response.raise_for_status()
                    return response
    else:
        def retry_middleware(request: 'httpx.Request', call_next: 'Send') -> 'httpx.Response':
            """
            Middleware that retries requests if they are being rate limited.
            """
            for attempt in stamina.retry_context(
                attempts = retries,
                on = is_retryable_error,
            ):
                with attempt:
                    response = call_next(request)
                    response.raise_for_status()
                    return response

    return retry_middleware





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
        retries: Number of times to retry a failed request. Default: `None`
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
        settings: t.Optional[QdrantClientSettings] = None,
        mute_httpx: t.Optional[bool] = True,
        retries: t.Optional[int] = None,
        **kwargs: t.Any,
    ):
        self._extra: t.Dict[str, t.Any] = {}
        self.settings = settings or _settings
        if mute_httpx:
            from lzl.api.aiohttpx.utils.logs import mute_httpx_logger
            mute_httpx_logger()
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
            retries = retries,
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
            **self.shared_config.model_dump(exclude_none = True),
            **self.shared_config.kwargs, 
        )
        if self.shared_config.set_model is not None:
            _api.set_model(self.shared_config.set_model, **self.shared_config.set_model_config)
        if self.shared_config.set_sparse_model is not None:
            _api.set_sparse_model(self.shared_config.set_sparse_model, **self.shared_config.set_sparse_model_config)
        if self.shared_config.retries:
            _api.http.client.add_middleware(
                retry_context_maker(
                    retries = self.shared_config.retries,
                    is_async = True,
                )
            )
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
            **self.shared_config.model_dump(exclude_none = True),
            **self.shared_config.kwargs, 
        )
        if self.shared_config.set_model is not None:
            _api.set_model(self.shared_config.set_model, **self.shared_config.set_model_config)
        if self.shared_config.set_sparse_model is not None:
            _api.set_sparse_model(self.shared_config.set_sparse_model, **self.shared_config.set_sparse_model_config)
        if self.shared_config.retries:
            _api.http.client.add_middleware(
                retry_context_maker(
                    retries = self.shared_config.retries,
                    is_async = False,
                )
            )
        return _api

    @property
    def _sapi_loaded(self) -> bool:
        """
        Returns True if the SAPI is loaded
        """
        return 'sapi' in self._extra
    
    @eproperty
    def models(self):
        """
        Returns the models module
        """
        from qdrant_client.http import models
        return models

    
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
    Child Methods
    """

    @t.overload
    def add(
        self,
        collection_name: str,
        documents: t.Iterable[str],
        metadata: t.Optional[t.Iterable[dict[str, t.Any]]] = None,
        ids: t.Optional[t.Iterable['models.ExtendedPointId']] = None,
        batch_size: int = 32,
        parallel: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> list[t.Union[str, int]]:
        """
        Adds text documents into qdrant collection.
        If collection does not exist, it will be created with default parameters.
        Metadata in combination with documents will be added as payload.
        Documents will be embedded using the specified embedding model.

        If you want to use your own vectors, use `upsert` method instead.

        Args:
            collection_name (str):
                Name of the collection to add documents to.
            documents (Iterable[str]):
                List of documents to embed and add to the collection.
            metadata (Iterable[dict[str, Any]], optional):
                List of metadata dicts. Defaults to None.
            ids (Iterable[models.ExtendedPointId], optional):
                List of ids to assign to documents.
                If not specified, UUIDs will be generated. Defaults to None.
            batch_size (int, optional):
                How many documents to embed and upload in single request. Defaults to 32.
            parallel (Optional[int], optional):
                How many parallel workers to use for embedding. Defaults to None.
                If number is specified, data-parallel process will be used.

        Raises:
            ImportError: If fastembed is not installed.

        Returns:
            List of IDs of added documents. If no ids provided, UUIDs will be randomly generated on client side.

        """
        ...

    def add(
        self,
        collection_name: str,
        documents: t.Iterable[str],
        **kwargs: t.Any,
    ) -> list[t.Union[str, int]]:
        return self.sapi.add(collection_name = collection_name, documents = documents, **kwargs)

    @t.overload
    async def aadd(
        self,
        collection_name: str,
        documents: t.Iterable[str],
        metadata: t.Optional[t.Iterable[dict[str, t.Any]]] = None,
        ids: t.Optional[t.Iterable['models.ExtendedPointId']] = None,
        batch_size: int = 32,
        parallel: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> list[t.Union[str, int]]:
        """
        Adds text documents into qdrant collection.
        If collection does not exist, it will be created with default parameters.
        Metadata in combination with documents will be added as payload.
        Documents will be embedded using the specified embedding model.

        If you want to use your own vectors, use `upsert` method instead.

        Args:
            collection_name (str):
                Name of the collection to add documents to.
            documents (Iterable[str]):
                List of documents to embed and add to the collection.
            metadata (Iterable[dict[str, Any]], optional):
                List of metadata dicts. Defaults to None.
            ids (Iterable[models.ExtendedPointId], optional):
                List of ids to assign to documents.
                If not specified, UUIDs will be generated. Defaults to None.
            batch_size (int, optional):
                How many documents to embed and upload in single request. Defaults to 32.
            parallel (Optional[int], optional):
                How many parallel workers to use for embedding. Defaults to None.
                If number is specified, data-parallel process will be used.

        Raises:
            ImportError: If fastembed is not installed.

        Returns:
            List of IDs of added documents. If no ids provided, UUIDs will be randomly generated on client side.

        """
        ...
    
    async def aadd(
        self,
        collection_name: str,
        documents: t.Iterable[str],
        **kwargs: t.Any,
    ) -> list[t.Union[str, int]]:
        return await self.api.add(
            collection_name=collection_name,
            documents=documents,
            **kwargs,
        )

    @t.overload
    def query(
        self,
        collection_name: str,
        query_text: str,
        query_filter: t.Optional['models.Filter'] = None,
        limit: int = 10,
        **kwargs: t.Any,
    ) -> t.List['QueryResponse']:
        """
        Search for documents in a collection.
        This method automatically embeds the query text using the specified embedding model.
        If you want to use your own query vector, use `search` method instead.

        Args:
            collection_name: Collection to search in
            query_text:
                Text to search for. This text will be embedded using the specified embedding model.
                And then used as a query vector.
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            limit: How many results return
            **kwargs: Additional search parameters. See `qdrant_client.models.SearchRequest` for details.

        Returns:
            list[types.ScoredPoint]: List of scored points.

        """
        ...
    
    def query(
        self,
        collection_name: str,
        query_text: str,
        **kwargs: t.Any,
    ) -> t.List['QueryResponse']:
        return self.sapi.query(
            collection_name=collection_name,
            query_text=query_text,
            **kwargs,
        )

    @t.overload
    async def aquery(
        self,
        collection_name: str,
        query_text: str,
        query_filter: t.Optional['models.Filter'] = None,
        limit: int = 10,
        **kwargs: t.Any,
    ) -> t.List['QueryResponse']:
        """
        Search for documents in a collection.
        This method automatically embeds the query text using the specified embedding model.
        If you want to use your own query vector, use `search` method instead.

        Args:
            collection_name: Collection to search in
            query_text:
                Text to search for. This text will be embedded using the specified embedding model.
                And then used as a query vector.
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            limit: How many results return
            **kwargs: Additional search parameters. See `qdrant_client.models.SearchRequest` for details.

        Returns:
            list[types.ScoredPoint]: List of scored points.

        """
        ...
    
    async def aquery(
        self,
        collection_name: str,
        query_text: str,
        **kwargs: t.Any,
    ) -> t.List['QueryResponse']:
        return await self.api.query(
            collection_name=collection_name,
            query_text=query_text,
            **kwargs,
        )
    
    @t.overload
    def query_batch(
        self,
        collection_name: str,
        query_texts: list[str],
        query_filter: t.Optional['models.Filter'] = None,
        limit: int = 10,
        **kwargs: t.Any,
    ) -> list[list['QueryResponse']]:
        """
        Search for documents in a collection with batched query.
        This method automatically embeds the query text using the specified embedding model.

        Args:
            collection_name: Collection to search in
            query_texts:
                A list of texts to search for. Each text will be embedded using the specified embedding model.
                And then used as a query vector for a separate search requests.
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
                This filter will be applied to all search requests.
            limit: How many results return
            **kwargs: Additional search parameters. See `qdrant_client.models.SearchRequest` for details.

        Returns:
            list[list[QueryResponse]]: List of lists of responses for each query text.

        """
        ...
    
    def query_batch(
        self,
        collection_name: str,
        query_texts: list[str],
        **kwargs: t.Any,
    ) -> list[list['QueryResponse']]:
        return self.sapi.query_batch(
            collection_name=collection_name,
            query_texts=query_texts,
            **kwargs,
        )
    
    @t.overload
    async def aquery_batch(
        self,
        collection_name: str,
        query_texts: list[str],
        query_filter: t.Optional['models.Filter'] = None,
        limit: int = 10,
        **kwargs: t.Any,
    ) -> list[list['QueryResponse']]:
        """
        Search for documents in a collection with batched query.
        This method automatically embeds the query text using the specified embedding model.

        Args:
            collection_name: Collection to search in
            query_texts:
                A list of texts to search for. Each text will be embedded using the specified embedding model.
                And then used as a query vector for a separate search requests.
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
                This filter will be applied to all search requests.
            limit: How many results return
            **kwargs: Additional search parameters. See `qdrant_client.models.SearchRequest` for details.

        Returns:
            list[list[QueryResponse]]: List of lists of responses for each query text.

        """
        ...

    async def aquery_batch(
        self,
        collection_name: str,
        query_texts: list[str],
        **kwargs: t.Any,
    ) -> list[list['QueryResponse']]:
        return await self.api.query_batch(
            collection_name=collection_name,
            query_texts=query_texts,
            **kwargs,
        )
    


    @t.overload
    def get_fastembed_vector_params(
        self,
        on_disk: t.Optional[bool] = None,
        quantization_config: t.Optional['models.QuantizationConfig'] = None,
        hnsw_config: t.Optional['models.HnswConfigDiff'] = None,
    ) -> dict[str, 'models.VectorParams']:
        """
        Generates vector configuration, compatible with fastembed models.

        Args:
            on_disk: if True, vectors will be stored on disk. If None, default value will be used.
            quantization_config: Quantization configuration. If None, quantization will be disabled.
            hnsw_config: HNSW configuration. If None, default configuration will be used.

        Returns:
            Configuration for `vectors_config` argument in `create_collection` method.
        """
        ...
    
    def get_fastembed_vector_params(
        self,
        **kwargs: t.Any,
    ) -> dict[str, 'models.VectorParams']:
        if self._api_loaded:
            return self.api.get_fastembed_vector_params(**kwargs)
        return self.sapi.get_fastembed_vector_params(**kwargs)


    @t.overload
    def get_fastembed_sparse_vector_params(
        self,
        on_disk: t.Optional[bool] = None,
        modifier: t.Optional['models.Modifier'] = None,
    ) -> t.Optional[dict[str, 'models.SparseVectorParams']]:
        """
        Generates vector configuration, compatible with fastembed sparse models.

        Args:
            on_disk: if True, vectors will be stored on disk. If None, default value will be used.
            modifier: Sparse vector queries modifier. E.g. Modifier.IDF for idf-based rescoring. Default: None.
        Returns:
            Configuration for `vectors_config` argument in `create_collection` method.
        """
        ...
    
    def get_fastembed_sparse_vector_params(
        self,
        **kwargs: t.Any,
    ) -> t.Optional[dict[str, 'models.SparseVectorParams']]:
        if self._api_loaded:
            return self.api.get_fastembed_sparse_vector_params(**kwargs)
        return self.sapi.get_fastembed_sparse_vector_params(**kwargs)


    """
    Methods
    """

    @t.overload
    def search_batch(
        self,
        collection_name: str,
        requests: t.Sequence['ct.SearchRequest'],
        timeout: t.Optional[int] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        **kwargs: t.Any,
    ) -> t.List[t.List['ct.ScoredPoint']]:
        """Perform multiple searches in a collection mitigating network overhead

        Args:
            collection_name: Name of the collection
            requests: List of search requests
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of search responses
        """
        ...

    def search_batch(
        self,
        collection_name: str,
        requests: t.Sequence['ct.SearchRequest'],
        **kwargs,
    ) -> t.List[t.List['ct.ScoredPoint']]:
        return self.sapi.search_batch(
            collection_name = collection_name, requests = requests, **kwargs
        )
    

    @t.overload
    async def asearch_batch(
        self,
        collection_name: str,
        requests: t.Sequence['ct.SearchRequest'],
        timeout: t.Optional[int] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        **kwargs: t.Any,
    ) -> t.List[t.List['ct.ScoredPoint']]:
        """Perform multiple searches in a collection mitigating network overhead

        Args:
            collection_name: Name of the collection
            requests: List of search requests
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of search responses
        """
        ...

    async def asearch_batch(
        self,
        collection_name: str,
        requests: t.Sequence['ct.SearchRequest'],
        **kwargs: t.Any,
    ) -> t.List[t.List['ct.ScoredPoint']]:
        return await self.api.search_batch(
            collection_name = collection_name,
            requests = requests,
            **kwargs,
        )
    
    @t.overload
    def search(
        self,
        collection_name: str,
        query_vector: t.Union[
            t.Sequence[float],
            t.Tuple[str, t.List[float]],
            'ct.NamedVector',
            'ct.NamedSparseVector',
            'ct.NumpyArray',
        ],
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        offset: t.Optional[int] = None,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        score_threshold: t.Optional[float] = None,
        append_payload: bool = True,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.ScoredPoint']:
        """Search for closest vectors in collection taking into account filtering conditions

        Args:
            collection_name: Collection to search in
            query_vector:
                Search for vectors closest to this.
                Can be either a vector itself, or a named vector, or a named sparse vector, or a tuple of vector name and vector itself
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            search_params: Additional search params
            limit: How many results return
            offset:
                Offset of the first result to return.
                May be used to paginate results.
                Note: large offset values may cause performance issues.
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - include only specified fields
                - Default: `False`
            score_threshold:
                Define a minimal score threshold for the result.
                If defined, less similar results will not be returned.
                Score of the returned result might be higher or smaller than the threshold depending
                on the Distance function used.
                E.g. for cosine similarity only higher scores will be returned.
            append_payload: Same as `with_payload`. Deprecated.
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Examples:

        `Search with filter`::

            qdrant.search(
                collection_name="test_collection",
                query_vector=[1.0, 0.1, 0.2, 0.7],
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key='color',
                            range=Match(
                                value="red"
                            )
                        )
                    ]
                )
            )

        Returns:
            List of found close points with similarity scores.
        """
        ...

    def search(
        self,
        collection_name: str,
        query_vector: t.Union[
            t.Sequence[float],
            t.Tuple[str, t.List[float]],
            'ct.NamedVector',
            'ct.NamedSparseVector',
            'ct.NumpyArray',
        ],
        **kwargs: t.Any,
    ) -> t.List['ct.ScoredPoint']:
        return self.sapi.search(
            collection_name = collection_name,
            query_vector = query_vector,
            **kwargs,
        )
    
    @t.overload
    async def asearch(
        self,
        collection_name: str,
        query_vector: t.Union[
            t.Sequence[float],
            t.Tuple[str, t.List[float]],
            'ct.NamedVector',
            'ct.NamedSparseVector',
            'ct.NumpyArray',
        ],
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        offset: t.Optional[int] = None,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        score_threshold: t.Optional[float] = None,
        append_payload: bool = True,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.ScoredPoint']:
        """Search for closest vectors in collection taking into account filtering conditions

        Args:
            collection_name: Collection to search in
            query_vector:
                Search for vectors closest to this.
                Can be either a vector itself, or a named vector, or a named sparse vector, or a tuple of vector name and vector itself
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            search_params: Additional search params
            limit: How many results return
            offset:
                Offset of the first result to return.
                May be used to paginate results.
                Note: large offset values may cause performance issues.
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - include only specified fields
                - Default: `False`
            score_threshold:
                Define a minimal score threshold for the result.
                If defined, less similar results will not be returned.
                Score of the returned result might be higher or smaller than the threshold depending
                on the Distance function used.
                E.g. for cosine similarity only higher scores will be returned.
            append_payload: Same as `with_payload`. Deprecated.
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Examples:

        `Search with filter`::

            qdrant.search(
                collection_name="test_collection",
                query_vector=[1.0, 0.1, 0.2, 0.7],
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key='color',
                            range=Match(
                                value="red"
                            )
                        )
                    ]
                )
            )

        Returns:
            List of found close points with similarity scores.
        """
        ...
    

    async def asearch(
        self,
        collection_name: str,
        query_vector: t.Union[
            t.Sequence[float],
            t.Tuple[str, t.List[float]],
            'ct.NamedVector',
            'ct.NamedSparseVector',
            'ct.NumpyArray',
        ],
        **kwargs: t.Any,
    ) -> t.List['ct.ScoredPoint']:
        return await self.api.search(
            collection_name = collection_name,
            query_vector = query_vector,
            **kwargs,
        )
    
    @t.overload
    def query_batch_points(
        self,
        collection_name: str,
        requests: t.Sequence['ct.QueryRequest'],
        consistency: t.Optional['ct.ReadConsistency'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.QueryResponse']:
        """Perform any search, recommend, discovery, context search operations in batch, and mitigate network overhead

        Args:
            collection_name: Name of the collection
            requests: List of query requests
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of query responses
        """
        ...
    
    def query_batch_points(
        self,
        collection_name: str,
        requests: t.Sequence['ct.QueryRequest'],
        **kwargs: t.Any,
    ) -> t.List['ct.QueryResponse']:
        return self.sapi.query_batch_points(
            collection_name = collection_name,
            requests = requests,
            **kwargs,
        )
    
    @t.overload
    async def aquery_batch_points(
        self,
        collection_name: str,
        requests: t.Sequence['ct.QueryRequest'],
        consistency: t.Optional['ct.ReadConsistency'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.QueryResponse']:
        """Perform any search, recommend, discovery, context search operations in batch, and mitigate network overhead

        Args:
            collection_name: Name of the collection
            requests: List of query requests
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of query responses
        """
        ...
    
    async def aquery_batch_points(
        self,
        collection_name: str,
        requests: t.Sequence['ct.QueryRequest'],
        **kwargs: t.Any,
    ) -> t.List['ct.QueryResponse']:
        return await self.api.query_batch_points(
            collection_name = collection_name,
            requests = requests,
            **kwargs,
        )
    
    @t.overload
    def query_points(
        self,
        collection_name: str,
        query: t.Union[
            'ct.PointId',
            t.List[float],
            t.List[t.List[float]],
            'ct.SparseVector',
            'ct.Query',
            'ct.NumpyArray',
            'ct.Document',
            'ct.Image',
            'ct.InferenceObject',
            None,
        ] = None,
        using: t.Optional[str] = None,
        prefetch: t.Union['ct.Prefetch', t.List['ct.Prefetch'], None] = None,
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        offset: t.Optional[int] = None,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        score_threshold: t.Optional[float] = None,
        lookup_from: t.Optional['ct.LookupLocation'] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> 'ct.QueryResponse':
        """Universal endpoint to run any available operation, such as search, recommendation, discovery, context search.

        
        Args:
            collection_name: Collection to search in
            query:
                Query for the chosen search type operation.
                - If `str` - use string as UUID of the existing point as a search query.
                - If `int` - use integer as ID of the existing point as a search query.
                - If `list[float]` - use as a dense vector for nearest search.
                - If `list[list[float]]` - use as a multi-vector for nearest search.
                - If `SparseVector` - use as a sparse vector for nearest search.
                - If `Query` - use as a query for specific search type.
                - If `NumpyArray` - use as a dense vector for nearest search.
                - If `Document` - infer vector from the document text and use it for nearest search (requires `fastembed` package installed).
                - If `None` - return first `limit` points from the collection.
            prefetch: prefetch queries to make a selection of the data to be used with the main query
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            search_params: Additional search params
            limit: How many results return
            offset:
                Offset of the first result to return.
                May be used to paginate results.
                Note: large offset values may cause performance issues.
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - include only specified fields
                - Default: `False`
            score_threshold:
                Define a minimal score threshold for the result.
                If defined, less similar results will not be returned.
                Score of the returned result might be higher or smaller than the threshold depending
                on the Distance function used.
                E.g. for cosine similarity only higher scores will be returned.
            using:
                Name of the vectors to use for query.
                If `None` - use default vectors or provided in named vector structures.
            lookup_from:
                Defines a location (collection and vector field name), used to lookup vectors for recommendations,
                    discovery and context queries.
                If `None` - current collection will be used.
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Examples:

        `Search for closest points with a filter`::

            qdrant.query(
                collection_name="test_collection",
                query=[1.0, 0.1, 0.2, 0.7],
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key='color',
                            range=Match(
                                value="red"
                            )
                        )
                    ]
                )
            )

        Returns:
            QueryResponse structure containing list of found close points with similarity scores.
        """
        ...
    
    def query_points(
        self,
        collection_name: str,
        query: t.Union[
            'ct.PointId',
            t.List[float],
            t.List[t.List[float]],
            'ct.SparseVector',
            'ct.Query',
            'ct.NumpyArray',
            'ct.Document',
            'ct.Image',
            'ct.InferenceObject',
            None,
        ] = None,
        **kwargs: t.Any,
    ) -> 'ct.QueryResponse':
        return self.sapi.query_points(
            collection_name = collection_name,
            query = query,
            **kwargs,
        )
    
    async def aquery_points(
        self,
        collection_name: str,
        query: t.Union[
            'ct.PointId',
            t.List[float],
            t.List[t.List[float]],
            'ct.SparseVector',
            'ct.Query',
            'ct.NumpyArray',
            'ct.Document',
            'ct.Image',
            'ct.InferenceObject',
            None,
        ] = None,
        using: t.Optional[str] = None,
        prefetch: t.Union['ct.Prefetch', t.List['ct.Prefetch'], None] = None,
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        offset: t.Optional[int] = None,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        score_threshold: t.Optional[float] = None,
        lookup_from: t.Optional['ct.LookupLocation'] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> 'ct.QueryResponse':
        """Universal endpoint to run any available operation, such as search, recommendation, discovery, context search.


        Args:
            collection_name: Collection to search in
            query:
                Query for the chosen search type operation.
                - If `str` - use string as UUID of the existing point as a search query.
                - If `int` - use integer as ID of the existing point as a search query.
                - If `list[float]` - use as a dense vector for nearest search.
                - If `list[list[float]]` - use as a multi-vector for nearest search.
                - If `SparseVector` - use as a sparse vector for nearest search.
                - If `Query` - use as a query for specific search type.
                - If `NumpyArray` - use as a dense vector for nearest search.
                - If `Document` - infer vector from the document text and use it for nearest search (requires `fastembed` package installed).
                - If `None` - return first `limit` points from the collection.
            prefetch: prefetch queries to make a selection of the data to be used with the main query
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            search_params: Additional search params
            limit: How many results return
            offset:
                Offset of the first result to return.
                May be used to paginate results.
                Note: large offset values may cause performance issues.
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - include only specified fields
                - Default: `False`
            score_threshold:
                Define a minimal score threshold for the result.
                If defined, less similar results will not be returned.
                Score of the returned result might be higher or smaller than the threshold depending
                on the Distance function used.
                E.g. for cosine similarity only higher scores will be returned.
            using:
                Name of the vectors to use for query.
                If `None` - use default vectors or provided in named vector structures.
            lookup_from:
                Defines a location (collection and vector field name), used to lookup vectors for recommendations,
                    discovery and context queries.
                If `None` - current collection will be used.
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Examples:

        `Search for closest points with a filter`::

            qdrant.aquery(
                collection_name="test_collection",
                query=[1.0, 0.1, 0.2, 0.7],
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key='color',
                            range=Match(
                                value="red"
                            )
                        )
                    ]
                )
            )

        Returns:
            QueryResponse structure containing list of found close points with similarity scores.
        """
        ...

    async def aquery_points(
        self,
        collection_name: str,
        query: t.Union[
            'ct.PointId',
            t.List[float],
            t.List[t.List[float]],
            'ct.SparseVector',
            'ct.Query',
            'ct.NumpyArray',
            'ct.Document',
            'ct.Image',
            'ct.InferenceObject',
            None,
        ] = None,
        **kwargs: t.Any,
    ) -> 'ct.QueryResponse':
        return await self.api.query_points(
            collection_name = collection_name,
            query = query,
            **kwargs,
        )
    
    @t.overload
    def query_points_groups(
        self,
        collection_name: str,
        group_by: str,
        query: t.Union[
            'ct.PointId',
            t.List[float],
            t.List[t.List[float]],
            'ct.SparseVector',
            'ct.Query',
            'ct.NumpyArray',
            'ct.Document',
            'ct.Image',
            'ct.InferenceObject',
            None,
        ] = None,
        using: t.Optional[str] = None,
        prefetch: t.Union['ct.Prefetch', t.List['ct.Prefetch'], None] = None,
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        group_size: int = 3,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        score_threshold: t.Optional[float] = None,
        with_lookup: t.Optional['ct.WithLookupInterface'] = None,
        lookup_from: t.Optional['ct.LookupLocation'] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.GroupsResult']:
        """Universal endpoint to group on any available operation, such as search, recommendation, discovery, context search.

        Args:
            collection_name: Collection to search in
            query:
                Query for the chosen search type operation.
                - If `str` - use string as UUID of the existing point as a search query.
                - If `int` - use integer as ID of the existing point as a search query.
                - If `list[float]` - use as a dense vector for nearest search.
                - If `list[list[float]]` - use as a multi-vector for nearest search.
                - If `SparseVector` - use as a sparse vector for nearest search.
                - If `Query` - use as a query for specific search type.
                - If `NumpyArray` - use as a dense vector for nearest search.
                - If `Document` - infer vector from the document text and use it for nearest search (requires `fastembed` package installed).
                - If `None` - return first `limit` points from the collection.
            prefetch: prefetch queries to make a selection of the data to be used with the main query
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            search_params: Additional search params
            limit: How many results return
            group_size: How many results return for each group
            group_by: Name of the payload field to group by. Field must be of type "keyword" or "integer".
                Nested fields are specified using dot notation, e.g. "nested_field.subfield".
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - include only specified fields
                - Default: `False`
            score_threshold:
                Define a minimal score threshold for the result.
                If defined, less similar results will not be returned.
                Score of the returned result might be higher or smaller than the threshold depending
                on the Distance function used.
                E.g. for cosine similarity only higher scores will be returned.
            using:
                Name of the vectors to use for query.
                If `None` - use default vectors or provided in named vector structures.
            with_lookup:
                Look for points in another collection using the group ids.
                If specified, each group will contain a record from the specified collection
                with the same id as the group id. In addition, the parameter allows to specify
                which parts of the record should be returned, like in `with_payload` and `with_vectors` parameters.
            lookup_from:
                Defines a location (collection and vector field name), used to lookup vectors being referenced in the query as IDs.
                If `None` - current collection will be used.
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Examples:

        `Search for closest points and group results`::

            qdrant.query_points_groups(
                collection_name="test_collection",
                query=[1.0, 0.1, 0.2, 0.7],
                group_by="color",
                group_size=3,
            )

         Returns:
            List of groups with not more than `group_size` hits in each group.
            Each group also contains an id of the group, which is the value of the payload field.
        """
        ...

    def query_points_groups(
        self,
        collection_name: str,
        group_by: str,
        **kwargs: t.Any,
    ) -> t.List['ct.GroupsResult']:
        return self.sapi.query_points_groups(
            collection_name = collection_name,
            group_by = group_by,
            **kwargs,
        )
    
    @t.overload
    async def aquery_points_groups(
        self,
        collection_name: str,
        group_by: str,
        query: t.Union[
            'ct.PointId',
            t.List[float],
            t.List[t.List[float]],
            'ct.SparseVector',
            'ct.Query',
            'ct.NumpyArray',
            'ct.Document',
            'ct.Image',
            'ct.InferenceObject',
            None,
        ] = None,
        using: t.Optional[str] = None,
        prefetch: t.Union['ct.Prefetch', t.List['ct.Prefetch'], None] = None,
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        group_size: int = 3,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        score_threshold: t.Optional[float] = None,
        with_lookup: t.Optional['ct.WithLookupInterface'] = None,
        lookup_from: t.Optional['ct.LookupLocation'] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.GroupsResult']:
        """Universal endpoint to group on any available operation, such as search, recommendation, discovery, context search.

        Args:
            collection_name: Collection to search in
            query:
                Query for the chosen search type operation.
                - If `str` - use string as UUID of the existing point as a search query.
                - If `int` - use integer as ID of the existing point as a search query.
                - If `list[float]` - use as a dense vector for nearest search.
                - If `list[list[float]]` - use as a multi-vector for nearest search.
                - If `SparseVector` - use as a sparse vector for nearest search.
                - If `Query` - use as a query for specific search type.
                - If `NumpyArray` - use as a dense vector for nearest search.
                - If `Document` - infer vector from the document text and use it for nearest search (requires `fastembed` package installed).
                - If `None` - return first `limit` points from the collection.
            prefetch: prefetch queries to make a selection of the data to be used with the main query
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            search_params: Additional search params
            limit: How many results return
            group_size: How many results return for each group
            group_by: Name of the payload field to group by. Field must be of type "keyword" or "integer".
                Nested fields are specified using dot notation, e.g. "nested_field.subfield".
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - include only specified fields
                - Default: `False`
            score_threshold:
                Define a minimal score threshold for the result.
                If defined, less similar results will not be returned.
                Score of the returned result might be higher or smaller than the threshold depending
                on the Distance function used.
                E.g. for cosine similarity only higher scores will be returned.
            using:
                Name of the vectors to use for query.
                If `None` - use default vectors or provided in named vector structures.
            with_lookup:
                Look for points in another collection using the group ids.
                If specified, each group will contain a record from the specified collection
                with the same id as the group id. In addition, the parameter allows to specify
                which parts of the record should be returned, like in `with_payload` and `with_vectors` parameters.
            lookup_from:
                Defines a location (collection and vector field name), used to lookup vectors being referenced in the query as IDs.
                If `None` - current collection will be used.
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Examples:

        `Search for closest points and group results`::

            qdrant.query_points_groups(
                collection_name="test_collection",
                query=[1.0, 0.1, 0.2, 0.7],
                group_by="color",
                group_size=3,
            )

         Returns:
            List of groups with not more than `group_size` hits in each group.
            Each group also contains an id of the group, which is the value of the payload field.
        """
        ...

    async def aquery_points_groups(
        self,
        collection_name: str,
        group_by: str,
        **kwargs: t.Any,
    ) -> t.List['ct.GroupsResult']:
        return await self.api.query_points_groups(
            collection_name = collection_name,
            group_by = group_by,
            **kwargs,
        )
    
    @t.overload
    def search_groups(
        self,
        collection_name: str,
        query_vector: t.Union[
            t.Sequence[float],
            t.Tuple[str, t.List[float]],
            'ct.NamedVector',
            'ct.NamedSparseVector',
            'ct.NumpyArray',
        ],
        group_by: str,
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        group_size: int = 1,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        score_threshold: t.Optional[float] = None,
        with_lookup: t.Optional['ct.WithLookupInterface'] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.GroupsResult']:
        """Search for closest vectors grouped by payload field.

        Searches best matches for query vector grouped by the value of payload field.
        Useful to obtain most relevant results for each category, deduplicate results,
        finding the best representation vector for the same entity.

        Args:
            collection_name: Collection to search in
            query_vector:
                Search for vectors closest to this.
                Can be either a vector itself, or a named vector, or a named sparse vector, or a tuple of vector name and vector itself
            group_by: Name of the payload field to group by.
                Field must be of type "keyword" or "integer".
                Nested fields are specified using dot notation, e.g. "nested_field.subfield".
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            search_params: Additional search params
            limit: How many groups return
            group_size: How many results return for each group
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - include only specified fields
                - Default: `False`
            score_threshold: Minimal score threshold for the result.
                If defined, less similar results will not be returned.
                Score of the returned result might be higher or smaller than the threshold depending
                on the Distance function used.
                E.g. for cosine similarity only higher scores will be returned.
            with_lookup:
                Look for points in another collection using the group ids.
                If specified, each group will contain a record from the specified collection
                with the same id as the group id. In addition, the parameter allows to specify
                which parts of the record should be returned, like in `with_payload` and `with_vectors` parameters.
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result.
                Values:
                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of groups with not more than `group_size` hits in each group.
            Each group also contains an id of the group, which is the value of the payload field.
        """
        ...

    def search_groups(
        self,
        collection_name: str,
        query_vector: t.Union[
            t.Sequence[float],
            t.Tuple[str, t.List[float]],
            'ct.NamedVector',
            'ct.NamedSparseVector',
            'ct.NumpyArray',
        ],
        group_by: str,
        **kwargs: t.Any,
    ) -> t.List['ct.GroupsResult']:
        return self.sapi.search_groups(
            collection_name = collection_name,
            query_vector = query_vector,
            group_by = group_by,
            **kwargs,
        )

    @t.overload
    async def asearch_groups(
        self,
        collection_name: str,
        query_vector: t.Union[
            t.Sequence[float],
            t.Tuple[str, t.List[float]],
            'ct.NamedVector',
            'ct.NamedSparseVector',
            'ct.NumpyArray',
        ],
        group_by: str,
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        group_size: int = 1,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        score_threshold: t.Optional[float] = None,
        with_lookup: t.Optional['ct.WithLookupInterface'] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.GroupsResult']:
        """Search for closest vectors grouped by payload field.

        Searches best matches for query vector grouped by the value of payload field.
        Useful to obtain most relevant results for each category, deduplicate results,
        finding the best representation vector for the same entity.

        Args:
            collection_name: Collection to search in
            query_vector:
                Search for vectors closest to this.
                Can be either a vector itself, or a named vector, or a named sparse vector, or a tuple of vector name and vector itself
            group_by: Name of the payload field to group by.
                Field must be of type "keyword" or "integer".
                Nested fields are specified using dot notation, e.g. "nested_field.subfield".
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            search_params: Additional search params
            limit: How many groups return
            group_size: How many results return for each group
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - include only specified fields
                - Default: `False`
            score_threshold: Minimal score threshold for the result.
                If defined, less similar results will not be returned.
                Score of the returned result might be higher or smaller than the threshold depending
                on the Distance function used.
                E.g. for cosine similarity only higher scores will be returned.
            with_lookup:
                Look for points in another collection using the group ids.
                If specified, each group will contain a record from the specified collection
                with the same id as the group id. In addition, the parameter allows to specify
                which parts of the record should be returned, like in `with_payload` and `with_vectors` parameters.
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result.
                Values:
                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of groups with not more than `group_size` hits in each group.
            Each group also contains an id of the group, which is the value of the payload field.
        """
        ...

    async def asearch_groups(
        self,
        collection_name: str,
        query_vector: t.Union[
            t.Sequence[float],
            t.Tuple[str, t.List[float]],
            'ct.NamedVector',
            'ct.NamedSparseVector',
            'ct.NumpyArray',
        ],
        group_by: str,
        **kwargs: t.Any,
    ) -> t.List['ct.GroupsResult']:
        return await self.api.search_groups(
            collection_name = collection_name,
            query_vector = query_vector,
            group_by = group_by,
            **kwargs,
        )
    
    @t.overload
    def recommend_batch(
        self,
        collection_name: str,
        requests: t.Sequence['ct.RecommendRequest'],
        consistency: t.Optional['ct.ReadConsistency'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List[t.List['ct.ScoredPoint']]:
        """Perform multiple recommend requests in batch mode

        Args:
            collection_name: Name of the collection
            requests: List of recommend requests
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of recommend responses
        """
        ...

    def recommend_batch(
        self,
        collection_name: str,
        requests: t.Sequence['ct.RecommendRequest'],
        **kwargs: t.Any,
    ) -> t.List[t.List['ct.ScoredPoint']]:
        return self.sapi.recommend_batch(
            collection_name = collection_name,
            requests = requests,
            **kwargs,
        )
    
    @t.overload
    async def arecommend_batch(
        self,
        collection_name: str,
        requests: t.Sequence['ct.RecommendRequest'],
        consistency: t.Optional['ct.ReadConsistency'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List[t.List['ct.ScoredPoint']]:
        """Perform multiple recommend requests in batch mode

        Args:
            collection_name: Name of the collection
            requests: List of recommend requests
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of recommend responses
        """
        ...

    async def arecommend_batch(
        self,
        collection_name: str,
        requests: t.Sequence['ct.RecommendRequest'],
        **kwargs: t.Any,
    ) -> t.List[t.List['ct.ScoredPoint']]:
        return await self.api.recommend_batch(
            collection_name = collection_name,
            requests = requests,
            **kwargs,
        )
    
    @t.overload
    def recommend(
        self,
        collection_name: str,
        positive: t.Optional[t.Sequence['ct.RecommendExample']] = None,
        negative: t.Optional[t.Sequence['ct.RecommendExample']] = None,
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        offset: int = 0,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        score_threshold: t.Optional[float] = None,
        using: t.Optional[str] = None,
        lookup_from: t.Optional['ct.LookupLocation'] = None,
        strategy: t.Optional['ct.RecommendStrategy'] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.ScoredPoint']:
        """Recommend points: search for similar points based on already stored in Qdrant examples.

        Provide IDs of the stored points, and Qdrant will perform search based on already existing vectors.
        This functionality is especially useful for recommendation over existing collection of points.

        Args:
            collection_name: Collection to search in
            positive:
                List of stored point IDs or vectors, which should be used as reference for similarity search.
                If there is only one example - this request is equivalent to the regular search with vector of that
                point.
                If there are more than one example, Qdrant will attempt to search for similar to all of them.
                Recommendation for multiple vectors is experimental.
                Its behaviour may change depending on selected strategy.
            negative:
                List of stored point IDs or vectors, which should be dissimilar to the search result.
                Negative examples is an experimental functionality.
                Its behaviour may change depending on selected strategy.
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            search_params: Additional search params
            limit: How many results return
            offset:
                Offset of the first result to return.
                May be used to paginate results.
                Note: large offset values may cause performance issues.
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - include only specified fields
                - Default: `False`
            score_threshold:
                Define a minimal score threshold for the result.
                If defined, less similar results will not be returned.
                Score of the returned result might be higher or smaller than the threshold depending
                on the Distance function used.
                E.g. for cosine similarity only higher scores will be returned.
            using:
                Name of the vectors to use for recommendations.
                If `None` - use default vectors.
            lookup_from:
                Defines a location (collection and vector field name), used to lookup vectors for recommendations.
                If `None` - current collection will be used.
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.
            strategy:
                Strategy to use for recommendation.
                Strategy defines how to combine multiple examples into a recommendation query.
                Possible values:

                - 'average_vector' - calculates average vector of all examples and uses it for search
                - 'best_score' - finds the result which is closer to positive examples and further from negative
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of recommended points with similarity scores.
        """
        ...
    
    def recommend(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.List['ct.ScoredPoint']:
        return self.sapi.recommend(
            collection_name = collection_name,
            **kwargs,
        )

    @t.overload
    async def arecommend(
        self,
        collection_name: str,
        positive: t.Optional[t.Sequence['ct.RecommendExample']] = None,
        negative: t.Optional[t.Sequence['ct.RecommendExample']] = None,
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        offset: int = 0,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        score_threshold: t.Optional[float] = None,
        using: t.Optional[str] = None,
        lookup_from: t.Optional['ct.LookupLocation'] = None,
        strategy: t.Optional['ct.RecommendStrategy'] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.ScoredPoint']:
        """Recommend points: search for similar points based on already stored in Qdrant examples.

        Provide IDs of the stored points, and Qdrant will perform search based on already existing vectors.
        This functionality is especially useful for recommendation over existing collection of points.

        Args:
            collection_name: Collection to search in
            positive:
                List of stored point IDs or vectors, which should be used as reference for similarity search.
                If there is only one example - this request is equivalent to the regular search with vector of that
                point.
                If there are more than one example, Qdrant will attempt to search for similar to all of them.
                Recommendation for multiple vectors is experimental.
                Its behaviour may change depending on selected strategy.
            negative:
                List of stored point IDs or vectors, which should be dissimilar to the search result.
                Negative examples is an experimental functionality.
                Its behaviour may change depending on selected strategy.
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            search_params: Additional search params
            limit: How many results return
            offset:
                Offset of the first result to return.
                May be used to paginate results.
                Note: large offset values may cause performance issues.
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - include only specified fields
                - Default: `False`
            score_threshold:
                Define a minimal score threshold for the result.
                If defined, less similar results will not be returned.
                Score of the returned result might be higher or smaller than the threshold depending
                on the Distance function used.
                E.g. for cosine similarity only higher scores will be returned.
            using:
                Name of the vectors to use for recommendations.
                If `None` - use default vectors.
            lookup_from:
                Defines a location (collection and vector field name), used to lookup vectors for recommendations.
                If `None` - current collection will be used.
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.
            strategy:
                Strategy to use for recommendation.
                Strategy defines how to combine multiple examples into a recommendation query.
                Possible values:

                - 'average_vector' - calculates average vector of all examples and uses it for search
                - 'best_score' - finds the result which is closer to positive examples and further from negative
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of recommended points with similarity scores.
        """
        ...
    
    async def arecommend(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.List['ct.ScoredPoint']:
        return await self.api.recommend(
            collection_name = collection_name,
            **kwargs,
        )
    
    @t.overload
    def search_matrix_pairs(
        self,
        collection_name: str,
        query_filter: t.Optional['ct.Filter'] = None,
        limit: int = 3,
        sample: int = 10,
        using: t.Optional[str] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        timeout: t.Optional[int] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.SearchMatrixPairsResponse']:
        """
        Compute distance matrix for sampled points with a pair-based output format.

        Args:
            collection_name: Name of the collection.
            query_filter: Filter to apply.
            limit: How many neighbors per sample to find.
            sample: How many points to select and search within.
            using: Name of the vectors to use for search. If `None`, use default vectors.
            consistency: Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:
                - int: Number of replicas to query, values should be present in all queried replicas.
                - 'majority': Query all replicas, but return values present in the majority of replicas.
                - 'quorum': Query the majority of replicas, return values present in all of them.
                - 'all': Query all replicas, and return values present in all replicas.
            timeout: Overrides global timeout for this search. Unit is seconds.
            shard_key_selector: This parameter allows specifying which shards should be queried.
                If `None`, query all shards. Only works for collections with the `custom` sharding method.

        Returns:
            Distance matrix using a pair-based encoding.
        """
        ...

    def search_matrix_pairs(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.List['ct.SearchMatrixPairsResponse']:
        return self.sapi.search_matrix_pairs(
            collection_name = collection_name,
            **kwargs,
        )

    @t.overload
    async def asearch_matrix_pairs(
        self,
        collection_name: str,
        query_filter: t.Optional['ct.Filter'] = None,
        limit: int = 3,
        sample: int = 10,
        using: t.Optional[str] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        timeout: t.Optional[int] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.SearchMatrixPairsResponse']:
        """
        Compute distance matrix for sampled points with a pair-based output format.

        Args:
            collection_name: Name of the collection.
            query_filter: Filter to apply.
            limit: How many neighbors per sample to find.
            sample: How many points to select and search within.
            using: Name of the vectors to use for search. If `None`, use default vectors.
            consistency: Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:
                - int: Number of replicas to query, values should be present in all queried replicas.
                - 'majority': Query all replicas, but return values present in the majority of replicas.
                - 'quorum': Query the majority of replicas, return values present in all of them.
                - 'all': Query all replicas, and return values present in all replicas.
            timeout: Overrides global timeout for this search. Unit is seconds.
            shard_key_selector: This parameter allows specifying which shards should be queried.
                If `None`, query all shards. Only works for collections with the `custom` sharding method.

        Returns:
            Distance matrix using a pair-based encoding.
        """
        ...

    async def asearch_matrix_pairs(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.List['ct.SearchMatrixPairsResponse']:
        return await self.api.search_matrix_pairs(
            collection_name = collection_name,
            **kwargs,
        )

    @t.overload
    def search_matrix_offsets(
        self,
        collection_name: str,
        query_filter: t.Optional['ct.Filter'] = None,
        limit: int = 3,
        sample: int = 10,
        using: t.Optional[str] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        timeout: t.Optional[int] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.SearchMatrixOffsetsResponse']:
        """
        Compute distance matrix for sampled points with an offset-based output format.

        Args:
            collection_name: Name of the collection.
            query_filter: Filter to apply.
            limit: How many neighbors per sample to find.
            sample: How many points to select and search within.
            using: Name of the vectors to use for search. If `None`, use default vectors.
            consistency: Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:
                - int: Number of replicas to query, values should present in all queried replicas.
                - 'majority': Query all replicas, but return values present in the majority of replicas.
                - 'quorum': Query the majority of replicas, return values present in all of them.
                - 'all': Query all replicas and return values present in all replicas.
            timeout: Overrides global timeout for this search. Unit is seconds.
            shard_key_selector: This parameter allows specifying which shards should be queried.
                If `None`, query all shards. Only works for collections with the `custom` sharding method.

        Returns:
            Distance matrix using an offset-based encoding.
        """
        ...

    def search_matrix_offsets(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.List['ct.SearchMatrixOffsetsResponse']:
        return self.sapi.search_matrix_offsets(
            collection_name = collection_name,
            **kwargs,
        )

    @t.overload
    async def asearch_matrix_offsets(
        self,
        collection_name: str,
        query_filter: t.Optional['ct.Filter'] = None,
        limit: int = 3,
        sample: int = 10,
        using: t.Optional[str] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        timeout: t.Optional[int] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.SearchMatrixOffsetsResponse']:
        """Compute distance matrix for sampled points with an offset-based output format.

        Args:
            collection_name: Name of the collection.
            query_filter: Filter to apply.
            limit: How many neighbors per sample to find.
            sample: How many points to select and search within.
            using: Name of the vectors to use for search. If `None`, use default vectors.
            consistency: Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:
                - int: Number of replicas to query, values should be present in all queried replicas.
                - 'majority': Query all replicas, but return values present in the majority of replicas.
                - 'quorum': Query the majority of replicas, return values present in all of them.
                - 'all': Query all replicas, and return values present in all replicas.
            timeout: Overrides global timeout for this search. Unit is seconds.
            shard_key_selector: This parameter allows specifying which shards should be queried.
                If `None`, query all shards. Only works for collections with the `custom` sharding method.

        Returns:    
            Distance matrix using an offset-based encoding.
        """
        ...

    async def asearch_matrix_offsets(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.List['ct.SearchMatrixOffsetsResponse']:
        return await self.api.search_matrix_offsets(
            collection_name = collection_name,
            **kwargs,
        )

    @t.overload
    def recommend_groups(
        self,
        collection_name: str,
        group_by: str,
        positive: t.Optional[t.Sequence['ct.RecommendExample']] = None,
        negative: t.Optional[t.Sequence['ct.RecommendExample']] = None,
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        group_size: int = 1,
        score_threshold: t.Optional[float] = None,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        using: t.Optional[str] = None,
        lookup_from: t.Optional['ct.LookupLocation'] = None,
        with_lookup: t.Optional['ct.WithLookupInterface'] = None,
        strategy: t.Optional['ct.RecommendStrategy'] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.GroupsResult']:
        """Recommend point groups: search for similar points based on already stored in Qdrant examples
        and groups by payload field.

        Recommend best matches for given stored examples grouped by the value of payload field.
        Useful to obtain most relevant results for each category, deduplicate results,
        finding the best representation vector for the same entity.

        Args:
            collection_name: Collection to search in
            positive:
                List of stored point IDs or vectors, which should be used as reference for similarity search.
                If there is only one example - this request is equivalent to the regular search with vector of that
                point.
                If there are more than one example, Qdrant will attempt to search for similar to all of them.
                Recommendation for multiple vectors is experimental.
                Its behaviour may change depending on selected strategy.
            negative:
                List of stored point IDs or vectors, which should be dissimilar to the search result.
                Negative examples is an experimental functionality.
                Its behaviour may change depending on selected strategy.
            group_by: Name of the payload field to group by.
                Field must be of type "keyword" or "integer".
                Nested fields are specified using dot notation, e.g. "nested_field.subfield".
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            search_params: Additional search params
            limit: How many groups return
            group_size: How many results return for each group
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - include only specified fields
                - Default: `False`
            score_threshold:
                Define a minimal score threshold for the result.
                If defined, less similar results will not be returned.
                Score of the returned result might be higher or smaller than the threshold depending
                on the Distance function used.
                E.g. for cosine similarity only higher scores will be returned.
            using:
                Name of the vectors to use for recommendations.
                If `None` - use default vectors.
            lookup_from:
                Defines a location (collection and vector field name), used to lookup vectors for recommendations.
                If `None` - current collection will be used.
            with_lookup:
                Look for points in another collection using the group ids.
                If specified, each group will contain a record from the specified collection
                with the same id as the group id. In addition, the parameter allows to specify
                which parts of the record should be returned, like in `with_payload` and `with_vectors` parameters.
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.
            strategy:
                Strategy to use for recommendation.
                Strategy defines how to combine multiple examples into a recommendation query.
                Possible values:

                - 'average_vector' - calculates average vector of all examples and uses it for search
                - 'best_score' - finds the result which is closer to positive examples and further from negative
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of groups with not more than `group_size` hits in each group.
            Each group also contains an id of the group, which is the value of the payload field.

        """
        ...
    
    def search_groups(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.List['ct.GroupsResult']:
        return self.sapi.search_groups(
            collection_name = collection_name,
            **kwargs,
        )

    @t.overload
    async def asearch_groups(
        self,
        collection_name: str,
        query_vector: t.Union[
            t.Sequence[float],
            t.Tuple[str, t.List[float]],
            'ct.NamedVector',
            'ct.NamedSparseVector',
            'ct.NumpyArray',
        ],
        group_by: str,
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        group_size: int = 1,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        score_threshold: t.Optional[float] = None,
        with_lookup: t.Optional['ct.WithLookupInterface'] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.GroupsResult']:
        """Search for closest vectors grouped by payload field.

        Searches best matches for query vector grouped by the value of payload field.
        Useful to obtain most relevant results for each category, deduplicate results,
        finding the best representation vector for the same entity.

        Args:
            collection_name: Collection to search in
            positive:
                List of stored point IDs or vectors, which should be used as reference for similarity search.
                If there is only one example - this request is equivalent to the regular search with vector of that
                point.
                If there are more than one example, Qdrant will attempt to search for similar to all of them.
                Recommendation for multiple vectors is experimental.
                Its behaviour may change depending on selected strategy.
            negative:
                List of stored point IDs or vectors, which should be dissimilar to the search result.
                Negative examples is an experimental functionality.
                Its behaviour may change depending on selected strategy.
            group_by: Name of the payload field to group by.
                Field must be of type "keyword" or "integer".
                Nested fields are specified using dot notation, e.g. "nested_field.subfield".
            query_filter:
                - Exclude vectors which doesn't fit given conditions.
                - If `None` - search among all vectors
            search_params: Additional search params
            limit: How many groups return
            group_size: How many results return for each group
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - include only specified fields
                - Default: `False`
            score_threshold:
                Define a minimal score threshold for the result.
                If defined, less similar results will not be returned.
                Score of the returned result might be higher or smaller than the threshold depending
                on the Distance function used.
                E.g. for cosine similarity only higher scores will be returned.
            using:
                Name of the vectors to use for recommendations.
                If `None` - use default vectors.
            lookup_from:
                Defines a location (collection and vector field name), used to lookup vectors for recommendations.
                If `None` - current collection will be used.
            with_lookup:
                Look for points in another collection using the group ids.
                If specified, each group will contain a record from the specified collection
                with the same id as the group id. In addition, the parameter allows to specify
                which parts of the record should be returned, like in `with_payload` and `with_vectors` parameters.
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.
            strategy:
                Strategy to use for recommendation.
                Strategy defines how to combine multiple examples into a recommendation query.
                Possible values:

                - 'average_vector' - calculates average vector of all examples and uses it for search
                - 'best_score' - finds the result which is closer to positive examples and further from negative
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of groups with not more than `group_size` hits in each group.
            Each group also contains an id of the group, which is the value of the payload field.

        """
        ...

    async def asearch_groups(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.List['ct.GroupsResult']:
        return await self.api.search_groups(
            collection_name = collection_name,
            **kwargs,
        )

    @t.overload
    def discover(
        self,
        collection_name: str,
        target: t.Optional[t.Sequence['ct.TargetVector']] = None,
        context: t.Optional[t.Sequence['ct.ContextExamplePair']] = None,
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        offset: t.Optional[int] = None,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        using: t.Optional[str] = None,
        lookup_from: t.Optional['ct.LookupLocation'] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.ScoredPoint']:
        """Use context and a target to find the most similar points, constrained by the context.

        Args:
            collection_name: Collection to discover in

            target:
                Look for vectors closest to this.

                When using the target (with or without context), the integer part of the score represents the rank with respect to the context, while the decimal part of the score relates to the distance to the target.

            context:
                Pairs of { positive, negative } examples to constrain the search.

                When using only the context (without a target), a special search - called context search - is performed where pairs of points are used to generate a loss that guides the search towards the zone where most positive examples overlap. This means that the score minimizes the scenario of finding a point closer to a negative than to a positive part of a pair.

                Since the score of a context relates to loss, the maximum score a point can get is 0.0, and it becomes normal that many points can have a score of 0.0.

                For discovery search (when including a target), the context part of the score for each pair is calculated +1 if the point is closer to a positive than to a negative part of a pair, and -1 otherwise.

            query_filter:
                Look only for points which satisfies this conditions

            search_params:
                Additional search params

            limit:
                Max number of result to return

            offset:
                Offset of the first result to return. May be used to paginate results. Note: large offset values may cause performance issues.

            with_payload:
                Select which payload to return with the response. Default: None

            with_vectors:
                Whether to return the point vector with the result?

            using:
                Define which vector to use for recommendation, if not specified - try to use default vector.

            lookup_from:
                The location used to lookup vectors. If not specified - use current collection. Note: the other collection should have the same vector size as the current collection.

            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas

            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.

            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of discovered points with discovery or context scores, accordingly.
        """
        ...

    def discover(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.List['ct.ScoredPoint']:
        return self.sapi.discover(
            collection_name = collection_name,
            **kwargs,
        )

    @t.overload
    async def adiscover(
        self,
        collection_name: str,
        target: t.Optional[t.Sequence['ct.TargetVector']] = None,
        context: t.Optional[t.Sequence['ct.ContextExamplePair']] = None,
        query_filter: t.Optional['ct.Filter'] = None,
        search_params: t.Optional['ct.SearchParams'] = None,
        limit: int = 10,
        offset: t.Optional[int] = None,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        using: t.Optional[str] = None,
        lookup_from: t.Optional['ct.LookupLocation'] = None,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.ScoredPoint']:
        """Use context and a target to find the most similar points, constrained by the context.

        Args:
            collection_name: Collection to discover in

            target:
                Look for vectors closest to this.

                When using the target (with or without context), the integer part of the score represents the rank with respect to the context, while the decimal part of the score relates to the distance to the target.

            context:
                Pairs of { positive, negative } examples to constrain the search.

                When using only the context (without a target), a special search - called context search - is performed where pairs of points are used to generate a loss that guides the search towards the zone where most positive examples overlap. This means that the score minimizes the scenario of finding a point closer to a negative than to a positive part of a pair.

                Since the score of a context relates to loss, the maximum score a point can get is 0.0, and it becomes normal that many points can have a score of 0.0.

                For discovery search (when including a target), the context part of the score for each pair is calculated +1 if the point is closer to a positive than to a negative part of a pair, and -1 otherwise.

            query_filter:
                Look only for points which satisfies this conditions

            search_params:
                Additional search params

            limit:
                Max number of result to return

            offset:
                Offset of the first result to return. May be used to paginate results. Note: large offset values may cause performance issues.

            with_payload:
                Select which payload to return with the response. Default: None

            with_vectors:
                Whether to return the point vector with the result?

            using:
                Define which vector to use for recommendation, if not specified - try to use default vector.

            lookup_from:
                The location used to lookup vectors. If not specified - use current collection. Note: the other collection should have the same vector size as the current collection.

            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas

            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.

            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of discovered points with discovery or context scores, accordingly.
        """
        ...
    
    async def adiscover(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.List['ct.ScoredPoint']:
        return await self.api.discover(
            collection_name = collection_name,
            **kwargs,
        )

    @t.overload
    def discover_batch(
        self,
        collection_name: str,
        requests: t.Sequence['ct.DiscoverRequest'],
        consistency: t.Optional['ct.ReadConsistency'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List[t.List['ct.ScoredPoint']]:
        """Perform multiple discover requests in batch mode

        Args:
            collection_name: Name of the collection
            requests: List of discover requests
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of discover responses
        """
        ...

    def discover_batch(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.List[t.List['ct.ScoredPoint']]:
        return self.sapi.discover_batch(
            collection_name = collection_name,
            **kwargs,
        )
    
    @t.overload
    async def adiscover_batch(
        self,
        collection_name: str,
        requests: t.Sequence['ct.DiscoverRequest'],
        consistency: t.Optional['ct.ReadConsistency'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List[t.List['ct.ScoredPoint']]:
        """Perform multiple discover requests in batch mode

        Args:
            collection_name: Name of the collection
            requests: List of discover requests
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            timeout:
                Overrides global timeout for this search. Unit is seconds.

        Returns:
            List of discover responses
        """
        ...

    async def adiscover_batch(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.List[t.List['ct.ScoredPoint']]:
        return await self.api.discover_batch(
            collection_name = collection_name,
            **kwargs,
        )

    
    @t.overload
    def scroll(
        self,
        collection_name: str,
        scroll_filter: t.Optional['ct.Filter'] = None,
        limit: int = 10,
        order_by: t.Optional['ct.OrderBy'] = None,
        offset: t.Optional['ct.PointId'] = None,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.Tuple[t.List['ct.Record'], t.Optional['ct.PointId']]:
        """Scroll over all (matching) points in the collection.

        This method provides a way to iterate over all stored points with some optional filtering condition.
        Scroll does not apply any similarity estimations, it will return points sorted by id in ascending order.

        Args:
            collection_name: Name of the collection
            scroll_filter: If provided - only returns points matching filtering conditions
            limit: How many points to return
            order_by: Order the records by a payload key. If `None` - order by id
            offset: If provided - skip points with ids less than given `offset`
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` (default) - Do not attach vector.
                - If List of string - include only specified fields
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas

            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.

            timeout:
                Overrides global timeout for this operation. Unit is seconds.

        Returns:
            A pair of (List of points) and (optional offset for the next scroll request).
            If next page offset is `None` - there is no more points in the collection to scroll.
        """
        ...

    def scroll(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.Tuple[t.List['ct.Record'], t.Optional['ct.PointId']]:
        return self.sapi.scroll(
            collection_name = collection_name,
            **kwargs,
        )

    @t.overload
    async def ascroll(
        self,
        collection_name: str,
        scroll_filter: t.Optional['ct.Filter'] = None,
        limit: int = 10,
        order_by: t.Optional['ct.OrderBy'] = None,
        offset: t.Optional['ct.PointId'] = None,
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.Tuple[t.List['ct.Record'], t.Optional['ct.PointId']]:
        """Scroll over all (matching) points in the collection.

        This method provides a way to iterate over all stored points with some optional filtering condition.
        Scroll does not apply any similarity estimations, it will return points sorted by id in ascending order.

        Args:
            collection_name: Name of the collection
            scroll_filter: If provided - only returns points matching filtering conditions
            limit: How many points to return
            order_by: Order the records by a payload key. If `None` - order by id
            offset: If provided - skip points with ids less than given `offset`
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` (default) - Do not attach vector.
                - If List of string - include only specified fields
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas

            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.

            timeout:
                Overrides global timeout for this operation. Unit is seconds.

        Returns:
            A pair of (List of points) and (optional offset for the next scroll request).
            If next page offset is `None` - there is no more points in the collection to scroll.
        """
        ...
    
    async def ascroll(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> t.Tuple[t.List['ct.Record'], t.Optional['ct.PointId']]:
        return await self.api.scroll(
            collection_name = collection_name,
            **kwargs,
        )

    @t.overload
    def count(
        self,
        collection_name: str,
        count_filter: t.Optional['ct.Filter'] = None,
        exact: bool = True,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> 'ct.CountResult':
        """Count points in the collection.

        Count points in the collection matching the given filter.

        Args:
            collection_name: name of the collection to count points in
            count_filter: filtering conditions
            exact:
                If `True` - provide the exact count of points matching the filter.
                If `False` - provide the approximate count of points matching the filter. Works faster.

            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.

            timeout:
                Overrides global timeout for this operation. Unit is seconds.

        Returns:
            Amount of points in the collection matching the filter.
        """
        ...

    def count(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> 'ct.CountResult':
        return self.sapi.count(
            collection_name = collection_name,
            **kwargs,
        )

    @t.overload
    async def acount(
        self,
        collection_name: str,
        count_filter: t.Optional['ct.Filter'] = None,
        exact: bool = True,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> 'ct.CountResult':
        """Count points in the collection.

        Count points in the collection matching the given filter.

        Args:
            collection_name: name of the collection to count points in
            count_filter: filtering conditions
            exact:
                If `True` - provide the exact count of points matching the filter.
                If `False` - provide the approximate count of points matching the filter. Works faster.

            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.

            timeout:
                Overrides global timeout for this operation. Unit is seconds.

        Returns:
            Amount of points in the collection matching the filter.
        """
        ...
    
    async def acount(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> 'ct.CountResult':
        return await self.api.count(
            collection_name = collection_name,
            **kwargs,
        )
    
    @t.overload
    def facet(
        self,
        collection_name: str,
        key: str,
        facet_filter: t.Optional['ct.Filter'] = None,
        limit: int = 10,
        exact: bool = False,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        timeout: t.Optional[int] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.FacetResponse':
        """Facet counts for the collection. For a specific payload key, returns unique values along with their counts.
        Higher counts come first in the results.

        Args:
            collection_name: Name of the collection
            key: Payload field to facet
            facet_filter: Filter to apply
            limit: Maximum number of hits to return
            exact: If `True` - provide the exact count of points matching the filter. If `False` - provide the approximate count of points matching the filter. Works faster.

            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            timeout: Overrides global timeout for this search. Unit is seconds.
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.

        Returns:
            Unique values in the facet and the amount of points that they cover.
        """
        ...

    def facet(
        self,
        collection_name: str,
        key: str,
        **kwargs: t.Any,
    ) -> 'ct.FacetResponse':
        return self.sapi.facet(
            collection_name = collection_name,
            key = key,
            **kwargs,
        )

    @t.overload
    async def afacet(
        self,
        collection_name: str,
        key: str,
        facet_filter: t.Optional['ct.Filter'] = None,
        limit: int = 10,
        exact: bool = False,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        timeout: t.Optional[int] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.FacetResponse']:
        """Facet counts for the collection. For a specific payload key, returns unique values along with their counts.
        Higher counts come first in the results.

        Args:
            collection_name: Name of the collection
            key: Payload field to facet
            facet_filter: Filter to apply
            limit: Maximum number of hits to return
            exact: If `True` - provide the exact count of points matching the filter. If `False` - provide the approximate count of points matching the filter. Works faster.

            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas
            timeout: Overrides global timeout for this search. Unit is seconds.
            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.

        Returns:
            Unique values in the facet and the amount of points that they cover.
        """
        ...

    async def afacet(
        self,
        collection_name: str,
        key: str,
        **kwargs: t.Any,
    ) -> t.List['ct.FacetResponse']:
        return await self.api.facet(
            collection_name = collection_name,
            key = key,
            **kwargs,
        )
    
    @t.overload
    def upsert(
        self,
        collection_name: str,
        points: 'ct.Points',
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """
        Update or insert a new point into the collection.

        If point with given ID already exists - it will be overwritten.

        Args:
            collection_name (str): To which collection to insert
            points (Point): Batch or list of points to insert
            wait (bool): Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation Result(UpdateResult)
        """
        ...

    def upsert(
        self,
        collection_name: str,
        points: 'ct.Points',
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return self.sapi.upsert(
            collection_name = collection_name,
            points = points,
            **kwargs,
        )

    @t.overload
    async def aupsert(
        self,
        collection_name: str,
        points: 'ct.Points',
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """
        Update or insert a new point into the collection.

        If point with given ID already exists - it will be overwritten.

        Args:
            collection_name (str): To which collection to insert
            points (Point): Batch or list of points to insert
            wait (bool): Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation Result(UpdateResult)
        """
        ...
    
    async def aupsert(
        self,
        collection_name: str,
        points: 'ct.Points',
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return await self.api.upsert(
            collection_name = collection_name,
            points = points,
            **kwargs,
        )
    
    @t.overload
    def update_vectors(
        self,
        collection_name: str,
        points: t.Sequence['ct.PointVectors'],
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.UpdateResult']:
        """Update specified vectors in the collection. Keeps payload and unspecified vectors unchanged.

        Args:
            collection_name (str): Name of the collection to update vectors in
            points (Point): List of (id, vector) pairs to update. Vector might be a list of numbers or a dict of named vectors.
                Examples:

                - `PointVectors(id=1, vector=[1, 2, 3])`
                - `PointVectors(id=2, vector={'vector_1': [1, 2, 3], 'vector_2': [4, 5, 6]})`

            wait (bool): Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.

            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation Result(UpdateResult)
        """
        ...

    def update_vectors(
        self,
        collection_name: str,
        points: t.Sequence['ct.PointVectors'],
        **kwargs: t.Any,
    ) -> t.List['ct.UpdateResult']:
        return self.sapi.update_vectors(
            collection_name = collection_name,
            points = points,
            **kwargs,
        )

    @t.overload
    async def aupdate_vectors(
        self,
        collection_name: str,
        points: t.Sequence['ct.PointVectors'],
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.UpdateResult']:
        """Update specified vectors in the collection. Keeps payload and unspecified vectors unchanged.

        Args:
            collection_name (str): Name of the collection to update vectors in
            points (Point): List of (id, vector) pairs to update. Vector might be a list of numbers or a dict of named vectors.
                Examples:

                - `PointVectors(id=1, vector=[1, 2, 3])`
                - `PointVectors(id=2, vector={'vector_1': [1, 2, 3], 'vector_2': [4, 5, 6]})`

            wait (bool): Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.

            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation Result(UpdateResult)
        """
        ...
    
    async def aupdate_vectors(
        self,
        collection_name: str,
        points: t.Sequence['ct.PointVectors'],
        **kwargs: t.Any,
    ) -> t.List['ct.UpdateResult']:
        return await self.api.update_vectors(
            collection_name = collection_name,
            points = points,
            **kwargs,
        )
    
    @t.overload
    def delete_vectors(
        self,
        collection_name: str,
        vectors: t.Sequence[str],
        points: 'ct.PointsSelector',
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Delete specified vector from the collection. Does not affect payload.

        Args:

            collection_name (str): Name of the collection to delete vector from
            vectors: List of names of the vectors to delete. Use `""` to delete the default vector. At least one vector should be specified.
            points (Point): Selects points based on list of IDs or filter
                Examples:

                - `points=[1, 2, 3, "cd3b53f0-11a7-449f-bc50-d06310e7ed90"]`
                - `points=Filter(must=[FieldCondition(key='rand_number', range=Range(gte=0.7))])`
            wait (bool): Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation result
        """
        ...

    def delete_vectors(
        self,
        collection_name: str,
        vectors: t.Sequence[str],
        points: t.Sequence['ct.PointVectors'],
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return self.sapi.delete_vectors(
            collection_name = collection_name,
            vectors = vectors,
            points = points,
            **kwargs,
        )
    
    @t.overload
    async def adelete_vectors(
        self,
        collection_name: str,
        vectors: t.Sequence[str],
        points: t.Sequence['ct.PointVectors'],
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Delete specified vector from the collection. Does not affect payload.

        Args:

            collection_name (str): Name of the collection to delete vector from
            vectors: List of names of the vectors to delete. Use `""` to delete the default vector. At least one vector should be specified.
            points (Point): Selects points based on list of IDs or filter
                Examples:

                - `points=[1, 2, 3, "cd3b53f0-11a7-449f-bc50-d06310e7ed90"]`
                - `points=Filter(must=[FieldCondition(key='rand_number', range=Range(gte=0.7))])`
            wait (bool): Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation result
        """
        ...
    
    async def adelete_vectors(
        self,
        collection_name: str,
        vectors: t.Sequence[str],
        points: t.Sequence['ct.PointVectors'],
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return await self.api.delete_vectors(
            collection_name = collection_name,
            vectors = vectors,
            points = points,
            **kwargs,
        )
    
    @t.overload
    def retrieve(
        self,
        collection_name: str,
        ids: t.Sequence['ct.PointId'],
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.Record']:
        """Retrieve stored points by IDs

        Args:
            collection_name: Name of the collection to lookup in
            ids: list of IDs to lookup
            with_payload:
                - Specify which stored payload should be attached to the result.
                - If `True` - attach all payload
                - If `False` - do not attach any payload
                - If List of string - include only specified fields
                - If `PayloadSelector` - use explicit rules
            with_vectors:
                - If `True` - Attach stored vector to the search result.
                - If `False` - Do not attach vector.
                - If List of string - Attach only specified vectors.
                - Default: `False`
            consistency:
                Read consistency of the search. Defines how many replicas should be queried before returning the result. Values:

                - int - number of replicas to query, values should present in all queried replicas
                - 'majority' - query all replicas, but return values present in the majority of replicas
                - 'quorum' - query the majority of replicas, return values present in all of them
                - 'all' - query all replicas, and return values present in all replicas

            shard_key_selector:
                This parameter allows to specify which shards should be queried.
                If `None` - query all shards. Only works for collections with `custom` sharding method.

            timeout:
                Overrides global timeout for this operation. Unit is seconds.

        Returns:
            List of points
        """
        ...

    def retrieve(
        self,
        collection_name: str,
        ids: t.Sequence['ct.PointId'],
        **kwargs: t.Any,
    ) -> t.List['ct.Record']:
        return self.sapi.retrieve(
            collection_name = collection_name,
            ids = ids,
            **kwargs,
        )

    @t.overload
    async def aretrieve(
        self,
        collection_name: str,
        ids: t.Sequence['ct.PointId'],
        with_payload: t.Union[bool, t.Sequence[str], 'ct.PayloadSelector'] = True,
        with_vectors: t.Union[bool, t.Sequence[str]] = False,
        consistency: t.Optional['ct.ReadConsistency'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.Record']:
        return await self.api.retrieve(
            collection_name = collection_name,
            ids = ids,
            with_payload = with_payload,
            with_vectors = with_vectors,
            consistency = consistency,
            shard_key_selector = shard_key_selector,
            timeout = timeout,
            **kwargs,
        )
    
    @t.overload
    def delete(
        self,
        collection_name: str,
        points_selector: 'ct.PointsSelector',
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Deletes selected points from collection

        Args:
            collection_name: Name of the collection
            wait: Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            points_selector: Selects points based on list of IDs or filter.
                Examples:

                - `points=[1, 2, 3, "cd3b53f0-11a7-449f-bc50-d06310e7ed90"]`
                - `points=Filter(must=[FieldCondition(key='rand_number', range=Range(gte=0.7))])`
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation result
        """
        ...

    def delete(
        self,
        collection_name: str,
        points_selector: 'ct.PointsSelector',
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return self.sapi.delete(
            collection_name = collection_name,
            points_selector = points_selector,
            **kwargs,
        )

    @t.overload
    async def adelete(
        self,
        collection_name: str,
        points_selector: 'ct.PointsSelector',
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Deletes selected points from collection

        Args:
            collection_name: Name of the collection
            wait: Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            points_selector: Selects points based on list of IDs or filter.
                Examples:

                - `points=[1, 2, 3, "cd3b53f0-11a7-449f-bc50-d06310e7ed90"]`
                - `points=Filter(must=[FieldCondition(key='rand_number', range=Range(gte=0.7))])`
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation result
        """
        ...
    
    async def adelete(
        self,
        collection_name: str,
        points_selector: 'ct.PointsSelector',
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return await self.api.delete(
            collection_name = collection_name,
            points_selector = points_selector,
            **kwargs,
        )
    
    @t.overload
    def set_payload(
        self,
        collection_name: str,
        payload: 'ct.Payload',
        points: 'ct.PointsSelector',
        key: t.Optional[str] = None,
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """
        Modifies payload of the specified points.

        Examples:

            `Set payload`::

                # Assign payload value with key `"key"` to points 1, 2, 3.
                # If payload value with specified key already exists - it will be overwritten
                qdrant_client.set_payload(
                    collection_name="test_collection",
                    wait=True,
                    payload={
                        "key": "value"
                    },
                    points=[1, 2, 3]
                )

        Args:
            collection_name: Name of the collection.
            wait: Await for the results to be processed.
                - If `true`, the result will be returned only when all changes are applied.
                - If `false`, the result will be returned immediately after confirmation of receipt.
            payload: Key-value pairs of payload to assign.
            points: List of affected points, filter, or points selector.
                Example:
                    - `points=[1, 2, 3, "cd3b53f0-11a7-449f-bc50-d06310e7ed90"]`
                    - `points=Filter(must=[FieldCondition(key='rand_number', range=Range(gte=0.7))])`
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:
                - `weak` (default): Write operations may be reordered, works faster.
                - `medium`: Write operations go through a dynamically selected leader, may be inconsistent for a short period of time in case of leader change.
                - `strong`: Write operations go through the permanent leader, consistent, but may be unavailable if the leader is down.
            shard_key_selector: Defines the shard groups that should be used to write updates into.
                If multiple shard keys are provided, the update will be written to each of them.
                Only works for collections with the `custom` sharding method.
            key: Path to the nested field in the payload to modify. If not specified, modifies the root of the payload.
                E.g.::

                    PointStruct(
                        id=42,
                        vector=[...],
                        payload={
                            "recipe": {
                                "fruits": {"apple": "100g"}
                            }
                        }
                    )

                    qdrant_client.set_payload(
                        ...,
                        payload={"cinnamon": "2g"},
                        key="recipe.fruits",
                        points=[42]
                    )

                    PointStruct(
                        id=42,
                        vector=[...],
                        payload={
                            "recipe": {
                                "fruits": {
                                    "apple": "100g",
                                    "cinnamon": "2g"
                                }
                            }
                        }
                    )

        Returns:
            Operation result.
        """
        ...

    def set_payload(
        self,
        collection_name: str,
        payload: 'ct.Payload',
        points: 'ct.PointsSelector',
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return self.sapi.set_payload(
            collection_name = collection_name,
            payload = payload,
            points = points,
            **kwargs,
        )

    @t.overload
    async def aset_payload(
        self,
        collection_name: str,
        payload: 'ct.Payload',
        points: 'ct.PointsSelector',
        key: t.Optional[str] = None,
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """
        Modifies payload of the specified points.

        Examples:

            `Set payload`::

                # Assign payload value with key `"key"` to points 1, 2, 3.
                # If payload value with specified key already exists - it will be overwritten
                qdrant_client.set_payload(
                    collection_name="test_collection",
                    wait=True,
                    payload={
                        "key": "value"
                    },
                    points=[1, 2, 3]
                )

        Args:
            collection_name: Name of the collection.
            wait: Await for the results to be processed.
                - If `true`, the result will be returned only when all changes are applied.
                - If `false`, the result will be returned immediately after confirmation of receipt.
            payload: Key-value pairs of payload to assign.
            points: List of affected points, filter, or points selector.
                Example:
                    - `points=[1, 2, 3, "cd3b53f0-11a7-449f-bc50-d06310e7ed90"]`
                    - `points=Filter(must=[FieldCondition(key='rand_number', range=Range(gte=0.7))])`
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:
                - `weak` (default): Write operations may be reordered, works faster.
                - `medium`: Write operations go through a dynamically selected leader, may be inconsistent for a short period of time in case of leader change.
                - `strong`: Write operations go through the permanent leader, consistent, but may be unavailable if the leader is down.
            shard_key_selector: Defines the shard groups that should be used to write updates into.
                If multiple shard keys are provided, the update will be written to each of them.
                Only works for collections with the `custom` sharding method.
            key: Path to the nested field in the payload to modify. If not specified, modifies the root of the payload.
                E.g.::

                    PointStruct(
                        id=42,
                        vector=[...],
                        payload={
                            "recipe": {
                                "fruits": {"apple": "100g"}
                            }
                        }
                    )

                    qdrant_client.set_payload(
                        ...,
                        payload={"cinnamon": "2g"},
                        key="recipe.fruits",
                        points=[42]
                    )

                    PointStruct(
                        id=42,
                        vector=[...],
                        payload={
                            "recipe": {
                                "fruits": {
                                    "apple": "100g",
                                    "cinnamon": "2g"
                                }
                            }
                        }
                    )

        Returns:
            Operation result.
        """
        ...
    
    async def aset_payload(
        self,
        collection_name: str,
        payload: 'ct.Payload',
        points: 'ct.PointsSelector',
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return await self.api.set_payload(
            collection_name = collection_name,
            payload = payload,
            points = points,
            **kwargs,
        )
    
    @t.overload
    def overwrite_payload(
        self,
        collection_name: str,
        payload: 'ct.Payload',
        points: 'ct.PointsSelector',
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Overwrites payload of the specified points
        After this operation is applied, only the specified payload will be present in the point.
        The existing payload, even if the key is not specified in the payload, will be deleted.

        Examples:

        `Set payload`::

            # Overwrite payload value with key `"key"` to points 1, 2, 3.
            # If any other valid payload value exists - it will be deleted
            qdrant_client.overwrite_payload(
                collection_name="test_collection",
                wait=True,
                payload={
                    "key": "value"
                },
                points=[1,2,3]
            )

        Args:
            collection_name: Name of the collection
            wait: Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            payload: Key-value pairs of payload to assign
            points: List of affected points, filter or points selector.
                Example:
                    - `points=[1, 2, 3, "cd3b53f0-11a7-449f-bc50-d06310e7ed90"]`
                    - `points=Filter(must=[FieldCondition(key='rand_number', range=Range(gte=0.7))])`

            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation result
        """
        ...

    def overwrite_payload(
        self,
        collection_name: str,
        payload: 'ct.Payload',
        points: 'ct.PointsSelector',
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return self.sapi.overwrite_payload(
            collection_name = collection_name,
            payload = payload,
            points = points,
            **kwargs,
        )

    @t.overload
    async def aoverwrite_payload(
        self,
        collection_name: str,
        payload: 'ct.Payload',
        points: 'ct.PointsSelector',
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Overwrites payload of the specified points
        After this operation is applied, only the specified payload will be present in the point.
        The existing payload, even if the key is not specified in the payload, will be deleted.

        Examples:

        `Set payload`::

            # Overwrite payload value with key `"key"` to points 1, 2, 3.
            # If any other valid payload value exists - it will be deleted
            qdrant_client.overwrite_payload(
                collection_name="test_collection",
                wait=True,
                payload={
                    "key": "value"
                },
                points=[1,2,3]
            )

        Args:
            collection_name: Name of the collection
            wait: Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            payload: Key-value pairs of payload to assign
            points: List of affected points, filter or points selector.
                Example:
                    - `points=[1, 2, 3, "cd3b53f0-11a7-449f-bc50-d06310e7ed90"]`
                    - `points=Filter(must=[FieldCondition(key='rand_number', range=Range(gte=0.7))])`

            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation result
        """
        ...
    
    async def aoverwrite_payload(
        self,
        collection_name: str,
        payload: 'ct.Payload',
        points: 'ct.PointsSelector',
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return await self.api.overwrite_payload(
            collection_name = collection_name,
            payload = payload,
            points = points,
            **kwargs,
        )
    
    @t.overload
    def delete_payload(
        self,
        collection_name: str,
        keys: t.Sequence[str],
        points: 'ct.PointsSelector',
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Remove values from point's payload

        Args:
            collection_name: Name of the collection
            wait: Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            keys: List of payload keys to remove
            points: List of affected points, filter or points selector.
                Example:
                    - `points=[1, 2, 3, "cd3b53f0-11a7-449f-bc50-d06310e7ed90"]`
                    - `points=Filter(must=[FieldCondition(key='rand_number', range=Range(gte=0.7))])`
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is downn

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation result
        """
        ...

    def delete_payload(
        self,
        collection_name: str,
        keys: t.Sequence[str],
        points: 'ct.PointsSelector',
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return self.sapi.delete_payload(
            collection_name = collection_name,
            keys = keys,
            points = points,
            **kwargs,
        )

    @t.overload
    async def adelete_payload(
        self,
        collection_name: str,
        keys: t.Sequence[str],
        points: 'ct.PointsSelector',
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Remove values from point's payload

        Args:
            collection_name: Name of the collection
            wait: Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            keys: List of payload keys to remove
            points: List of affected points, filter or points selector.
                Example:
                    - `points=[1, 2, 3, "cd3b53f0-11a7-449f-bc50-d06310e7ed90"]`
                    - `points=Filter(must=[FieldCondition(key='rand_number', range=Range(gte=0.7))])`
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is downn

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation result
        """
        ...
    
    async def adelete_payload(
        self,
        collection_name: str,
        keys: t.Sequence[str],
        points: 'ct.PointsSelector',
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return await self.api.delete_payload(
            collection_name = collection_name,
            keys = keys,
            points = points,
            **kwargs,
        )
    
    @t.overload
    def clear_payload(
        self,
        collection_name: str,
        points_selector: 'ct.PointsSelector',
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Delete all payload for selected points

        Args:
            collection_name: Name of the collection
            wait: Await for the results to be processed.
                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            points_selector: List of affected points, filter or points selector. Example:
                - `points=[1, 2, 3, "cd3b53f0-11a7-449f-bc50-d06310e7ed90"]`
                - `points=Filter(must=[FieldCondition(key='rand_number', range=Range(gte=0.7))])`
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation result
        """
        ...
    
    def clear_payload(
        self,
        collection_name: str,
        points_selector: 'ct.PointsSelector',
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return self.sapi.clear_payload(
            collection_name = collection_name,
            points_selector = points_selector,
            **kwargs,
        )

    @t.overload
    async def aclear_payload(
        self,
        collection_name: str,
        points_selector: 'ct.PointsSelector',
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Delete all payload for selected points

        Args:
            collection_name: Name of the collection
            wait: Await for the results to be processed.
                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            points_selector: List of affected points, filter or points selector. Example:
                - `points=[1, 2, 3, "cd3b53f0-11a7-449f-bc50-d06310e7ed90"]`
                - `points=Filter(must=[FieldCondition(key='rand_number', range=Range(gte=0.7))])`
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

            shard_key_selector:
                Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        Returns:
            Operation result
        """
        ...
    
    async def aclear_payload(
        self,
        collection_name: str,
        points_selector: 'ct.PointsSelector',
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return await self.api.clear_payload(
            collection_name = collection_name,
            points_selector = points_selector,
            **kwargs,
        )
    
    @t.overload
    def batch_update_points(
        self,
        collection_name: str,
        update_operations: t.Sequence['ct.UpdateOperation'],
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.UpdateResult']:
        """Batch update points in the collection.

        Args:
            collection_name: Name of the collection
            update_operations: List of update operations
            wait: Await for the results to be processed.
                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

        Returns:
            Operation results
        """
        ...

    def batch_update_points(
        self,
        collection_name: str,
        update_operations: t.Sequence['ct.UpdateOperation'],
        **kwargs: t.Any,
    ) -> t.List['ct.UpdateResult']:
        return self.sapi.batch_update_points(
            collection_name = collection_name,
            update_operations = update_operations,
            **kwargs,
        )

    @t.overload
    async def abatch_update_points(
        self,
        collection_name: str,
        update_operations: t.Sequence['ct.UpdateOperation'],
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        **kwargs: t.Any,
    ) -> t.List['ct.UpdateResult']:
        """Batch update points in the collection.

        Args:
            collection_name: Name of the collection
            update_operations: List of update operations
            wait: Await for the results to be processed.
                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

        Returns:
            Operation results
        """
        ...
    
    async def abatch_update_points(
        self,
        collection_name: str,
        update_operations: t.Sequence['ct.UpdateOperation'],
        **kwargs: t.Any,
    ) -> t.List['ct.UpdateResult']:
        return await self.api.batch_update_points(
            collection_name = collection_name,
            update_operations = update_operations,
            **kwargs,
        )
    
    @t.overload
    def update_collection_aliases(
        self,
        change_aliases_operations: t.Sequence['ct.AliasOperations'],
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> bool:
        """Operation for performing changes of collection aliases.

        Alias changes are atomic, meaning that no collection modifications can happen between alias operations.

        Args:
            change_aliases_operations: List of operations to perform
            timeout:
                Wait for operation commit timeout in seconds.
                If timeout is reached - request will return with service error.

        Returns:
            Operation result
        """
        ...

    def update_collection_aliases(
        self,
        change_aliases_operations: t.Sequence['ct.AliasOperations'],
        **kwargs: t.Any,
    ) -> bool:
        return self.sapi.update_collection_aliases(
            change_aliases_operations = change_aliases_operations,
            **kwargs,
        )

    @t.overload
    async def aupdate_collection_aliases(
        self,
        change_aliases_operations: t.Sequence['ct.AliasOperations'],
        timeout: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> bool:
        """Operation for performing changes of collection aliases.

        Alias changes are atomic, meaning that no collection modifications can happen between alias operations.

        Args:
            change_aliases_operations: List of operations to perform
            timeout:
                Wait for operation commit timeout in seconds.
                If timeout is reached - request will return with service error.

        Returns:
            Operation result
        """
        ...
    
    async def aupdate_collection_aliases(
        self,
        change_aliases_operations: t.Sequence['ct.AliasOperations'],
        **kwargs: t.Any,
    ) -> bool:
        return await self.api.update_collection_aliases(
            change_aliases_operations = change_aliases_operations,
            **kwargs,
        )
    
    def get_collection_aliases(
        self, collection_name: str, **kwargs: t.Any
    ) -> 'ct.CollectionsAliasesResponse':
        """Get collection aliases

        Args:
            collection_name: Name of the collection

        Returns:
            Collection aliases
        """
        return self.sapi.get_collection_aliases(
            collection_name = collection_name,
            **kwargs,
        )

    async def aget_collection_aliases(
        self, collection_name: str, **kwargs: t.Any
    ) -> 'ct.CollectionsAliasesResponse':
        """Get collection aliases

        Args:
            collection_name: Name of the collection

        Returns:
            Collection aliases
        """
        return await self.api.get_collection_aliases(
            collection_name = collection_name,
            **kwargs,
        )
    
    def get_aliases(self, **kwargs: t.Any) -> 'ct.CollectionsAliasesResponse':
        """Get all aliases

        Returns:
            All aliases of all collections
        """
        return self.sapi.get_aliases(
            **kwargs,
        )

    
    async def aget_aliases(self, **kwargs: t.Any) -> 'ct.CollectionsAliasesResponse':
        """Get all aliases

        Returns:
            All aliases of all collections
        """
        return await self.api.get_aliases(
            **kwargs,
        )
    
    def get_collections(self, **kwargs: t.Any) -> 'ct.CollectionsResponse':
        """Get list name of all existing collections

        Returns:
            List of the collections
        """
        return self.sapi.get_collections(
            **kwargs,
        )

    
    async def aget_collections(self, **kwargs: t.Any) -> 'ct.CollectionsResponse':
        """Get list name of all existing collections

        Returns:
            List of the collections
        """
        return await self.api.get_collections(
            **kwargs,
        )
    
    def get_collection(self, collection_name: str, **kwargs: t.Any) -> 'ct.CollectionInfo':
        """Get detailed information about specified existing collection

        Args:
            collection_name: Name of the collection

        Returns:
            Detailed information about the collection
        """
        return self.sapi.get_collection(
            collection_name = collection_name,
            **kwargs,
        )

    
    async def aget_collection(self, collection_name: str, **kwargs: t.Any) -> 'ct.CollectionInfo':
        """Get detailed information about specified existing collection

        Args:
            collection_name: Name of the collection

        Returns:
            Detailed information about the collection
        """
        return await self.api.get_collection(
            collection_name = collection_name,
            **kwargs,
        )
    
    def collection_exists(self, collection_name: str, **kwargs: t.Any) -> bool:
        """Check whether collection already exists

        Args:
            collection_name: Name of the collection

        Returns:
            True if collection exists, False if not
        """
        return self.sapi.collection_exists(
            collection_name = collection_name,
            **kwargs,
        )

    
    async def acollection_exists(self, collection_name: str, **kwargs: t.Any) -> bool:
        """Check whether collection already exists

        Args:
            collection_name: Name of the collection

        Returns:
            True if collection exists, False if not
        """
        return await self.api.collection_exists(
            collection_name = collection_name,
            **kwargs,
        )
    
    @t.overload
    def update_collection(
        self,
        collection_name: str,
        optimizers_config: t.Optional['ct.OptimizersConfigDiff'] = None,
        collection_params: t.Optional['ct.CollectionParamsDiff'] = None,
        vectors_config: t.Optional['ct.VectorsConfigDiff'] = None,
        hnsw_config: t.Optional['ct.HnswConfigDiff'] = None,
        quantization_config: t.Optional['ct.QuantizationConfigDiff'] = None,
        timeout: t.Optional[int] = None,
        sparse_vectors_config: t.Optional[t.Mapping[str, 'ct.SparseVectorParams']] = None,
        strict_mode_config: t.Optional['ct.StrictModeConfig'] = None,
        **kwargs: t.Any,
    ) -> bool:
        """Update parameters of the collection

        Args:
            collection_name: Name of the collection
            optimizers_config: Override for optimizer configuration
            collection_params: Override for collection parameters
            vectors_config: Override for vector-specific configuration
            hnsw_config: Override for HNSW index params
            quantization_config: Override for quantization params
            timeout:
                Wait for operation commit timeout in seconds.
                If timeout is reached - request will return with service error.
            sparse_vectors_config: Override for sparse vector-specific configuration
            strict_mode_config: Override for strict mode configuration
        Returns:
            Operation result
        """
        ...

    def update_collection(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> bool:
        return self.sapi.update_collection(
            collection_name = collection_name,
            **kwargs,
        )

    
    @t.overload
    async def aupdate_collection(
        self,
        collection_name: str,
        optimizers_config: t.Optional['ct.OptimizersConfigDiff'] = None,
        collection_params: t.Optional['ct.CollectionParamsDiff'] = None,
        vectors_config: t.Optional['ct.VectorsConfigDiff'] = None,
        hnsw_config: t.Optional['ct.HnswConfigDiff'] = None,
        quantization_config: t.Optional['ct.QuantizationConfigDiff'] = None,
        timeout: t.Optional[int] = None,
        sparse_vectors_config: t.Optional[t.Mapping[str, 'ct.SparseVectorParams']] = None,
        strict_mode_config: t.Optional['ct.StrictModeConfig'] = None,
        **kwargs: t.Any,
    ) -> bool:
        """Update parameters of the collection

        Args:
            collection_name: Name of the collection
            optimizers_config: Override for optimizer configuration
            collection_params: Override for collection parameters
            vectors_config: Override for vector-specific configuration
            hnsw_config: Override for HNSW index params
            quantization_config: Override for quantization params
            timeout:
                Wait for operation commit timeout in seconds.
                If timeout is reached - request will return with service error.
            sparse_vectors_config: Override for sparse vector-specific configuration
            strict_mode_config: Override for strict mode configuration
        Returns:
            Operation result
        """
        ...

    async def aupdate_collection(
        self,
        collection_name: str,
        **kwargs: t.Any,
    ) -> bool:
        return self.api.update_collection(
            collection_name = collection_name,
            **kwargs,
        )

    def delete_collection(
        self, collection_name: str, timeout: t.Optional[int] = None, **kwargs: t.Any
    ) -> bool:
        """Removes collection and all it's data

        Args:
            collection_name: Name of the collection to delete
            timeout:
                Wait for operation commit timeout in seconds.
                If timeout is reached - request will return with service error.

        Returns:
            Operation result
        """
        return self.sapi.delete_collection(
            collection_name = collection_name,
            timeout = timeout,
            **kwargs,
        )

    
    async def adelete_collection(
        self, collection_name: str, timeout: t.Optional[int] = None, **kwargs: t.Any
    ) -> bool:
        """Removes collection and all it's data

        Args:
            collection_name: Name of the collection to delete
            timeout:
                Wait for operation commit timeout in seconds.
                If timeout is reached - request will return with service error.

        Returns:
            Operation result
        """
        return await self.api.delete_collection(
            collection_name = collection_name,
            timeout = timeout,
            **kwargs,
        )
    
    @t.overload
    def create_collection(
        self,
        collection_name: str,
        vectors_config: t.Union[t.Sequence['ct.VectorParams'], t.Mapping[str, 'ct.VectorParams']],
        sparse_vectors_config: t.Optional[t.Mapping[str, 'ct.SparseVectorParams']] = None,
        shard_number: t.Optional[int] = None,
        sharding_method: t.Optional['ct.ShardingMethod'] = None,
        replication_factor: t.Optional[int] = None,
        write_consistency_factor: t.Optional[int] = None,
        on_disk_payload: t.Optional[bool] = None,
        hnsw_config: t.Optional['ct.HnswConfigDiff'] = None,
        optimizers_config: t.Optional['ct.OptimizersConfigDiff'] = None,
        wal_config: t.Optional['ct.WalConfigDiff'] = None,
        quantization_config: t.Optional['ct.QuantizationConfig'] = None,
        init_from: t.Optional['ct.InitFrom'] = None,
        timeout: t.Optional[int] = None,
        strict_mode_config: t.Optional['ct.StrictModeConfig'] = None,
        **kwargs: t.Any,
    ) -> bool:
        """Create empty collection with given parameters

        Args:
            collection_name: Name of the collection to recreate
            vectors_config:
                Configuration of the vector storage. Vector params contains size and distance for the vector storage.
                If dict is passed, service will create a vector storage for each key in the dict.
                If single VectorParams is passed, service will create a single anonymous vector storage.
            sparse_vectors_config:
                Configuration of the sparse vector storage.
                The service will create a sparse vector storage for each key in the dict.
            shard_number: Number of shards in collection. Default is 1, minimum is 1.
            sharding_method:
                Defines strategy for shard creation.
                Option `auto` (default) creates defined number of shards automatically.
                Data will be distributed between shards automatically.
                After creation, shards could be additionally replicated, but new shards could not be created.
                Option `custom` allows to create shards manually, each shard should be created with assigned
                unique `shard_key`. Data will be distributed between based on `shard_key` value.
            replication_factor:
                Replication factor for collection. Default is 1, minimum is 1.
                Defines how many copies of each shard will be created.
                Have effect only in distributed mode.
            write_consistency_factor:
                Write consistency factor for collection. Default is 1, minimum is 1.
                Defines how many replicas should apply the operation for us to consider it successful.
                Increasing this number will make the collection more resilient to inconsistencies, but will
                also make it fail if not enough replicas are available.
                Does not have any performance impact.
                Have effect only in distributed mode.
            on_disk_payload:
                If true - point`s payload will not be stored in memory.
                It will be read from the disk every time it is requested.
                This setting saves RAM by (slightly) increasing the response time.
                Note: those payload values that are involved in filtering and are indexed - remain in RAM.
            hnsw_config: Params for HNSW index
            optimizers_config: Params for optimizer
            wal_config: Params for Write-Ahead-Log
            quantization_config: Params for quantization, if None - quantization will be disabled
            init_from: Use data stored in another collection to initialize this collection
            timeout:
                Wait for operation commit timeout in seconds.
                If timeout is reached - request will return with service error.
            strict_mode_config: Configure limitations for the collection, such as max size, rate limits, etc.

        Returns:
            Operation result
        """
        ...

    def create_collection(
        self,
        collection_name: str,
        vectors_config: t.Union[t.Sequence['ct.VectorParams'], t.Mapping[str, 'ct.VectorParams']],
        **kwargs: t.Any,
    ) -> bool:
        return self.sapi.create_collection(
            collection_name = collection_name,
            vectors_config = vectors_config,
            **kwargs,
        )
    
    @t.overload
    async def acreate_collection(
        self,
        collection_name: str,
        vectors_config: t.Union[t.Sequence['ct.VectorParams'], t.Mapping[str, 'ct.VectorParams']],
        sparse_vectors_config: t.Optional[t.Mapping[str, 'ct.SparseVectorParams']] = None,
        shard_number: t.Optional[int] = None,
        sharding_method: t.Optional['ct.ShardingMethod'] = None,
        replication_factor: t.Optional[int] = None,
        write_consistency_factor: t.Optional[int] = None,
        on_disk_payload: t.Optional[bool] = None,
        hnsw_config: t.Optional['ct.HnswConfigDiff'] = None,
        optimizers_config: t.Optional['ct.OptimizersConfigDiff'] = None,
        wal_config: t.Optional['ct.WalConfigDiff'] = None,
        quantization_config: t.Optional['ct.QuantizationConfig'] = None,
        init_from: t.Optional['ct.InitFrom'] = None,
        timeout: t.Optional[int] = None,
        strict_mode_config: t.Optional['ct.StrictModeConfig'] = None,
        **kwargs: t.Any,
    ) -> bool:
        """Create empty collection with given parameters

        Args:
            collection_name: Name of the collection to recreate
            vectors_config:
                Configuration of the vector storage. Vector params contains size and distance for the vector storage.
                If dict is passed, service will create a vector storage for each key in the dict.
                If single VectorParams is passed, service will create a single anonymous vector storage.
            sparse_vectors_config:
                Configuration of the sparse vector storage.
                The service will create a sparse vector storage for each key in the dict.
            shard_number: Number of shards in collection. Default is 1, minimum is 1.
            sharding_method:
                Defines strategy for shard creation.
                Option `auto` (default) creates defined number of shards automatically.
                Data will be distributed between shards automatically.
                After creation, shards could be additionally replicated, but new shards could not be created.
                Option `custom` allows to create shards manually, each shard should be created with assigned
                unique `shard_key`. Data will be distributed between based on `shard_key` value.
            replication_factor:
                Replication factor for collection. Default is 1, minimum is 1.
                Defines how many copies of each shard will be created.
                Have effect only in distributed mode.
            write_consistency_factor:
                Write consistency factor for collection. Default is 1, minimum is 1.
                Defines how many replicas should apply the operation for us to consider it successful.
                Increasing this number will make the collection more resilient to inconsistencies, but will
                also make it fail if not enough replicas are available.
                Does not have any performance impact.
                Have effect only in distributed mode.
            on_disk_payload:
                If true - point`s payload will not be stored in memory.
                It will be read from the disk every time it is requested.
                This setting saves RAM by (slightly) increasing the response time.
                Note: those payload values that are involved in filtering and are indexed - remain in RAM.
            hnsw_config: Params for HNSW index
            optimizers_config: Params for optimizer
            wal_config: Params for Write-Ahead-Log
            quantization_config: Params for quantization, if None - quantization will be disabled
            init_from: Use data stored in another collection to initialize this collection
            timeout:
                Wait for operation commit timeout in seconds.
                If timeout is reached - request will return with service error.
            strict_mode_config: Configure limitations for the collection, such as max size, rate limits, etc.

        Returns:
            Operation result
        """
        ...

    async def acreate_collection(
        self,
        collection_name: str,
        vectors_config: t.Union[t.Sequence['ct.VectorParams'], t.Mapping[str, 'ct.VectorParams']],
        **kwargs: t.Any,
    ) -> bool:
        return await self.api.create_collection(
            collection_name = collection_name,
            vectors_config = vectors_config,
            **kwargs,
        )
    
    @t.overload
    def recreate_collection(
        self,
        collection_name: str,
        vectors_config: t.Union[t.Sequence['ct.VectorParams'], t.Mapping[str, 'ct.VectorParams']],
        sparse_vectors_config: t.Optional[t.Mapping[str, 'ct.SparseVectorParams']] = None,
        shard_number: t.Optional[int] = None,
        sharding_method: t.Optional['ct.ShardingMethod'] = None,
        replication_factor: t.Optional[int] = None,
        write_consistency_factor: t.Optional[int] = None,
        on_disk_payload: t.Optional[bool] = None,
        hnsw_config: t.Optional['ct.HnswConfigDiff'] = None,
        optimizers_config: t.Optional['ct.OptimizersConfigDiff'] = None,
        wal_config: t.Optional['ct.WalConfigDiff'] = None,
        quantization_config: t.Optional['ct.QuantizationConfig'] = None,
        init_from: t.Optional['ct.InitFrom'] = None,
        timeout: t.Optional[int] = None,
        strict_mode_config: t.Optional['ct.StrictModeConfig'] = None,
        **kwargs: t.Any,
    ) -> bool:
        """Delete and create empty collection with given parameters

        Args:
            collection_name: Name of the collection to recreate
            vectors_config:
                Configuration of the vector storage. Vector params contains size and distance for the vector storage.
                If dict is passed, service will create a vector storage for each key in the dict.
                If single VectorParams is passed, service will create a single anonymous vector storage.
            sparse_vectors_config:
                Configuration of the sparse vector storage.
                The service will create a sparse vector storage for each key in the dict.
            shard_number: Number of shards in collection. Default is 1, minimum is 1.
            sharding_method:
                Defines strategy for shard creation.
                Option `auto` (default) creates defined number of shards automatically.
                Data will be distributed between shards automatically.
                After creation, shards could be additionally replicated, but new shards could not be created.
                Option `custom` allows to create shards manually, each shard should be created with assigned
                unique `shard_key`. Data will be distributed between based on `shard_key` value.
            replication_factor:
                Replication factor for collection. Default is 1, minimum is 1.
                Defines how many copies of each shard will be created.
                Have effect only in distributed mode.
            write_consistency_factor:
                Write consistency factor for collection. Default is 1, minimum is 1.
                Defines how many replicas should apply the operation for us to consider it successful.
                Increasing this number will make the collection more resilient to inconsistencies, but will
                also make it fail if not enough replicas are available.
                Does not have any performance impact.
                Have effect only in distributed mode.
            on_disk_payload:
                If true - point`s payload will not be stored in memory.
                It will be read from the disk every time it is requested.
                This setting saves RAM by (slightly) increasing the response time.
                Note: those payload values that are involved in filtering and are indexed - remain in RAM.
            hnsw_config: Params for HNSW index
            optimizers_config: Params for optimizer
            wal_config: Params for Write-Ahead-Log
            quantization_config: Params for quantization, if None - quantization will be disabled
            init_from: Use data stored in another collection to initialize this collection
            timeout:
                Wait for operation commit timeout in seconds.
                If timeout is reached - request will return with service error.
            strict_mode_config: Configure limitations for the collection, such as max size, rate limits, etc.

        Returns:
            Operation result
        """
        ...

    def recreate_collection(
        self,
        collection_name: str,
        vectors_config: t.Union[t.Sequence['ct.VectorParams'], t.Mapping[str, 'ct.VectorParams']],
        **kwargs: t.Any,
    ) -> bool:
        return self.sapi.recreate_collection(
            collection_name = collection_name,
            vectors_config = vectors_config,
            **kwargs,
        )
    
    @t.overload
    async def arecreate_collection(
        self,
        collection_name: str,
        vectors_config: t.Union[t.Sequence['ct.VectorParams'], t.Mapping[str, 'ct.VectorParams']],
        sparse_vectors_config: t.Optional[t.Mapping[str, 'ct.SparseVectorParams']] = None,
        shard_number: t.Optional[int] = None,
        sharding_method: t.Optional['ct.ShardingMethod'] = None,
        replication_factor: t.Optional[int] = None,
        write_consistency_factor: t.Optional[int] = None,
        on_disk_payload: t.Optional[bool] = None,
        hnsw_config: t.Optional['ct.HnswConfigDiff'] = None,
        optimizers_config: t.Optional['ct.OptimizersConfigDiff'] = None,
        wal_config: t.Optional['ct.WalConfigDiff'] = None,
        quantization_config: t.Optional['ct.QuantizationConfig'] = None,
        init_from: t.Optional['ct.InitFrom'] = None,
        timeout: t.Optional[int] = None,
        strict_mode_config: t.Optional['ct.StrictModeConfig'] = None,
        **kwargs: t.Any,
    ) -> bool:
        """Delete and create empty collection with given parameters

        Args:
            collection_name: Name of the collection to recreate
            vectors_config:
                Configuration of the vector storage. Vector params contains size and distance for the vector storage.
                If dict is passed, service will create a vector storage for each key in the dict.
                If single VectorParams is passed, service will create a single anonymous vector storage.
            sparse_vectors_config:
                Configuration of the sparse vector storage.
                The service will create a sparse vector storage for each key in the dict.
            shard_number: Number of shards in collection. Default is 1, minimum is 1.
            sharding_method:
                Defines strategy for shard creation.
                Option `auto` (default) creates defined number of shards automatically.
                Data will be distributed between shards automatically.
                After creation, shards could be additionally replicated, but new shards could not be created.
                Option `custom` allows to create shards manually, each shard should be created with assigned
                unique `shard_key`. Data will be distributed between based on `shard_key` value.
            replication_factor:
                Replication factor for collection. Default is 1, minimum is 1.
                Defines how many copies of each shard will be created.
                Have effect only in distributed mode.
            write_consistency_factor:
                Write consistency factor for collection. Default is 1, minimum is 1.
                Defines how many replicas should apply the operation for us to consider it successful.
                Increasing this number will make the collection more resilient to inconsistencies, but will
                also make it fail if not enough replicas are available.
                Does not have any performance impact.
                Have effect only in distributed mode.
            on_disk_payload:
                If true - point`s payload will not be stored in memory.
                It will be read from the disk every time it is requested.
                This setting saves RAM by (slightly) increasing the response time.
                Note: those payload values that are involved in filtering and are indexed - remain in RAM.
            hnsw_config: Params for HNSW index
            optimizers_config: Params for optimizer
            wal_config: Params for Write-Ahead-Log
            quantization_config: Params for quantization, if None - quantization will be disabled
            init_from: Use data stored in another collection to initialize this collection
            timeout:
                Wait for operation commit timeout in seconds.
                If timeout is reached - request will return with service error.
            strict_mode_config: Configure limitations for the collection, such as max size, rate limits, etc.

        Returns:
            Operation result
        """
        ...
    
    async def arecreate_collection(
        self,
        collection_name: str,
        vectors_config: t.Union[t.Sequence['ct.VectorParams'], t.Mapping[str, 'ct.VectorParams']],
        **kwargs: t.Any,
    ) -> bool:
        return await self.api.recreate_collection(
            collection_name = collection_name,
            vectors_config = vectors_config,
            **kwargs,
        )

    @t.overload
    def upload_records(
        self,
        collection_name: str,
        records: t.Iterable[t.Sequence['ct.Record']],
        batch_size: int = 64,
        parallel: int = 1,
        method: t.Optional[str] = None,
        max_retries: int = 3,
        wait: bool = False,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> None:
        """Upload records to the collection

        Similar to `upload_collection` method, but operates with records, rather than vector and payload individually.

        Args:
            collection_name:  Name of the collection to upload to
            records: Iterator over records to upload
            batch_size: How many vectors upload per-request, Default: 64
            parallel: Number of parallel processes of upload
            method: Start method for parallel processes, Default: forkserver
            max_retries: maximum number of retries in case of a failure
                during the upload of a batch
            wait:
                Await for the results to be applied on the server side.
                If `true`, each update request will explicitly wait for the confirmation of completion. Might be slower.
                If `false`, each update request will return immediately after the confirmation of receiving.
            shard_key_selector: Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        """
        ...

    def upload_records(
        self,
        collection_name: str,
        records: t.Iterable[t.Sequence['ct.Record']],
        **kwargs: t.Any,
    ) -> None:
        return self.sapi.upload_records(
            collection_name = collection_name,
            records = records,
            **kwargs,
        )
    
    @t.overload
    async def aupload_records(
        self,
        collection_name: str,
        records: t.Iterable[t.Sequence['ct.Record']],
        batch_size: int = 64,
        parallel: int = 1,
        method: t.Optional[str] = None,
        max_retries: int = 3,
        wait: bool = False,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> None:
        """Upload records to the collection

        Similar to `upload_collection` method, but operates with records, rather than vector and payload individually.

        Args:
            collection_name:  Name of the collection to upload to
            records: Iterator over records to upload
            batch_size: How many vectors upload per-request, Default: 64
            parallel: Number of parallel processes of upload
            method: Start method for parallel processes, Default: forkserver
            max_retries: maximum number of retries in case of a failure
                during the upload of a batch
            wait:
                Await for the results to be applied on the server side.
                If `true`, each update request will explicitly wait for the confirmation of completion. Might be slower.
                If `false`, each update request will return immediately after the confirmation of receiving.
            shard_key_selector: Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        """
        ...
    
    async def aupload_records(
        self,
        collection_name: str,
        records: t.Iterable[t.Sequence['ct.Record']],
        **kwargs: t.Any,
    ) -> None:
        return await self.api.upload_records(
            collection_name = collection_name,
            records = records,
            **kwargs,
        )
    
    @t.overload
    def upload_points(
        self,
        collection_name: str,
        points: t.Iterable[t.Sequence['ct.PointStruct']],
        batch_size: int = 64,
        parallel: int = 1,
        method: t.Optional[str] = None,
        max_retries: int = 3,
        wait: bool = False,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> None:
        """Upload points to the collection

        Similar to `upload_collection` method, but operates with points, rather than vector and payload individually.

        Args:
            collection_name:  Name of the collection to upload to
            points: Iterator over points to upload
            batch_size: How many vectors upload per-request, Default: 64
            parallel: Number of parallel processes of upload
            method: Start method for parallel processes, Default: forkserver
            max_retries: maximum number of retries in case of a failure
                during the upload of a batch
            wait:
                Await for the results to be applied on the server side.
                If `true`, each update request will explicitly wait for the confirmation of completion. Might be slower.
                If `false`, each update request will return immediately after the confirmation of receiving.
            shard_key_selector: Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        """
        ...
    
    def upload_points(
        self,
        collection_name: str,
        points: t.Iterable[t.Sequence['ct.PointStruct']],
        **kwargs: t.Any,
    ) -> None:
        return self.sapi.upload_points(
            collection_name = collection_name,
            points = points,
            **kwargs,
        )

    @t.overload
    async def aupload_points(
        self,
        collection_name: str,
        points: t.Iterable[t.Sequence['ct.PointStruct']],
        batch_size: int = 64,
        parallel: int = 1,
        method: t.Optional[str] = None,
        max_retries: int = 3,
        wait: bool = False,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> None:
        """Upload points to the collection

        Similar to `upload_collection` method, but operates with points, rather than vector and payload individually.

        Args:
            collection_name:  Name of the collection to upload to
            points: Iterator over points to upload
            batch_size: How many vectors upload per-request, Default: 64
            parallel: Number of parallel processes of upload
            method: Start method for parallel processes, Default: forkserver
            max_retries: maximum number of retries in case of a failure
                during the upload of a batch
            wait:
                Await for the results to be applied on the server side.
                If `true`, each update request will explicitly wait for the confirmation of completion. Might be slower.
                If `false`, each update request will return immediately after the confirmation of receiving.
            shard_key_selector: Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.

        """
        ...
    
    async def aupload_points(
        self,
        collection_name: str,
        points: t.Iterable[t.Sequence['ct.PointStruct']],
        **kwargs: t.Any,
    ) -> None:
        return await self.api.upload_points(
            collection_name = collection_name,
            points = points,
            **kwargs,
        )
    
    @t.overload
    def upload_collection(
        self,
        collection_name: str,
        vectors: t.Union[t.Sequence[t.Sequence['ct.VectorStruct']], t.Mapping[str, t.Sequence['ct.NumpyArray']]],
        payload: t.Optional[t.Iterable[t.Mapping[t.Any, t.Any]]] = None,
        ids: t.Optional[t.Iterable['ct.PointId']] = None,
        batch_size: int = 64,
        parallel: int = 1,
        method: t.Optional[str] = None,
        max_retries: int = 3,
        wait: bool = False,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> None:
        """Upload vectors and payload to the collection.
        This method will perform automatic batching of the data.
        If you need to perform a single update, use `upsert` method.
        Note: use `upload_records` method if you want to upload multiple vectors with single payload.

        Args:
            collection_name:  Name of the collection to upload to
            vectors: np.ndarray or an iterable over vectors to upload. Might be mmaped
            payload: Iterable of vectors payload, Optional, Default: None
            ids: Iterable of custom vectors ids, Optional, Default: None
            batch_size: How many vectors upload per-request, Default: 64
            parallel: Number of parallel processes of upload
            method: Start method for parallel processes, Default: forkserver
            max_retries: maximum number of retries in case of a failure
                during the upload of a batch
            wait:
                Await for the results to be applied on the server side.
                If `true`, each update request will explicitly wait for the confirmation of completion. Might be slower.
                If `false`, each update request will return immediately after the confirmation of receiving.
            shard_key_selector: Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.
        """
        ...

    def upload_collection(
        self,
        collection_name: str,
        vectors: t.Union[t.Sequence[t.Sequence['ct.VectorStruct']], t.Mapping[str, t.Sequence['ct.NumpyArray']]],
        **kwargs: t.Any,
    ) -> None:
        return self.sapi.upload_collection(
            collection_name = collection_name,
            vectors = vectors,
            **kwargs,
        )
    
    @t.overload
    async def aupload_collection(
        self,
        collection_name: str,
        vectors: t.Union[t.Sequence[t.Sequence['ct.VectorStruct']], t.Mapping[str, t.Sequence['ct.NumpyArray']]],
        payload: t.Optional[t.Iterable[t.Mapping[t.Any, t.Any]]] = None,
        ids: t.Optional[t.Iterable['ct.PointId']] = None,
        batch_size: int = 64,
        parallel: int = 1,
        method: t.Optional[str] = None,
        max_retries: int = 3,
        wait: bool = False,
        shard_key_selector: t.Optional['ct.ShardKeySelector'] = None,
        **kwargs: t.Any,
    ) -> None:
        """Upload vectors and payload to the collection.
        This method will perform automatic batching of the data.
        If you need to perform a single update, use `upsert` method.        

        Args:
            collection_name:  Name of the collection to upload to
            vectors: np.ndarray or an iterable over vectors to upload. Might be mmaped
            payload: Iterable of vectors payload, Optional, Default: None
            ids: Iterable of custom vectors ids, Optional, Default: None
            batch_size: How many vectors upload per-request, Default: 64
            parallel: Number of parallel processes of upload
            method: Start method for parallel processes, Default: forkserver
            max_retries: maximum number of retries in case of a failure
                during the upload of a batch
            wait:
                Await for the results to be applied on the server side.
                If `true`, each update request will explicitly wait for the confirmation of completion. Might be slower.
                If `false`, each update request will return immediately after the confirmation of receiving.
            shard_key_selector: Defines the shard groups that should be used to write updates into.
                If multiple shard_keys are provided, the update will be written to each of them.
                Only works for collections with `custom` sharding method.
        """
        ...

    async def aupload_collection(
        self,
        collection_name: str,
        vectors: t.Union[t.Sequence[t.Sequence['ct.VectorStruct']], t.Mapping[str, t.Sequence['ct.NumpyArray']]],
        **kwargs: t.Any,
    ) -> None:
        return await self.api.upload_collection(
            collection_name = collection_name,
            vectors = vectors,
            **kwargs,
        )
    
    @t.overload
    def create_payload_index(
        self,
        collection_name: str,
        field_name: str,
        field_schema: t.Optional['ct.PayloadSchemaType'] = None,
        field_type: t.Optional['ct.PayloadSchemaType'] = None,
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Creates index for a given payload field.
        Indexed fields allow to perform filtered search operations faster.

        Args:
            collection_name: Name of the collection
            field_name: Name of the payload field
            field_schema: Type of data to index
            field_type: Same as field_schema, but deprecated
            wait: Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

        Returns:
            Operation Result
        """
        ...

    def create_payload_index(
        self,
        collection_name: str,
        field_name: str,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return self.sapi.create_payload_index(
            collection_name = collection_name,
            field_name = field_name,
            **kwargs,
        )

    
    @t.overload
    async def acreate_payload_index(
        self,
        collection_name: str,
        field_name: str,
        field_schema: t.Optional['ct.PayloadSchemaType'] = None,
        field_type: t.Optional['ct.PayloadSchemaType'] = None,
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Creates index for a given payload field.
        Indexed fields allow to perform filtered search operations faster.

        Args:
            collection_name: Name of the collection
            field_name: Name of the payload field
            field_schema: Type of data to index
            field_type: Same as field_schema, but deprecated
            wait: Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

        Returns:
            Operation Result
        """
        ...
    
    async def acreate_payload_index(
        self,
        collection_name: str,
        field_name: str,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return await self.api.create_payload_index(
            collection_name = collection_name,
            field_name = field_name,
            **kwargs,
        )
    
    @t.overload
    def delete_payload_index(
        self,
        collection_name: str,
        field_name: str,
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Removes index for a given payload field.

        Args:
            collection_name: Name of the collection
            field_name: Name of the payload field
            wait: Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

        Returns:
            Operation Result
        """
        ...

    def delete_payload_index(
        self,
        collection_name: str,
        field_name: str,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return self.sapi.delete_payload_index(
            collection_name = collection_name,
            field_name = field_name,
            **kwargs,
        )

    
    @t.overload
    async def adelete_payload_index(
        self,
        collection_name: str,
        field_name: str,
        wait: bool = True,
        ordering: t.Optional['ct.WriteOrdering'] = None,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        """Removes index for a given payload field.

        Args:
            collection_name: Name of the collection
            field_name: Name of the payload field
            wait: Await for the results to be processed.

                - If `true`, result will be returned only when all changes are applied
                - If `false`, result will be returned immediately after the confirmation of receiving.
            ordering (Optional[WriteOrdering]): Define strategy for ordering of the points. Possible values:

                - `weak` (default) - write operations may be reordered, works faster
                - `medium` - write operations go through dynamically selected leader, may be inconsistent for a short period of time in case of leader change
                - `strong` - Write operations go through the permanent leader, consistent, but may be unavailable if leader is down

        Returns:
            Operation Result
        """
        ...
    
    async def adelete_payload_index(
        self,
        collection_name: str,
        field_name: str,
        **kwargs: t.Any,
    ) -> 'ct.UpdateResult':
        return await self.api.delete_payload_index(
            collection_name = collection_name,
            field_name = field_name,
            **kwargs,
        )
    

    def list_snapshots(
        self, collection_name: str, **kwargs: t.Any
    ) -> t.List['ct.SnapshotDescription']:
        """List all snapshots for a given collection.

        Args:
            collection_name: Name of the collection

        Returns:
            List of snapshots
        """
        return self.sapi.list_snapshots(
            collection_name = collection_name,
            **kwargs,
        )
    
    async def alist_snapshots(
        self, collection_name: str, **kwargs: t.Any
    ) -> t.List['ct.SnapshotDescription']:
        """List all snapshots for a given collection.

        Args:
            collection_name: Name of the collection

        Returns:
            List of snapshots
        """
        return await self.api.list_snapshots(
            collection_name = collection_name,
            **kwargs,
        )
    
    def create_snapshot(
        self, collection_name: str, wait: bool = True, **kwargs: t.Any
    ) -> t.Optional['ct.SnapshotDescription']:
        """Create snapshot for a given collection.

        Args:
            collection_name: Name of the collection
            wait: Await for the snapshot to be created.

                - If `true`, result will be returned only when a snapshot is created
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            Snapshot description
        """
        return self.sapi.create_snapshot(
            collection_name = collection_name,
            wait = wait,
            **kwargs,
        )
    
    async def acreate_snapshot(
        self, collection_name: str, wait: bool = True, **kwargs: t.Any
    ) -> t.Optional['ct.SnapshotDescription']:
        """Create snapshot for a given collection.

        Args:
            collection_name: Name of the collection
            wait: Await for the snapshot to be created.

                - If `true`, result will be returned only when a snapshot is created
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            Snapshot description
        """
        return await self.api.create_snapshot(
            collection_name = collection_name,
            wait = wait,
            **kwargs,
        )
    
    def delete_snapshot(
        self, collection_name: str, snapshot_name: str, wait: bool = True, **kwargs: t.Any
    ) -> t.Optional[bool]:
        """Delete snapshot for a given collection.

        Args:
            collection_name: Name of the collection
            snapshot_name: Snapshot id
            wait: Await for the snapshot to be deleted.

                - If `true`, result will be returned only when the snapshot is deleted
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            True if snapshot was deleted
        """
        return self.sapi.delete_snapshot(
            collection_name = collection_name,
            snapshot_name = snapshot_name,
            wait = wait,
            **kwargs,
        )
    
    async def adelete_snapshot(
        self, collection_name: str, snapshot_name: str, wait: bool = True, **kwargs: t.Any
    ) -> t.Optional[bool]:
        """Delete snapshot for a given collection.

        Args:
            collection_name: Name of the collection
            snapshot_name: Snapshot id
            wait: Await for the snapshot to be deleted.

                - If `true`, result will be returned only when the snapshot is deleted
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            True if snapshot was deleted
        """
        return await self.api.delete_snapshot(
            collection_name = collection_name,
            snapshot_name = snapshot_name,
            wait = wait,
            **kwargs,
        )
    
    def list_full_snapshots(self, **kwargs: t.Any) -> t.List['ct.SnapshotDescription']:
        """List all snapshots for a whole storage

        Returns:
            List of snapshots
        """
        return self.sapi.list_full_snapshots(
            **kwargs,
        )

    async def alist_full_snapshots(self, **kwargs: t.Any) -> t.List['ct.SnapshotDescription']:
        """List all snapshots for a whole storage

        Returns:
            List of snapshots
        """
        return await self.api.list_full_snapshots(
            **kwargs,
        )
    

    def create_full_snapshot(
        self, wait: bool = True, **kwargs: t.Any
    ) -> t.Optional['ct.SnapshotDescription']:
        """Create snapshot for a whole storage.

        Args:
            wait: Await for the snapshot to be created.

                - If `true`, result will be returned only when the snapshot is created
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            Snapshot description
        """
        return self.sapi.create_full_snapshot(
            wait = wait,
            **kwargs,
        )
    
    async def acreate_full_snapshot(
        self, wait: bool = True, **kwargs: t.Any
    ) -> t.Optional['ct.SnapshotDescription']:
        """Create snapshot for a whole storage.

        Args:
            wait: Await for the snapshot to be created.

                - If `true`, result will be returned only when the snapshot is created
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            Snapshot description
        """
        return await self.api.create_full_snapshot(
            wait = wait,
            **kwargs,
        )
    
    def delete_full_snapshot(
        self, snapshot_name: str, wait: bool = True, **kwargs: t.Any
    ) -> t.Optional[bool]:
        """Delete snapshot for a whole storage.

        Args:
            snapshot_name: Snapshot name
            wait: Await for the snapshot to be deleted.

                - If `true`, result will be returned only when the snapshot is deleted
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            True if snapshot was deleted
        """
        return self.sapi.delete_full_snapshot(
            snapshot_name = snapshot_name,
            wait = wait,
            **kwargs,
        )
    
    async def adelete_full_snapshot(
        self, snapshot_name: str, wait: bool = True, **kwargs: t.Any
    ) -> t.Optional[bool]:
        """Delete snapshot for a whole storage.

        Args:
            snapshot_name: Snapshot name
            wait: Await for the snapshot to be deleted.

                - If `true`, result will be returned only when the snapshot is deleted
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            True if snapshot was deleted
        """
        return await self.api.delete_full_snapshot(
            snapshot_name = snapshot_name,
            wait = wait,
            **kwargs,
        )
    
    @t.overload
    def recover_snapshot(
        self,
        collection_name: str,
        location: str,
        api_key: t.Optional[str] = None,
        checksum: t.Optional[str] = None,
        priority: t.Optional['ct.SnapshotPriority'] = None,
        wait: bool = True,
        **kwargs: t.Any,
    ) -> t.Optional[bool]:
        """Recover collection from snapshot.

        Args:
            collection_name: Name of the collection
            location: URL of the snapshot
                Example:
                - URL `http://localhost:8080/collections/my_collection/snapshots/my_snapshot`
                - Local path `file:///qdrant/snapshots/test_collection/test_collection-6194298859870377-2023-11-09-15-17-51.snapshot`

            api_key: API key to use for accessing the snapshot on another server.

            checksum: Checksum of the snapshot to verify the integrity of the snapshot.

            priority: Defines source of truth for snapshot recovery

                - `replica` (default) means - prefer existing data over the snapshot
                - `no_sync` means - do not sync shard with other shards
                - `snapshot` means - prefer snapshot data over the current state

            wait: Await for the recovery to be done.

                - If `true`, result will be returned only when the recovery is done
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            True if snapshot was recovered
        """
        ...

    def recover_snapshot(
        self,
        collection_name: str,
        location: str,
        **kwargs: t.Any,
    ) -> t.Optional[bool]:
        return self.sapi.recover_snapshot(
            collection_name = collection_name,
            location = location,
            **kwargs,
        )

    
    @t.overload
    async def arecover_snapshot(
        self,
        collection_name: str,
        location: str,
        api_key: t.Optional[str] = None,
        checksum: t.Optional[str] = None,
        priority: t.Optional['ct.SnapshotPriority'] = None,
        wait: bool = True,
        **kwargs: t.Any,
    ) -> t.Optional[bool]:
        """Recover collection from snapshot.

        Args:
            collection_name: Name of the collection
            location: URL of the snapshot
                Example:
                - URL `http://localhost:8080/collections/my_collection/snapshots/my_snapshot`
                - Local path `file:///qdrant/snapshots/test_collection/test_collection-6194298859870377-2023-11-09-15-17-51.snapshot`

            api_key: API key to use for accessing the snapshot on another server.

            checksum: Checksum of the snapshot to verify the integrity of the snapshot.

            priority: Defines source of truth for snapshot recovery

                - `replica` (default) means - prefer existing data over the snapshot
                - `no_sync` means - do not sync shard with other shards
                - `snapshot` means - prefer snapshot data over the current state

            wait: Await for the recovery to be done.

                - If `true`, result will be returned only when the recovery is done
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            True if snapshot was recovered
        """
        ...

    async def arecover_snapshot(
        self,
        collection_name: str,
        location: str,
        **kwargs: t.Any,
    ) -> t.Optional[bool]:
        return await self.api.recover_snapshot(
            collection_name = collection_name,
            location = location,
            **kwargs,
        )
    
    def list_shard_snapshots(
        self, collection_name: str, shard_id: int, **kwargs: t.Any
    ) -> t.List['ct.SnapshotDescription']:
        """List all snapshots of a given shard

        Args:
            collection_name: Name of the collection
            shard_id: Index of the shard

        Returns:
            List of snapshots
        """
        return self.sapi.list_shard_snapshots(
            collection_name = collection_name,
            shard_id = shard_id,
            **kwargs,
        )
    
    async def alist_shard_snapshots(
        self, collection_name: str, shard_id: int, **kwargs: t.Any
    ) -> t.List['ct.SnapshotDescription']:
        """List all snapshots of a given shard

        Args:
            collection_name: Name of the collection
            shard_id: Index of the shard

        Returns:
            List of snapshots
        """
        return await self.api.list_shard_snapshots(
            collection_name = collection_name,
            shard_id = shard_id,
            **kwargs,
        )
    
    def create_shard_snapshot(
        self, collection_name: str, shard_id: int, wait: bool = True, **kwargs: t.Any
    ) -> t.Optional['ct.SnapshotDescription']:
        """Create snapshot for a given shard.

        Args:
            collection_name: Name of the collection
            shard_id: Index of the shard
            wait: Await for the snapshot to be created.

                - If `true`, result will be returned only when the snapshot is created.
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            Snapshot description
        """
        return self.sapi.create_shard_snapshot(
            collection_name = collection_name,
            shard_id = shard_id,
            wait = wait,
            **kwargs,
        )
    
    async def acreate_shard_snapshot(
        self, collection_name: str, shard_id: int, wait: bool = True, **kwargs: t.Any
    ) -> t.Optional['ct.SnapshotDescription']:
        """Create snapshot for a given shard.

        Args:
            collection_name: Name of the collection
            shard_id: Index of the shard
            wait: Await for the snapshot to be created.

                - If `true`, result will be returned only when the snapshot is created.
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            Snapshot description
        """
        return await self.api.create_shard_snapshot(
            collection_name = collection_name,
            shard_id = shard_id,
            wait = wait,
            **kwargs,
        )
    
    def delete_shard_snapshot(
        self,
        collection_name: str,
        shard_id: int,
        snapshot_name: str,
        wait: bool = True,
        **kwargs: t.Any,
    ) -> t.Optional[bool]:
        """Delete snapshot for a given shard.

        Args:
            collection_name: Name of the collection
            shard_id: Index of the shard
            snapshot_name: Snapshot id
            wait: Await for the snapshot to be deleted.

                - If `true`, result will be returned only when the snapshot is deleted
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            True if snapshot was deleted
        """
        return self.sapi.delete_shard_snapshot(
            collection_name = collection_name,
            shard_id = shard_id,
            snapshot_name = snapshot_name,
            wait = wait,
            **kwargs,
        )
    
    async def adelete_shard_snapshot(
        self,
        collection_name: str,
        shard_id: int,
        snapshot_name: str,
        wait: bool = True,
        **kwargs: t.Any,
    ) -> t.Optional[bool]:
        """Delete snapshot for a given shard.

        Args:
            collection_name: Name of the collection
            shard_id: Index of the shard
            snapshot_name: Snapshot id
            wait: Await for the snapshot to be deleted.

                - If `true`, result will be returned only when the snapshot is deleted
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            True if snapshot was deleted
        """
        return await self.api.delete_shard_snapshot(
            collection_name = collection_name,
            shard_id = shard_id,
            snapshot_name = snapshot_name,
            wait = wait,
            **kwargs,
        )
    
    @t.overload
    def recover_shard_snapshot(
        self,
        collection_name: str,
        shard_id: int,
        location: str,
        api_key: t.Optional[str] = None,
        checksum: t.Optional[str] = None,
        priority: t.Optional['ct.SnapshotPriority'] = None,
        wait: bool = True,
        **kwargs: t.Any,
    ) -> t.Optional[bool]:
        """Recover shard from snapshot.

        Args:
            collection_name: Name of the collection
            shard_id: Index of the shard
            location: URL of the snapshot
                Example:
                - URL `http://localhost:8080/collections/my_collection/snapshots/my_snapshot`

            api_key: API key to use for accessing the snapshot on another server.
            checksum: Checksum of the snapshot to verify the integrity of the snapshot.
            priority: Defines source of truth for snapshot recovery

                - `replica` (default) means - prefer existing data over the snapshot
                - `no_sync` means - do not sync shard with other shards
                - `snapshot` means - prefer snapshot data over the current state
            wait: Await for the recovery to be done.

                - If `true`, result will be returned only when the recovery is done
                - If `false`, result will be returned immediately after the confirmation of receiving.

        Returns:
            True if snapshot was recovered
        """
        ...
    
    def recover_shard_snapshot(
        self,
        collection_name: str,
        shard_id: int,
        location: str,
        **kwargs: t.Any,
    ) -> t.Optional[bool]:
        return self.sapi.recover_shard_snapshot(
            collection_name = collection_name,
            shard_id = shard_id,
            location = location,
            **kwargs,
        )

    
    @t.overload
    async def arecover_shard_snapshot(
        self,
        collection_name: str,
        shard_id: int,
        location: str,
        api_key: t.Optional[str] = None,
        checksum: t.Optional[str] = None,
        priority: t.Optional['ct.SnapshotPriority'] = None,
        wait: bool = True,
        **kwargs: t.Any,
    ) -> t.Optional[bool]:
        """Recover shard from snapshot.

        Args:
            collection_name: Name of the collection
            shard_id: Index of the shard
            location: URL of the snapshot
                Example:
                - URL `http://localhost:8080/collections/my_collection/snapshots/my_snapshot`

            api_key: API key to use for accessing the snapshot on another server.
            checksum: Checksum of the snapshot to verify the integrity of the snapshot.
            priority: Defines source of truth for snapshot recovery

                - `replica` (default) means - prefer existing data over the snapshot
                - `no_sync` means - do not sync shard with other shards
                - `snapshot` means - prefer snapshot data over the current state
            wait: Await for the recovery to be done.

                - If `true`, result will be returned only when the recovery is done
                - If `false`, result will be returned immediately after the confirmation of receiving.        
        Returns:
            True if snapshot was recovered
        """
        ...
    
    async def arecover_shard_snapshot(
        self,
        collection_name: str,
        shard_id: int,
        location: str,
        **kwargs: t.Any,
    ) -> t.Optional[bool]:
        return await self.api.recover_shard_snapshot(
            collection_name = collection_name,
            shard_id = shard_id,
            location = location,
            **kwargs,
        )
    
    def lock_storage(self, reason: str, **kwargs: t.Any) -> 'ct.LocksOption':
        """Lock storage for writing."""
        return self.sapi.lock_storage(
            reason = reason,
            **kwargs,
        )
    
    async def alock_storage(self, reason: str, **kwargs: t.Any) -> 'ct.LocksOption':
        """Lock storage for writing."""
        return await self.api.lock_storage(
            reason = reason,
            **kwargs,
        )
    
    def unlock_storage(self, **kwargs: t.Any) -> 'ct.LocksOption':
        """Unlock storage for writing."""
        return self.sapi.unlock_storage(
            **kwargs,
        )
    
    async def aunlock_storage(self, **kwargs: t.Any) -> 'ct.LocksOption':
        """Unlock storage for writing."""
        return await self.api.unlock_storage(
            **kwargs,
        )
    
    def get_locks(self, **kwargs: t.Any) -> 'ct.LocksOption':
        """Get current locks state."""
        return self.sapi.get_locks(
            **kwargs,
        )
    
    async def aget_locks(self, **kwargs: t.Any) -> 'ct.LocksOption':
        """Get current locks state."""
        return await self.api.get_locks(
            **kwargs,
        )
    
    @t.overload
    def create_shard_key(
        self,
        collection_name: str,
        shard_key: 'ct.ShardKey',
        shards_number: t.Optional[int] = None,
        replication_factor: t.Optional[int] = None,
        placement: t.Optional[list[int]] = None,
        **kwargs: t.Any,
    ) -> bool:
        """Create shard key for collection.

        Only works for collections with `custom` sharding method.

        Args:
            collection_name: Name of the collection
            shard_key: Shard key to create
            shards_number: How many shards to create for this key
            replication_factor: Replication factor for this key
            placement: List of peers to place shards on. If None - place on all peers.

        Returns:
            Operation result
        """
        ...
    

    def create_shard_key(
        self,
        collection_name: str,
        shard_key: 'ct.ShardKey',
        **kwargs: t.Any,
    ) -> bool:
        return self.sapi.create_shard_key(
            collection_name = collection_name,
            shard_key = shard_key,
            **kwargs,
        )
    
    @t.overload
    async def acreate_shard_key(
        self,
        collection_name: str,
        shard_key: 'ct.ShardKey',
        shards_number: t.Optional[int] = None,
        replication_factor: t.Optional[int] = None,
        placement: t.Optional[list[int]] = None,
        **kwargs: t.Any,
    ) -> bool:
        """Create shard key for collection.

        Only works for collections with `custom` sharding method.

        Args:
            collection_name: Name of the collection
            shard_key: Shard key to create
            shards_number: How many shards to create for this key
            replication_factor: Replication factor for this key
            placement: List of peers to place shards on. If None - place on all peers.

        Returns:
            Operation result
        """
        ...
    
    async def acreate_shard_key(
        self,
        collection_name: str,
        shard_key: 'ct.ShardKey',
        **kwargs: t.Any,
    ) -> bool:
        return await self.api.create_shard_key(
            collection_name = collection_name,
            shard_key = shard_key,
            **kwargs,
        )
    

    def delete_shard_key(
        self,
        collection_name: str,
        shard_key: 'ct.ShardKey',
        **kwargs: t.Any,
    ) -> bool:
        """Delete shard key for collection.

        Only works for collections with `custom` sharding method.

        Args:
            collection_name: Name of the collection
            shard_key: Shard key to delete

        Returns:
            Operation result
        """
        return self.sapi.delete_shard_key(
            collection_name = collection_name,
            shard_key = shard_key,
            **kwargs,
        )
    
    async def adelete_shard_key(
        self,
        collection_name: str,
        shard_key: 'ct.ShardKey',
        **kwargs: t.Any,
    ) -> bool:
        """Delete shard key for collection.

        Only works for collections with `custom` sharding method.

        Args:
            collection_name: Name of the collection
            shard_key: Shard key to delete

        Returns:
            Operation result
        """
        return await self.api.delete_shard_key(
            collection_name = collection_name,
            shard_key = shard_key,
            **kwargs,
        )
    
    def info(self) -> 'ct.VersionInfo':
        """Returns information about the running Qdrant instance like version and commit id

        Returns:
            Title, version and optionally commit info

        """
        return self.sapi.info()
    
    async def ainfo(self) -> 'ct.VersionInfo':
        """Returns information about the running Qdrant instance like version and commit id

        Returns:
            Title, version and optionally commit info

        """
        return await self.api.info()
    
