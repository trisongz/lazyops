from __future__ import annotations

"""
Qdrant Mixins
"""

import abc
import datetime
import typing as t
from lzl import load
from lzl.types import eproperty
from lzo.utils import Timer, parse_datetime
from lzl.logging import Logger, logger as _logger, null_logger

if t.TYPE_CHECKING:
    from pydantic import BaseModel
    from lzl.api.qdrant import QdrantClient, QdrantClientSettings
    from fastembed.rerank.cross_encoder import TextCrossEncoder
    from qdrant_client.conversions import common_types as ct
    from qdrant_client.http import models as qm
    from qdrant_client.fastembed_common import QueryResponse

    class QdrantBaseModel(BaseModel):
        """
        Base Qdrant Model
        """

        @classmethod
        def get_qdrant_index_config(cls) -> t.Dict[str, t.Dict[str, t.Any]]:
            """
            Returns the Qdrant index config
            """
            return {}
        
    
QdrantModelT = t.TypeVar('QdrantModelT', bound = 'QdrantBaseModel')

def get_model_config_fields(
    model: t.Type['BaseModel'],
    config_filters: t.Dict[str, t.Union[bool, str, t.Any]] = {
        'qdrant_index': True,
    }, 
    results: t.Literal['included', 'excluded', 'exclusive'] = 'included',
    match_all: bool = True,
) -> t.Dict[str, t.Dict[str, t.Any]]:  # sourcery skip: default-mutable-arg
    """
    Returns the fields for the model
    """
    excluded, included = [], []
    for field_name, field in model.model_fields.items():
        if not field.json_schema_extra: 
            if results == 'exclusive': excluded.append(field_name)
            continue
        for key, value in config_filters.items():
            if key not in field.json_schema_extra: continue
            if field.json_schema_extra[key] == value: 
                included.append(field_name)
            else:
                excluded.append(field_name)
    if match_all: included = [i for i in included if i not in excluded]
    fields = set(excluded if results in {'excluded', 'exclusive'} else included)
    # Now we actually build the config
    config_filter_keys = list(config_filters.keys())
    config: t.Dict[str, t.Dict[str, t.Any]] = {}
    for field_name in fields:
        field_schema = model.model_fields[field_name]
        config[field_name] = {
             k: v for k,v in field_schema.json_schema_extra.items() if k not in 
             config_filter_keys
        }
    return config

_SupportedIndexTypes: t.Set[str] = {'keyword', 'integer', 'float', 'bool', 'geo', 'datetime', 'text', 'uuid'}
CollectionState = t.Literal['create', 'recreate', 'delete']
comp_op = {
    '>': 'gt',
    '<': 'lt',
    '>=': 'gte',
    '<=': 'lte',
}

class QdrantSearchMixin(abc.ABC, t.Generic[QdrantModelT]):
    """
    Qdrant Search Mixin
    """

    collection_name: t.Optional[str] = None
    schema: t.Optional[t.Type[QdrantModelT]] = None

    on_disk_default: t.Optional[bool] = None
    on_disk_by_type: t.Optional[t.Dict[str, bool]] = None
    on_disk_by_field: t.Optional[t.Dict[str, bool]] = None

    dense_model: t.Optional[str] = None
    sparse_model: t.Optional[str] = None
    rerank_model: t.Optional[str] = None
    debug_enabled: t.Optional[bool] = None
    retries: t.Optional[int] = None

    has_dataset: t.Optional[bool] = None

    ds_batch_size: t.Optional[int] = 25
    ds_log_every: t.Optional[int] = None


    def __init__(
        self,
        collection_name: t.Optional[str] = None,
        schema: t.Optional[t.Type[QdrantModelT]] = None,
        dense_model: t.Optional[str] = None,
        sparse_model: t.Optional[str] = None,
        rerank_model: t.Optional[str] = None,
        debug_enabled: t.Optional[bool] = None,
        
        on_disk_default: t.Optional[bool] = None,
        on_disk_by_type: t.Optional[t.Dict[str, bool]] = None,
        on_disk_by_field: t.Optional[t.Dict[str, bool]] = None,

        has_dataset: t.Optional[bool] = None,

        **kwargs: t.Any,
    ):
        self._extra: t.Dict[str, t.Any] = {}
        if collection_name is not None: self.collection_name = collection_name
        if schema is not None: self.schema = schema
        if dense_model is not None: self.dense_model = dense_model
        if sparse_model is not None: self.sparse_model = sparse_model
        if rerank_model is not None: self.rerank_model = rerank_model
        if debug_enabled is not None: self.debug_enabled = debug_enabled
        if on_disk_default is not None: self.on_disk_default = on_disk_default
        self.on_disk_by_type = on_disk_by_type if on_disk_by_type is not None else {}
        self.on_disk_by_field = on_disk_by_field if on_disk_by_field is not None else {}
        
        if has_dataset is not None: self.has_dataset = has_dataset
        self._initialized: bool = False
        self._ingested: bool = False
        self._kwargs = kwargs

    @eproperty
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        return _logger

    @eproperty
    def autologger(self) -> 'Logger':
        """
        Automatic Logger that is enabled in devel mode
        """
        return self.logger if self.debug_enabled else null_logger

    @eproperty
    def client(self) -> 'QdrantClient':
        """
        Returns the Qdrant Client
        """
        from lzl.api.qdrant import QdrantClient
        return QdrantClient(
            set_model = self.dense_model,
            set_sparse_model = self.sparse_model,
            retries = self.retries,
            **self._kwargs,
        )
    

    @eproperty
    def settings(self) -> 'QdrantClientSettings':
        """
        Returns the Qdrant Client Settings
        """
        return self.client.settings
    
    @eproperty
    def has_reranker(self) -> bool:
        """
        Returns whether the Opportunity has a Reranker
        """
        return self.rerank_model is not None

    @eproperty
    def reranker(self) -> t.Optional['TextCrossEncoder']:
        """
        Returns the Reranker if provided
        """
        if self.rerank_model is None: return None
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        return TextCrossEncoder(
            model_name = self.rerank_model,
            lazy_load = True,
        )


    @staticmethod
    def get_model_config_from_fields(
        model: t.Type['BaseModel'],
        config_filters: t.Dict[str, t.Union[bool, str, t.Any]] = {
            'qdrant_index': True,
        }, 
        results: t.Literal['included', 'excluded', 'exclusive'] = 'included',
        match_all: bool = True,
    ) -> t.Dict[str, t.Dict[str, t.Any]]:  # sourcery skip: default-mutable-arg
        """
        Returns the model config for the BaseModel
        """
        return get_model_config_fields(
            model = model,
            config_filters = config_filters,
            results = results,
            match_all = match_all,
        )

    @eproperty
    def qm(self):
        """
        Returns the Qm
        """
        from qdrant_client.http import models
        return models
    
    @eproperty
    def schema_model_config(self) -> t.Dict[str, t.Dict[str, t.Any]]:
        """
        Returns the schema model config
        """
        return self.get_model_config_from_fields(self.schema)

    """
    Downstream Methods
    """

    def get_vectors_config(self, **kwargs):
        """
        Returns the collection vectors config
        """
        return self.client.get_fastembed_vector_params(**kwargs)

    def get_sparse_vectors_config(self, **kwargs):
        """
        Returns the collection sparse vectors config
        """
        return self.client.get_fastembed_sparse_vector_params(**kwargs)
    
    def get_collection_config(self, **kwargs) -> t.Dict[str, t.Any]:
        """
        Returns the collection config
        """
        return {}

    def _parse_kwargs(
        self,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        """
        Parses the kwargs
        """
        return {k: v for k,v in kwargs.items() if v is not None}

    def get_on_disk_default(
        self,
        index_type: str,
        field_name: t.Optional[str] = None,
    ) -> bool:
        """
        Returns the default on disk value
        """
        if field_name and field_name in self.on_disk_by_field: return self.on_disk_by_field[field_name]
        if index_type in self.on_disk_by_type: return self.on_disk_by_type[index_type]
        return self.on_disk_default
    
    def _on_collection_state(
        self,
        state: CollectionState,
        **kwargs,
    ):
        """
        Hook for Collection State Change
        """
        pass

    async def _aon_collection_state(
        self,
        state: CollectionState,
        **kwargs,
    ):
        """
        Hook for Collection State Change
        """
        pass

    def on_collection_state(
        self,
        state: CollectionState,
        is_async: t.Optional[bool] = True,
        **kwargs,
    ):
        """
        Hook for Collection State Change
        """
        func = self._aon_collection_state if is_async else self._on_collection_state
        return func(
            state = state,
            **kwargs,
        )

    """
    Initialization Methods
    """        

    def get_index_config(
        self,
        index_type: str,
        index_config: t.Dict[str, t.Any],
        field_name: t.Optional[str] = None,
    ) -> 'ct.PayloadSchemaType':
        """
        Returns the index config
        """
        if index_type == 'keyword':
            return self.qm.KeywordIndexParams(
                type = "keyword", 
                **self._parse_kwargs(
                    is_tenant = index_config.get('is_tenant'),
                    on_disk = index_config.get('on_disk', self.get_on_disk_default(index_type = index_type, field_name = field_name)),
                )
            )

        if index_type == 'integer':
            return self.qm.IntegerIndexParams(
                type = "integer",
                **self._parse_kwargs(
                    lookup = index_config.get('lookup', True),
                    range = index_config.get('range', True),
                    is_principal = index_config.get('is_principal'),
                    on_disk = index_config.get('on_disk', self.get_on_disk_default(index_type = index_type, field_name = field_name)),
                ),
            )

        if index_type == 'float':
            return self.qm.FloatIndexParams(
                type = "float",
                **self._parse_kwargs(
                    is_principal = index_config.get('is_principal'),
                    on_disk = index_config.get('on_disk', self.get_on_disk_default(index_type = index_type, field_name = field_name))
                ),
            )
        
        if index_type == 'bool':
            return self.qm.BoolIndexParams(
                type = "bool",
                **self._parse_kwargs(
                    on_disk = index_config.get('on_disk', self.get_on_disk_default(index_type = index_type, field_name = field_name)),
                ),
            )

        if index_type == 'geo':
            return self.qm.GeoIndexParams(
                type = "geo",
                **self._parse_kwargs(
                    on_disk = index_config.get('on_disk', self.get_on_disk_default(index_type = index_type, field_name = field_name)),
                ),
            )
        

        if index_type == 'datetime':
            return self.qm.DatetimeIndexParams(
                type = "datetime", 
                **self._parse_kwargs(
                    is_principal = index_config.get('is_principal'),
                    on_disk = index_config.get('on_disk', self.get_on_disk_default(index_type = index_type, field_name = field_name)),
                ),
            )
        

        if index_type == 'text':
            return self.qm.TextIndexParams(
                type = "text",
                **self._parse_kwargs(
                    tokenizer = index_config.get('tokenizer', self.qm.TokenizerType.WORD),
                    min_token_len = index_config.get('min_token_len', 2),
                    max_token_len = index_config.get('max_token_len', 40),
                    lowercase = index_config.get('lowercase', True),
                    on_disk = index_config.get('on_disk', self.get_on_disk_default(index_type = index_type, field_name = field_name)),
                ),
            )
        
        if index_type == 'uuid':
            return self.qm.UuidIndexParams(
                type = "uuid",
                **self._parse_kwargs(
                    is_tenant = index_config.get('is_tenant'),
                    on_disk = index_config.get('on_disk', self.get_on_disk_default(index_type = index_type, field_name = field_name)),
                ),
            )
        
        raise ValueError(f'Invalid index type: {index_type}')

    def _build_index_from_config(
        self,
        qdrant_index_config: t.Dict[str, t.Dict[str, t.Any]],
        **kwargs,
    ):
        """
        Builds the index from the config
        """
        for field_name, index_config in qdrant_index_config.items():
            index_type = index_config.get('index_type', 'text')
            if index_config.get('nested_field_name'): field_name = index_config['nested_field_name']
            if index_type not in _SupportedIndexTypes:
                self.logger.warning(f'Unsupported index type: {index_type}')
                continue
            if 'index_config' in index_config: index_config = index_config['index_config']
            self.client.create_payload_index(
                collection_name = self.collection_name,
                field_name = field_name,
                field_schema = self.get_index_config(
                    index_type = index_type,
                    index_config = index_config,
                    field_name = field_name,
                )
            )
        
    def _init_collection_index(
        self,
        **kwargs,
    ):
        """
        Initializes the collection index

        - This can be overwritten by a downstream method
        """
        if not self.schema: return
        # model_config = self.get_model_config_from_fields(self.schema)
        self.autologger.info(f'Initializing Collection Index: `|g|{self.collection_name}|e|`', colored = True)
        self._build_index_from_config(self.schema_model_config, **kwargs)
        if hasattr(self.schema, 'get_qdrant_index_config'):
            schema_index_config: t.Dict[str, t.Dict[str, t.Any]] = self.schema.get_qdrant_index_config()
            self._build_index_from_config(schema_index_config, **kwargs)
        

    async def _abuild_index_from_config(
        self,
        qdrant_index_config: t.Dict[str, t.Dict[str, t.Any]],
        **kwargs,
    ):
        """
        Builds the index from the config
        """
        for field_name, index_config in qdrant_index_config.items():
            index_type = index_config.get('index_type', 'text')
            if index_config.get('nested_field_name'): field_name = index_config['nested_field_name']
            if index_type not in _SupportedIndexTypes:
                self.logger.warning(f'Unsupported index type: {index_type}')
                continue
            self.autologger.info(f'Setting up index for `|g|{field_name}|e|` with type `|y|{index_type}|e|`', colored = True)
            if 'index_config' in index_config: index_config = index_config['index_config']
            await self.client.acreate_payload_index(
                collection_name = self.collection_name,
                field_name = field_name,
                field_schema = self.get_index_config(
                    index_type = index_type,
                    index_config = index_config,
                    field_name = field_name,
                )
            )


    async def _ainit_collection_index(
        self,
        **kwargs,
    ):
        """
        Initializes the collection index

        - This can be overwritten by a downstream method
        """
        if not self.schema: return
        # model_config = self.get_model_config_from_fields(self.schema)
        self.autologger.info(f'Initializing Collection Index: `|g|{self.collection_name}|e|`', colored = True)
        await self._abuild_index_from_config(self.schema_model_config, **kwargs)
        if hasattr(self.schema, 'get_qdrant_index_config'):
            schema_index_config: t.Dict[str, t.Dict[str, t.Any]] = self.schema.get_qdrant_index_config()
            self.autologger.info(f'Initializing from Qdrant Schema Config: `|g|{self.collection_name}|e|`: {schema_index_config}', colored = True)
            await self._abuild_index_from_config(schema_index_config, **kwargs)


    def _init_collection(
        self,
        skip_init_index: t.Optional[bool] = None,
        **kwargs,
    ):
        """
        Initializes the collection
        """
        if self._initialized: return
        if self.collection_name is None: raise ValueError('Collection Name is None')
        if self.client.collection_exists(self.collection_name): 
            collection_info = self.client.get_collection(collection_name = self.collection_name)
            self.client.api._validate_collection_info(collection_info)
            self._initialized = True
            return
        self.autologger.info(f'Initializing Collection: `|g|{self.collection_name}|e|`', colored = True)
        self.client.create_collection(
            collection_name = self.collection_name,
            vectors_config = self.get_vectors_config(),
            sparse_vectors_config = self.get_sparse_vectors_config(),
            **self.get_collection_config(**kwargs),
        )
        self.on_collection_state('create', is_async = False)
        if not skip_init_index: self._init_collection_index(**kwargs)
        self._initialized = True


    async def _ainit_collection(
        self,
        skip_init_index: t.Optional[bool] = None,
        **kwargs,
    ):
        """
        Initializes the collection
        """
        if self._initialized: return
        if self.collection_name is None: raise ValueError('Collection Name is None')
        if await self.client.acollection_exists(self.collection_name): 
            collection_info = await self.client.aget_collection(collection_name = self.collection_name)
            self.client.api._validate_collection_info(collection_info)
            self._initialized = True
            return
        self.autologger.info(f'Initializing Collection: `|g|{self.collection_name}|e|`', colored = True)
        await self.client.acreate_collection(
            collection_name = self.collection_name,
            vectors_config = self.get_vectors_config(),
            sparse_vectors_config = self.get_sparse_vectors_config(),
            **self.get_collection_config(**kwargs),
        )
        await self.on_collection_state('create', is_async = True)
        if not skip_init_index: await self._ainit_collection_index(**kwargs)
        self._initialized = True

    def init_collection(
        self,
        skip_init_index: t.Optional[bool] = None,
        is_async: t.Optional[bool] = True,
        **kwargs,
    ):
        """
        Initializes the collection
        """
        func = self._ainit_collection if is_async else self._init_collection
        return func(skip_init_index = skip_init_index, **kwargs)

    def _delete_collection(self, **kwargs):
        """
        Deletes the existing collection
        """
        if self.collection_name is None: raise ValueError('Collection Name is None')
        if not self.client.collection_exists(self.collection_name): 
            self.autologger.warning(f'Collection: `|g|{self.collection_name}|e|` does not exist', colored = True)
            return
        self.autologger.info(f'Deleting Collection: `|g|{self.collection_name}|e|`', colored = True)
        self.client.delete_collection(
            collection_name = self.collection_name,
        )
        self.on_collection_state('deletion', is_async = False)
        self._initialized = False
        self._ingested = False

    async def _adelete_collection(self, **kwargs):
        """
        Deletes the existing collection
        """
        if self.collection_name is None: raise ValueError('Collection Name is None')
        if not await self.client.acollection_exists(self.collection_name): 
            self.autologger.warning(f'Collection: `|g|{self.collection_name}|e|` does not exist', colored = True)
            return
        self.autologger.info(f'Deleting Collection: `|g|{self.collection_name}|e|`', colored = True)
        await self.client.adelete_collection(
            collection_name = self.collection_name,
        )
        await self.on_collection_state('deletion', is_async = True)
        self._initialized = False
        self._ingested = False

    def delete_collection(self, is_async: t.Optional[bool] = True, **kwargs):
        """
        Deletes the existing collection
        """
        func = self._adelete_collection if is_async else self._delete_collection
        return func(**kwargs)

    def _recreate_collection(self, skip_init_index: t.Optional[bool] = None, **kwargs):
        """
        Recreates the existing collection with Upsert Operation
        """
        if self.collection_name is None: raise ValueError('Collection Name is None')
        if self.client.collection_exists(self.collection_name):  
            self.delete_collection(is_async = False, **kwargs)
        self.init_collection(skip_init_index = skip_init_index, is_async = False, **kwargs)
        self.on_collection_state('recreate', is_async = False)

    async def _arecreate_collection(self, skip_init_index: t.Optional[bool] = None, **kwargs):
        """
        Recreates the existing collection with Upsert Operation
        """
        if self.collection_name is None: raise ValueError('Collection Name is None')
        if await self.client.acollection_exists(self.collection_name):  
            await self.delete_collection(is_async = True, **kwargs)
        await self.init_collection(skip_init_index = skip_init_index, is_async = True, **kwargs)
        await self.on_collection_state('recreate', is_async = True)

    def recreate_collection(self, skip_init_index: t.Optional[bool] = None, is_async: t.Optional[bool] = True, **kwargs):
        """
        Recreates the existing collection with an Upsert Operation
        """
        func = self._arecreate_collection if is_async else self._recreate_collection
        return func(skip_init_index = skip_init_index, **kwargs)

    """
    Ingestion Methods
    """

    def dataset_iterator(self, **kwargs) -> t.Generator[t.Tuple[str, str, t.Dict[str, t.Any]], None, None]:
        """
        Returns an iterator for the dataset

        - This should be overwritten by a downstream method
        """
        yield
        raise NotImplementedError
    

    async def dataset_aiterator(self, **kwargs) -> t.AsyncGenerator[t.Tuple[str, str, t.Dict[str, t.Any]], None]:
        """
        Returns an async iterator for the dataset

        - This should be overwritten by a downstream method
        """
        yield
        raise NotImplementedError


    def _build_dataset(
        self,
        batch_size: t.Optional[int] = None,
        max_items: t.Optional[int] = None,
        parallel: t.Optional[int] = None,
        **kwargs,
    ):
        """
        Builds the dataset

        - This should be overwritten by a downstream method
        """
        raise NotImplementedError('This method should be overwritten by a downstream method')

    async def _abuild_dataset(
        self,
        batch_size: t.Optional[int] = None,
        max_items: t.Optional[int] = None,
        parallel: t.Optional[int] = None,
        **kwargs,
    ):
        """
        Builds the dataset

        - This should be overwritten by a downstream method
        """
        raise NotImplementedError('This method should be overwritten by a downstream method')

    def _init_dataset(
        self,
        batch_size: t.Optional[int] = None,
        max_items: t.Optional[int] = None,
        log_every: t.Optional[int] = None,
        parallel: t.Optional[int] = None,
        **kwargs,
    ):
        """
        Initializes the dataset
        """
        if not self.has_dataset: return
        if self._ingested: return
        self.autologger.info(f'Initializing Dataset: `|g|{self.collection_name}|e|`', colored = True)
        batch_size = batch_size or self.ds_batch_size
        log_every = log_every if log_every is not None else self.ds_log_every
        result = self._build_dataset(batch_size = batch_size, max_items = max_items, log_every = log_every, parallel = parallel, **kwargs)
        self._ingested = True
        return result
    
    async def _ainit_dataset(
        self,
        batch_size: t.Optional[int] = None,
        max_items: t.Optional[int] = None,
        log_every: t.Optional[int] = None,
        parallel: t.Optional[int] = None,
        **kwargs,
    ):
        """
        Initializes the dataset
        """
        if not self.has_dataset: return
        if self._ingested: return
        self.autologger.info(f'Initializing Dataset: `|g|{self.collection_name}|e|`', colored = True)
        batch_size = batch_size or self.ds_batch_size
        log_every = log_every if log_every is not None else self.ds_log_every
        result = await self._abuild_dataset(batch_size = batch_size, max_items = max_items, log_every = log_every, parallel = parallel, **kwargs)
        self._ingested = True
        return result
    
    def init_dataset(
        self,
        batch_size: t.Optional[int] = None,
        max_items: t.Optional[int] = None,
        log_every: t.Optional[int] = None,
        parallel: t.Optional[int] = None,
        is_async: t.Optional[bool] = True,
        **kwargs,
    ):
        """
        Ingests the dataset
        """
        func = self._ainit_dataset if is_async else self._init_dataset
        return func(batch_size = batch_size, max_items = max_items, log_every = log_every, parallel = parallel, **kwargs)


    """
    Search Methods
    """

    def _filter_datetime_parse(
        self,
        key: str,
        value: t.Union[str, int, datetime.datetime, t.Tuple[datetime.datetime, datetime.datetime]],
    ) -> 'qm.FieldCondition':
        """
        Parses the datetime Filter
        
        Possible Values:
        - str
            - '> 2023-08-16'
            - '< 2023-08-16'
            - '>= 2023-08-16'

        - datetime.datetime: we assume that it is always greater than for now.
            - 2023-08-16T00:00:00
            - 2023-08-16
        
        # - int: we assume that it is always greater than for now.
        #     - 
        """
        range_obj = self.qm.DatetimeRange()
        if isinstance(value, tuple):
            start, end = value
            start = parse_datetime(start)
            end = parse_datetime(end)
            setattr(range_obj, 'gte', start)
            setattr(range_obj, 'lte', end)

        elif isinstance(value, str): 
            if value.startswith('>') or value.startswith('<'):
                operator, value = value.split(' ', 1)
                value = parse_datetime(value.strip())
                setattr(range_obj, comp_op[operator], value)
            else:
                value = parse_datetime(value)
                setattr(range_obj, 'gt', value)
        elif isinstance(value, datetime.datetime):
            value = parse_datetime(value)
            setattr(range_obj, 'gt', value)
        
        elif isinstance(value, int):
            now = datetime.datetime.now(tz = datetime.timezone.utc) - datetime.timedelta(days = value)
            setattr(range_obj, 'gt', now)
        return self.qm.FieldCondition(key = key, range = range_obj)
            
    def _filter_numeric_parse(
        self,
        key: str,
        value: t.Union[str, int, float, t.Tuple[float, float]],
    ) -> 'qm.FieldCondition':
        """
        Parses the numeric Filter
        
        Possible Values:
        - str
            - '50 - 100'
            - '< 100'
            - '>= 100'
        
        - int: we assume that it is always greater than for now.
            - 50

        - float: we assume that it is always greater than for now.
            - 50.0
        """
        range_obj = self.qm.Range()
        if isinstance(value, tuple):
            start, end = value
            setattr(range_obj, 'gte', start)
            setattr(range_obj, 'lte', end)

        elif isinstance(value, str): 
            if value.startswith('>') or value.startswith('<'):
                operator, value = value.split(' ', 1)
                value = float(value.strip())
                setattr(range_obj, comp_op[operator], value)
            elif '-' in value:
                start, end = value.split('-', 1)
                start = float(start.strip())
                end = float(end.strip())
                setattr(range_obj, 'gte', start)
                setattr(range_obj, 'lte', end)
            else:
                value = float(value)
                setattr(range_obj, 'gt', value)
        else:
            value = float(value)
            setattr(range_obj, 'gt', value)
        return self.qm.FieldCondition(key = key, range = range_obj)

            

    def build_filters_for_search(
        self,
        query: t.Optional[str] = None,
        **kwargs,
    ) -> t.Tuple[str, t.Optional['qm.Filter']]:
        """
        Builds the filters for the search
        """
        raise NotImplementedError
        # query = query or ""
        # filters = []
        # min_filters = []

    def rerank_results(
        self,
        query: str,
        results: t.List['QueryResponse'],
    ) -> t.List['QueryResponse']:
        """
        Reranks the results
        """
        description_hits = [hit.document for hit in results]
        new_scores = list(self.reranker.rerank(query, description_hits))
        ranking = list(enumerate(new_scores)) #saving document indices
        ranking.sort(key=lambda x: x[1], reverse=True) #sorting them in order of relevance defined by reranker

        # return the rerank the results
        return [results[rank[0]] for rank in ranking]


    def _fast_query(
        self,
        limit: t.Optional[int] = None,
        **filters: t.Any,
    ) -> t.List[QdrantModelT]:
        """
        Does a Fast Search Query using Scroll
        """
        _, filters = self.build_filters_for_search(**filters)
        limit = limit or 10
        cursor = self.client.scroll(
            collection_name = self.collection_name,
            scroll_filter = filters,
            limit = limit,
            with_payload = True,
            timeout = 60 * 60,
        )
        results, _ = cursor
        if results:
            return [self.schema.model_validate(hit, context = {'source': 'qdrant'}) for hit in results]
        return []
    
    async def _afast_query(
        self,
        limit: t.Optional[int] = None,
        **filters: t.Any,
    ) -> t.List[QdrantModelT]:
        """
        Does a Fast Search Query using Scroll
        """
        _, filters = self.build_filters_for_search(**filters)
        limit = limit or 10
        cursor = await self.client.ascroll(
            collection_name = self.collection_name,
            scroll_filter = filters,
            limit = limit,
            with_payload = True,
            timeout = 60 * 60,
        )
        results, _ = cursor
        if results:
            return [self.schema.model_validate(hit, context = {'source': 'qdrant'}) for hit in results]
        return []

    def fast_query(
        self,
        limit: t.Optional[int] = None,
        is_async: t.Optional[bool] = True,
        **filters: t.Any,
    ) -> t.List[QdrantModelT] | t.Awaitable[t.List[QdrantModelT]]:
        """
        Does a Fast Search Query using Scroll
        """
        func = self._afast_query if is_async else self._fast_query
        return func(limit = limit, **filters)

    def _query(
        self,
        query: t.Optional[str] = None,
        limit: t.Optional[int] = None,
        **filters: t.Any,
    ) -> t.List[QdrantModelT]:
        """
        Queries the collection
        """
        query, filters = self.build_filters_for_search(query = query, **filters)
        limit = limit or 10
        results = self.client.query(
            collection_name = self.collection_name,
            query_text = query,
            query_filter = filters,
            limit = limit,
        )
        if results:
            if self.has_reranker:
                results = self.rerank_results(query = query, results = results)
            return [self.schema.model_validate(hit, context = {'source': 'qdrant'}) for hit in results]
        return []

    async def _aquery(
        self,
        query: t.Optional[str] = None,
        limit: t.Optional[int] = None,
        **filters: t.Any,
    ) -> t.List[QdrantModelT]:
        """
        Queries the collection
        """
        query, filters = self.build_filters_for_search(query = query, **filters)
        limit = limit or 10
        results = await self.client.aquery(
            collection_name = self.collection_name,
            query_text = query,
            query_filter = filters,
            limit = limit,
        )
        if results:
            if self.has_reranker:
                results = self.rerank_results(query = query, results = results)
            return [self.schema.model_validate(hit, context = {'source': 'qdrant'}) for hit in results]
        return []
    
    def query(
        self,
        query: t.Optional[str] = None,
        limit: t.Optional[int] = None,
        is_async: t.Optional[bool] = True,
        **filters: t.Any,
    ) -> t.List[QdrantModelT] | t.Awaitable[t.List[QdrantModelT]]:
        """
        Queries the collection
        """
        func = self._aquery if is_async else self._query
        return func(query = query, limit = limit, **filters)

    def _search(
        self,
        query: t.Optional[str] = None,
        limit: t.Optional[int] = None,
        is_async: t.Optional[bool] = True,
        **filters: t.Any,
    ) -> t.List[QdrantModelT]:
        """
        Queries/Searches the collection
        """
        query, filters = self.build_filters_for_search(query = query, **filters)
        limit = limit or 10
        if query:
            results = self.client.query(
                collection_name = self.collection_name,
                query_text = query,
                query_filter = filters,
                limit = limit,
            )
            if results:
                if self.has_reranker:
                    results = self.rerank_results(query = query, results = results)
        else:
            cursor = self.client.scroll(
                collection_name = self.collection_name,
                scroll_filter = filters,
                limit = limit,
                with_payload = True,
                timeout = 60 * 60,
            )
            results, _ = cursor
        if results: 
            return [self.schema.model_validate(hit, context = {'source': 'qdrant'}) for hit in results]
        return []

    async def _asearch(
        self,
        query: t.Optional[str] = None,
        limit: t.Optional[int] = None,
        is_async: t.Optional[bool] = True,
        **filters: t.Any,
    ) -> t.List[QdrantModelT]:
        """
        Queries/Searches the collection
        """
        query, filters = self.build_filters_for_search(query = query, **filters)
        limit = limit or 10
        if query:
            results = await self.client.aquery(
                collection_name = self.collection_name,
                query_text = query,
                query_filter = filters,
                limit = limit,
            )
            if results:
                if self.has_reranker:
                    results = self.rerank_results(query = query, results = results)
        else:
            cursor = await self.client.ascroll(
                collection_name = self.collection_name,
                scroll_filter = filters,
                limit = limit,
                with_payload = True,
                timeout = 60 * 60,
            )
            results, _ = cursor
        if results: 
            return [self.schema.model_validate(hit, context = {'source': 'qdrant'}) for hit in results]
        return []

    def search(
        self,
        query: t.Optional[str] = None,
        limit: t.Optional[int] = None,
        is_async: t.Optional[bool] = True,
        **filters: t.Any,
    ) -> t.List[QdrantModelT] | t.Awaitable[t.List[QdrantModelT]]:
        """
        Queries/Searches the collection
        """
        func = self._asearch if is_async else self._search
        return func(query = query, limit = limit, **filters)

    
    def _points_iterator(
        self,
        ids: t.Optional[t.Iterable['qm.ExtendedPointId']],
        metadata: t.Optional[t.Iterable[dict[str, t.Any]]],
        encoded_docs: t.Iterable[tuple[str, list[float]]],
        ids_accumulator: list,
        sparse_vectors: t.Optional[t.Iterable['ct.SparseVector']] = None,
        callback: t.Optional[t.Callable[[t.Any], None]] = None,
    ) -> t.Iterable['qm.PointStruct']:
        """
        The Points Iterator is a generator that yields PointStruct objects.
        """
        for point in self.client.sapi._points_iterator(
            ids = ids,
            metadata = metadata,
            encoded_docs = encoded_docs,
            ids_accumulator = ids_accumulator,
            sparse_vectors = sparse_vectors,
        ):
            yield point
            if callback: callback(point)
        
    
    def add(
        self,
        documents: t.Iterable[str],
        metadata: t.Optional[t.Iterable[dict[str, t.Any]]] = None,
        ids: t.Optional[t.Iterable['qm.ExtendedPointId']] = None,
        batch_size: int = 32,
        parallel: t.Optional[int] = None,
        callback: t.Optional[t.Callable[[t.Any], None]] = None,
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
        # Wrapper method for the add method
        if not self._initialized: self.init_collection(is_async = False)
        encoded_docs = self.client.sapi._embed_documents(
            documents=documents,
            embedding_model_name=self.client.sapi.embedding_model_name,
            batch_size=batch_size,
            embed_type="passage",
            parallel=parallel,
        )
        encoded_sparse_docs = None
        if self.client.sapi.sparse_embedding_model_name is not None:
            encoded_sparse_docs = self.client.sapi._sparse_embed_documents(
                documents = documents,
                embedding_model_name = self.client.sapi.sparse_embedding_model_name,
                batch_size = batch_size,
                parallel = parallel,
            )
        inserted_ids: list = []
        points = self._points_iterator(
            ids = ids,
            metadata = metadata,
            encoded_docs = encoded_docs,
            ids_accumulator = inserted_ids,
            sparse_vectors = encoded_sparse_docs,
            callback = callback,
        )
        # points = self.client.sapi._points_iterator(
        #     ids = ids,
        #     metadata = metadata,
        #     encoded_docs = encoded_docs,
        #     ids_accumulator = inserted_ids,
        #     sparse_vectors = encoded_sparse_docs,
        # )
        self.client.sapi.upload_points(
            collection_name = self.collection_name,
            points = points,
            wait = True,
            parallel = parallel or 1,
            batch_size = batch_size,
            **kwargs,
        )
        if ids and len(inserted_ids) != len(ids):
            missing_ids = set(ids) - set(inserted_ids)
            self.logger.warning(f'Some IDs were not inserted: {missing_ids} ({len(missing_ids)} missing)')
        return inserted_ids

    def _apoints_iterator(
        self,
        ids: t.Optional[t.Iterable['qm.ExtendedPointId']],
        metadata: t.Optional[t.Iterable[dict[str, t.Any]]],
        encoded_docs: t.Iterable[tuple[str, list[float]]],
        ids_accumulator: list,
        sparse_vectors: t.Optional[t.Iterable['ct.SparseVector']] = None,
        callback: t.Optional[t.Callable[[t.Any], None]] = None,
    ) -> t.Iterable['qm.PointStruct']:
        """
        [Async Client] The Points Iterator is a generator that yields PointStruct objects.
        """
        for point in self.client.api._points_iterator(
            ids = ids,
            metadata = metadata,
            encoded_docs = encoded_docs,
            ids_accumulator = ids_accumulator,
            sparse_vectors = sparse_vectors,
        ):
            yield point
            if callback: callback(point)

    async def aadd(
        self,
        documents: t.Iterable[str],
        metadata: t.Optional[t.Iterable[dict[str, t.Any]]] = None,
        ids: t.Optional[t.Iterable['qm.ExtendedPointId']] = None,
        batch_size: int = 32,
        parallel: t.Optional[int] = None,
        callback: t.Optional[t.Callable[[t.Any], None]] = None,
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
        if not self._initialized: await self.init_collection(is_async = True)
        encoded_docs = self.client.api._embed_documents(
            documents=documents,
            embedding_model_name=self.client.api.embedding_model_name,
            batch_size=batch_size,
            embed_type="passage",
            parallel=parallel,
        )
        encoded_sparse_docs = None
        if self.client.api.sparse_embedding_model_name is not None:
            encoded_sparse_docs = self.client.api._sparse_embed_documents(
                documents = documents,
                embedding_model_name = self.client.api.sparse_embedding_model_name,
                batch_size = batch_size,
                parallel = parallel,
            )
        inserted_ids: list = []
        points = self._apoints_iterator(
            ids = ids,
            metadata = metadata,
            encoded_docs = encoded_docs,
            ids_accumulator = inserted_ids,
            sparse_vectors = encoded_sparse_docs,
            callback = callback,
        )
        # points = self.client.api._points_iterator(
        #     ids = ids,
        #     metadata = metadata,
        #     encoded_docs = encoded_docs,
        #     ids_accumulator = inserted_ids,
        #     sparse_vectors = encoded_sparse_docs,
        # )
        self.client.api.upload_points(
            collection_name = self.collection_name,
            points = points,
            wait = True,
            parallel = parallel or 1,
            batch_size = batch_size,
            **kwargs,
        )
        if ids and len(inserted_ids) != len(ids):
            missing_ids = set(ids) - set(inserted_ids)
            self.logger.warning(f'Some IDs were not inserted: {missing_ids} ({len(missing_ids)} missing)')
        # self.logger.info(f'{inserted_ids}', prefix = f'{len(inserted_ids)}', colored = True)
        return inserted_ids

    """
    Setup Methods
    """
    @classmethod
    def _setup_(
        cls: t.Type['QdrantSearcher'],
        # Init Keywords
        collection_name: t.Optional[str] = None,
        schema: t.Optional[t.Type[QdrantModelT]] = None,
        dense_model: t.Optional[str] = None,
        sparse_model: t.Optional[str] = None,
        rerank_model: t.Optional[str] = None,
        debug_enabled: t.Optional[bool] = None,
        on_disk_default: t.Optional[bool] = None,
        on_disk_by_type: t.Optional[t.Dict[str, bool]] = None,
        on_disk_by_field: t.Optional[t.Dict[str, bool]] = None,
        has_dataset: t.Optional[bool] = None,
        

        # Initializers
        skip_init_collection: t.Optional[bool] = None,
        skip_init_index: t.Optional[bool] = None,
        skip_init_dataset: t.Optional[bool] = None,

        # Ingestion Kwargs
        dataset_batch_size: t.Optional[int] = None,
        dataset_max_items: t.Optional[int] = None,
        dataset_log_every: t.Optional[int] = None,

        # Downstream Kwargs
        init_collection_kwargs: t.Optional[t.Dict[str, t.Any]] = None,
        init_dataset_kwargs: t.Optional[t.Dict[str, t.Any]] = None,

        # Model Config
        set_cuda: t.Optional[bool | str] = None,
        set_model_config: t.Optional[t.Dict[str, t.Any]] = None,
        set_sparse_model_config: t.Optional[t.Dict[str, t.Any]] = None,

        **kwargs,        
    ) -> 'QdrantSearcher':
        """
        Sets up the Qdrant Searchable Text Collection
        """

        new = cls(
            collection_name = collection_name,
            schema = schema,
            dense_model = dense_model,
            sparse_model = sparse_model,
            rerank_model = rerank_model,
            debug_enabled = debug_enabled,
            on_disk_default = on_disk_default,
            on_disk_by_type = on_disk_by_type,
            on_disk_by_field = on_disk_by_field,
            has_dataset = has_dataset,
            **kwargs,
        )
        if set_cuda and isinstance(set_cuda, str) and set_cuda.lower() == 'auto':
            from lzo.utils.system import get_torch_device_name
            set_cuda = get_torch_device_name() == 'cuda'
        
        if set_cuda and set_cuda is True:
            if not set_model_config: set_model_config = {}
            set_model_config['cuda'] = set_cuda
            if not set_sparse_model_config: set_sparse_model_config = {}
            set_sparse_model_config['cuda'] = set_cuda

        if set_model_config: new.client.shared_config.set_model_config.update(set_model_config)
        if set_sparse_model_config: new.client.shared_config.set_sparse_model_config.update(set_sparse_model_config)

        if not skip_init_collection: 
            new.init_collection(
                skip_init_index = skip_init_index,
                is_async = False,
                **(init_collection_kwargs or {}),
            )
        
        if new.has_dataset and not skip_init_dataset:
            new.init_dataset(
                batch_size = dataset_batch_size,
                max_items = dataset_max_items,
                log_every = dataset_log_every,
                is_async = False,
                **(init_dataset_kwargs or {}),
            )
        
        return new
    
    @classmethod
    async def _asetup_(
        cls: t.Type['QdrantSearcher'],
        # Init Keywords
        collection_name: t.Optional[str] = None,
        schema: t.Optional[t.Type[QdrantModelT]] = None,
        dense_model: t.Optional[str] = None,
        sparse_model: t.Optional[str] = None,
        rerank_model: t.Optional[str] = None,
        debug_enabled: t.Optional[bool] = None,
        on_disk_default: t.Optional[bool] = None,
        on_disk_by_type: t.Optional[t.Dict[str, bool]] = None,
        on_disk_by_field: t.Optional[t.Dict[str, bool]] = None,
        has_dataset: t.Optional[bool] = None,

        # Initializers
        skip_init_collection: t.Optional[bool] = None,
        skip_init_index: t.Optional[bool] = None,
        skip_init_dataset: t.Optional[bool] = None,

        # Ingestion Kwargs
        dataset_batch_size: t.Optional[int] = None,
        dataset_max_items: t.Optional[int] = None,
        dataset_log_every: t.Optional[int] = None,

        # Downstream Kwargs
        init_collection_kwargs: t.Optional[t.Dict[str, t.Any]] = None,
        init_dataset_kwargs: t.Optional[t.Dict[str, t.Any]] = None,

        # Model Config
        set_cuda: t.Optional[bool | str] = None,
        set_model_config: t.Optional[t.Dict[str, t.Any]] = None,
        set_sparse_model_config: t.Optional[t.Dict[str, t.Any]] = None,

        **kwargs,        
    ) -> 'QdrantSearcher':
        """
        Sets up the Qdrant Searchable Text Collection
        """

        new = cls(
            collection_name = collection_name,
            schema = schema,
            dense_model = dense_model,
            sparse_model = sparse_model,
            rerank_model = rerank_model,
            debug_enabled = debug_enabled,
            on_disk_default = on_disk_default,
            on_disk_by_type = on_disk_by_type,
            on_disk_by_field = on_disk_by_field,
            has_dataset = has_dataset,
            **kwargs,
        )
        if set_cuda and isinstance(set_cuda, str) and set_cuda.lower() == 'auto':
            from lzo.utils.system import get_torch_device_name
            set_cuda = get_torch_device_name() == 'cuda'
        
        if set_cuda and set_cuda is True:
            if not set_model_config: set_model_config = {}
            set_model_config['cuda'] = set_cuda
            if not set_sparse_model_config: set_sparse_model_config = {}
            set_sparse_model_config['cuda'] = set_cuda

        if set_model_config: new.client.shared_config.set_model_config.update(set_model_config)
        if set_sparse_model_config: new.client.shared_config.set_sparse_model_config.update(set_sparse_model_config)

        if not skip_init_collection: 
            await new.init_collection(
                skip_init_index = skip_init_index,
                is_async = True,
                **(init_collection_kwargs or {}),
            )
        
        if new.has_dataset and not skip_init_dataset:
            await new.init_dataset(
                batch_size = dataset_batch_size,
                max_items = dataset_max_items,
                log_every = dataset_log_every,
                is_async = True,
                **(init_dataset_kwargs or {}),
            )
        return new
    
    @classmethod
    def setup(
        cls: t.Type['QdrantSearcher'],
        # Init Keywords
        collection_name: t.Optional[str] = None,
        schema: t.Optional[t.Type[QdrantModelT]] = None,
        dense_model: t.Optional[str] = None,
        sparse_model: t.Optional[str] = None,
        rerank_model: t.Optional[str] = None,
        debug_enabled: t.Optional[bool] = None,
        on_disk_default: t.Optional[bool] = None,
        on_disk_by_type: t.Optional[t.Dict[str, bool]] = None,
        on_disk_by_field: t.Optional[t.Dict[str, bool]] = None,
        has_dataset: t.Optional[bool] = None,

        # Initializers
        skip_init_collection: t.Optional[bool] = None,
        skip_init_index: t.Optional[bool] = None,
        skip_init_dataset: t.Optional[bool] = None,

        # Ingestion Kwargs
        dataset_batch_size: t.Optional[int] = None,
        dataset_max_items: t.Optional[int] = None,
        dataset_log_every: t.Optional[int] = None,

        # Downstream Kwargs
        init_collection_kwargs: t.Optional[t.Dict[str, t.Any]] = None,
        init_dataset_kwargs: t.Optional[t.Dict[str, t.Any]] = None,

        # Model Config
        set_cuda: t.Optional[bool | str] = None,
        set_model_config: t.Optional[t.Dict[str, t.Any]] = None,
        set_sparse_model_config: t.Optional[t.Dict[str, t.Any]] = None,

        is_async: t.Optional[bool] = True,
        **kwargs,        
    ) -> 'QdrantSearcher' | t.Awaitable['QdrantSearcher']:
        """
        Sets up the Qdrant Searchable Text Collection
        """
        method = cls._asetup_ if is_async else cls._setup_
        return method(
            collection_name = collection_name,
            schema = schema,
            dense_model = dense_model,
            sparse_model = sparse_model,
            rerank_model = rerank_model,
            debug_enabled = debug_enabled,
            on_disk_default = on_disk_default,
            on_disk_by_type = on_disk_by_type,
            on_disk_by_field = on_disk_by_field,
            has_dataset = has_dataset,

            # Initializers
            skip_init_collection = skip_init_collection,
            skip_init_index = skip_init_index,
            skip_init_dataset = skip_init_dataset,

            # Ingestion Kwargs
            dataset_batch_size = dataset_batch_size,
            dataset_max_items = dataset_max_items,
            dataset_log_every = dataset_log_every,

            # Downstream Kwargs
            init_collection_kwargs = init_collection_kwargs,
            init_dataset_kwargs = init_dataset_kwargs,

            # Model Config
            set_cuda = set_cuda,
            set_model_config = set_model_config,
            set_sparse_model_config = set_sparse_model_config,
            **kwargs,
        )

    
QdrantSearcher = t.TypeVar('QdrantSearcher', bound = QdrantSearchMixin)