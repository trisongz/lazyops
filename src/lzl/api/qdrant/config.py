from __future__ import annotations

import fastembed.embedding
import fastembed.rerank.cross_encoder.onnx_text_cross_encoder

"""
Qdrant Configuration
"""

import os
import warnings
import typing as t

warnings.filterwarnings("ignore", message = "Api key is used with an insecure connection.", category = UserWarning)

# warnings.filterwarnings("ignore", message = "Api key is used with an insecure connection.", module = "qdrant_client")
import pathlib
from lzl import load
from lzl.proxied import ProxyObject
from lzo.types import BaseModel, BaseSettings, AppEnv, eproperty
from pydantic import model_validator, Field, PrivateAttr
from lzl.logging import logger, null_logger, Logger

if t.TYPE_CHECKING:
    from lzl.io import TemporaryData
    import fastembed
    import fastembed.text.clip_embedding
    import fastembed.text.multitask_embedding
    import fastembed.text.onnx_embedding
    import fastembed.text.pooled_embedding
    import fastembed.text.pooled_normalized_embedding
    import fastembed.rerank.cross_encoder
    import fastembed.sparse.splade_pp
    # import fastembed.rerank.cross_encoder.onnx_text_cross_encoder
    from .full_client import QdrantClient
    
else:
    fastembed = load.LazyLoad('fastembed', install_missing = True)


"""
Config File Schema:

pooled_normalized_models:
- model: Alibaba-NLP/gte-modernbert-base
  dim: 768
  description: Text embeddings, Unimodal (text), English, 8192 input tokens truncation, Prefixes for queries/documents: not necessary, 2024 year.
  license: apache-2.0
  size_in_GB: 0.59
  sources:
    hf: Alibaba-NLP/gte-modernbert-base
  model_file: onnx/model.onnx
"""


lib_path = pathlib.Path(__file__).parent


class QdrantSharedConfig(BaseModel):
    """
    The shared config for Qdrant
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
    kwargs: t.Optional[t.Dict[str, t.Any]] = Field(None, exclude = True)

    set_model: t.Optional[str] = Field(None, exclude = True)
    set_model_config: t.Optional[t.Dict[str, t.Any]] = Field(default_factory=dict, exclude = True)
    set_sparse_model: t.Optional[str] = Field(None, exclude = True)
    set_sparse_model_config: t.Optional[t.Dict[str, t.Any]] = Field(default_factory=dict, exclude = True)
    retries: t.Optional[int] = Field(None, exclude = True)


    @classmethod
    def build(
        cls, 
        # s: 'QdrantClientSettings',
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
        retries: t.Optional[int] = None,
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
            'retries': retries if retries is not None else c.settings.retries,
            'kwargs': kwargs,
        }
        new = {k:v for k,v in new.items() if v is not None}
        return cls.model_validate(new, context = {'source': 'build', 'client': c})

class QdrantClientSettings(BaseSettings):
    """
    The Qdrant Client Settings
    """

    url: t.Optional[str] = None
    port: t.Optional[int] = 6333
    grpc_port: t.Optional[int] = 6334
    prefer_grpc: t.Optional[bool] = False
    https: t.Optional[bool] = None
    api_key: t.Optional[str] = None
    prefix: t.Optional[str] = None
    timeout: t.Optional[int] = None
    host: t.Optional[str] = None
    path: t.Optional[str] = None

    # Extra
    fastembed_config: t.Optional[str] = None
    set_model: t.Optional[str] = None
    set_sparse_model: t.Optional[str] = None
    retries: t.Optional[int] = None


    class Config(BaseSettings.Config):
        env_prefix = "QDRANT_"

    @eproperty
    def temp_data(self) -> 'TemporaryData':
        """
        Returns the temporary data
        """
        from lzl.io.persistence import TemporaryData
        return TemporaryData(lib_path.joinpath('data'))

    @eproperty
    def added_fastembed_models(self) -> t.Set[str]:
        """
        Returns the already added fastembed models
        """
        return set()
        # return self._extra.get('added_fastembed_models', set())

    
    def add_fastembed_models_v1(
        self,
        
        # embedding
        clip_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,
        multitask_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,
        pooled_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,
        pooled_normalized_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,
        onnx_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,

        # added for reranking
        cross_encoder_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,
        
        # added for sparse models
        sparse_splade_pp_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,

        verbose: t.Optional[bool] = False,
        **kwargs: t.Any,
    ) -> None:
        """
        [v1] Adds the specified models to the list of added models

        This method is for adding models before v0.6.0
        """
        # Embedding
        if clip_models:
            for conf in clip_models:
                if conf['model'] not in self.added_fastembed_models:
                    if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `clip_models`', colored = True)
                    fastembed.text.clip_embedding.supported_clip_models.append(conf)
                    self.added_fastembed_models.add(conf['model'])

        if multitask_models:
            try:
                for conf in multitask_models:
                    if conf['model'] not in self.added_fastembed_models:
                        if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `multitask_models`', colored = True)
                        fastembed.text.multitask_embedding.supported_multitask_models.append(conf)
                        self.added_fastembed_models.add(conf['model'])
            except Exception as e:
                logger.trace('Unable to add multi-task models', e)

        if pooled_models:
            for conf in pooled_models:
                if conf['model'] not in self.added_fastembed_models:
                    if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `pooled_models`', colored = True)
                    fastembed.text.pooled_embedding.supported_pooled_models.append(conf)
                    self.added_fastembed_models.add(conf['model'])

        if pooled_normalized_models:
            for conf in pooled_normalized_models:
                if conf['model'] not in self.added_fastembed_models:
                    if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `pooled_normalized_models`', colored = True)
                    fastembed.text.pooled_normalized_embedding.supported_pooled_normalized_models.append(conf)
                    self.added_fastembed_models.add(conf['model'])

        if onnx_models:
            for conf in onnx_models:
                if conf['model'] not in self.added_fastembed_models:
                    if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `onnx_models`', colored = True)
                    fastembed.text.pooled_normalized_embedding.supported_pooled_normalized_models.append(conf)
                    self.added_fastembed_models.add(conf['model'])

        # Rerankers
        if cross_encoder_models:
            for conf in cross_encoder_models:
                if conf['model'] not in self.added_fastembed_models:
                    if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `cross_encoder_models`', colored = True)
                    fastembed.rerank.cross_encoder.onnx_text_cross_encoder.supported_onnx_models.append(conf)
                    self.added_fastembed_models.add(conf['model'])
        
        # Sparse Models
        if sparse_splade_pp_models:
            for conf in sparse_splade_pp_models:
                if conf['model'] not in self.added_fastembed_models:
                    if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `sparse_splade_pp_models`', colored = True)
                    fastembed.sparse.splade_pp.supported_splade_models.append(conf)
                    self.added_fastembed_models.add(conf['model'])

    def add_fastembed_models(
        self,
        
        # embedding
        clip_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,
        multitask_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,
        pooled_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,
        pooled_normalized_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,
        onnx_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,

        # added for reranking
        cross_encoder_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,
        
        # added for sparse models
        sparse_splade_pp_models: t.Optional[t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = None,

        verbose: t.Optional[bool] = False,
        **kwargs: t.Any,
    ) -> None:
        """
        Adds the specified models to the list of added models
        """
        try:
            from fastembed.common.model_description import PoolingType, BaseModelDescription, ModelSource, DenseModelDescription, SparseModelDescription
        except ImportError:
            return self.add_fastembed_models_v1(
                clip_models=clip_models,
                multitask_models=multitask_models,
                pooled_models=pooled_models,
                pooled_normalized_models=pooled_normalized_models,
                onnx_models=onnx_models,
                cross_encoder_models=cross_encoder_models,
                sparse_splade_pp_models=sparse_splade_pp_models,
                verbose=verbose,
                **kwargs,
            )
        
        # > 0.6.0
        # CLIP Models 
        if clip_models:
            for conf in clip_models:
                if conf['model'] not in self.added_fastembed_models:
                    if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `clip_models`', colored = True)
                    sources = ModelSource(**conf.pop('sources'))
                    fastembed.text.clip_embedding.supported_clip_models.append(
                        DenseModelDescription(
                            sources = sources,
                            **conf
                        )
                    )
                    self.added_fastembed_models.add(conf['model'])
    
        if multitask_models:
            try:
                for conf in multitask_models:
                    if conf['model'] not in self.added_fastembed_models:
                        if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `multitask_models`', colored = True)
                        sources = ModelSource(**conf.pop('sources'))
                        fastembed.text.multitask_embedding.supported_multitask_models.append(
                            DenseModelDescription(
                                sources = sources,
                                **conf
                            )
                        )
                        self.added_fastembed_models.add(conf['model'])
            except Exception as e:
                logger.trace('Unable to add multi-task models', e)

        if pooled_models:
            for conf in pooled_models:
                if conf['model'] not in self.added_fastembed_models:
                    if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `pooled_models`', colored = True)
                    sources = ModelSource(**conf.pop('sources'))
                    fastembed.text.pooled_embedding.supported_pooled_models.append(
                        DenseModelDescription(
                            sources = sources,
                            **conf
                        )
                    )
                    # fastembed.text.pooled_embedding.supported_pooled_models.append(conf)
                    self.added_fastembed_models.add(conf['model'])

        if pooled_normalized_models:
            for conf in pooled_normalized_models:
                if conf['model'] not in self.added_fastembed_models:
                    if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `pooled_normalized_models`', colored = True)
                    sources = ModelSource(**conf.pop('sources'))
                    fastembed.text.pooled_normalized_embedding.supported_pooled_normalized_models.append(
                        DenseModelDescription(
                            sources = sources,
                            **conf
                        )
                    )
                    self.added_fastembed_models.add(conf['model'])

        if onnx_models:
            for conf in onnx_models:
                if conf['model'] not in self.added_fastembed_models:
                    if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `onnx_models`', colored = True)
                    sources = ModelSource(**conf.pop('sources'))
                    fastembed.text.onnx_embedding.supported_onnx_models.append(
                        DenseModelDescription(
                            sources = sources,
                            **conf
                        )
                    )
                    self.added_fastembed_models.add(conf['model'])

        # Rerankers
        if cross_encoder_models:
            for conf in cross_encoder_models:
                if conf['model'] not in self.added_fastembed_models:
                    if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `cross_encoder_models`', colored = True)
                    sources = ModelSource(**conf.pop('sources'))
                    fastembed.rerank.cross_encoder.onnx_text_cross_encoder.supported_onnx_models.append(
                        BaseModelDescription(
                            sources = sources,
                            **conf
                        )
                    )
                    self.added_fastembed_models.add(conf['model'])
        
        # Sparse Models
        if sparse_splade_pp_models:
            for conf in sparse_splade_pp_models:
                if conf['model'] not in self.added_fastembed_models:
                    if verbose: logger.info(f'Adding Model |g|{conf["model"]}|e| to `sparse_splade_pp_models`', colored = True)
                    sources = ModelSource(**conf.pop('sources'))
                    fastembed.sparse.splade_pp.supported_splade_models.append(
                        SparseModelDescription(
                            sources = sources,
                            **conf
                        )
                    )
                    self.added_fastembed_models.add(conf['model'])

        
    
    def _load_fastembed_configs(self, config: t.Optional[str]):
        """
        Loads the fastembed configs from a file
        """
        import yaml
        from lzl.io import File
        config_file = File(config)
        if not config_file.exists(): raise ValueError(f'Config File cannot be loaded from: `{config}`')
        if not self.temp_data.has_logged(f'config_file:load:{config_file.as_posix()}'):
            logger.info(f'Loading from Config File: `{config_file}`')
        
        config_data: t.Dict[str, t.List[t.Dict[str, t.Union[str, int, t.Dict[str, str]]]]] = yaml.safe_load(config_file.read_text())
        self.add_fastembed_models(**config_data)


    @model_validator(mode = 'after')
    def validate_config(self):
        """
        Validates the config
        """
        if self.fastembed_config: self._load_fastembed_configs(self.fastembed_config)
        return self
    

settings: QdrantClientSettings = ProxyObject(
    QdrantClientSettings
)