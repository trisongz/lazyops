from __future__ import annotations

"""
TemporalIO Config
"""
import os
import typing as t
from urllib.parse import urlparse
from lzo.types import BaseSettings, model_validator, Field
from lzl.types import eproperty
from lzl.proxied import ProxyObject
from lzl.io import File
from lzl.load import lazy_import
from lzo.utils.helpers.envvars import replace_envvars_in_text
from ..utils import logger
from .worker import TemporalWorkerConfig
from .telemetry import TemporalTelemetrySettings

if t.TYPE_CHECKING:
    from lzl.io.persistence import TemporaryData
    from temporalio.converter import DataConverter
    from temporalio.worker import Interceptor
    from temporalio.runtime import Runtime, TelemetryConfig
    from lzl.ext.temporal.loop.config import RuntimeConfig
    from lzl.ext.temporal.client import TemporalClient
    from ..registry import TemporalRegistry


class TemporalSettings(BaseSettings):
    """
    Temporal Settings
    """

    url: t.Optional[str] = Field(None, description = "The Temporal URL. Use a full URL including the protocol so that it can be parsed correctly, such as `https://localhost:7233`")
    host: t.Optional[str] = Field(None, description = "The Temporal host. Use a FQDN with the port such as `localhost:7233`")
    api_key: t.Optional[str] = Field(None, description = "The Temporal API Key")
    namespace: t.Optional[str] = Field('default', description = "The Temporal namespace")
    tls: t.Optional[bool] = Field(None, description = "If false, the default, do not use TLS. If true, use system default TLS configuration. If TLS configuration present, that TLS configuration will be used.")
    identity: t.Optional[str] = Field(None, description = "Identity for this client. If unset, a default is created based on the version of the SDK.")
    
    interceptors: t.List[str] = Field(default_factory=list, description = "The interceptors to use for the client")
    converter: t.Optional[str] = Field("serialized", description = "The converter to use for the client")

    default_factory: t.Optional[str] = Field(default="lzl.ext.temporal.loop.worker:WorkerFactory", description = "The worker factory to use for creating workers")
    pre_init: t.List[str] = Field(default_factory=list, description = "The pre-init functions to run before the worker is initialized")

    max_concurrent_activities: int = Field(default=100, description = "The maximum number of concurrent activities to run")
    max_concurrent_workflow_tasks: int = Field(default=100, description = "The maximum number of concurrent workflow tasks to run")
    disable_eager_activity_execution: bool = Field(default=True, description = "If true, the worker will not eagerly execute activities. This can improve performance for large workflows.")
    # metric_bind_address: str = Field(default="0.0.0.0:9000", description = "The address to bind the metrics server to")

    lazy: t.Optional[bool] = Field(None, description = "If true, the client will not connect until the first call is attempted. If false, the client will connect immediately.")
    default_task_queue: t.Optional[str] = Field(None, description = "The default task queue to use for this client.")

    data_jsonlib: t.Optional[str] = Field(None, description = "The JSON library to use for data conversion")
    data_compression: t.Optional[str] = Field(None, description = "The compression to use for data conversion")
    data_compression_level: t.Optional[int] = Field(None, description = "The compression level to use for data conversion")

    workers: t.List[TemporalWorkerConfig] = Field(default_factory=list, description = "The workers to use for the client")
    config_file: t.Optional[File] = Field(None, description = "The config file to load the settings from")
    client_class: t.Optional[str] = Field(None, description = "The client class to use")

    @model_validator(mode = 'after')
    def validate_settings(self):
        """
        Validates the settings
        """
        if self.config_file is not None:
            self._load_from_config_file_(self.config_file)
        if self.url is not None:
            self._construct_endpoint_()
        return self
    
    @eproperty
    def telemetry(self) -> TemporalTelemetrySettings:
        """
        Returns the Telemetry Settings
        """
        return TemporalTelemetrySettings()

    def _construct_endpoint_(self):
        """
        Constructs the URL Endpoint
        """
        url = urlparse(self.url)
        self.host = f'{url.hostname}:'
        if url.port: self.host += str(url.port)
        elif url.scheme == 'http': self.host += '80'
        elif url.scheme == 'https': self.host += '443'
        elif url.scheme in {'grpc', 'grpcs'}: self.host += '7233'
        else: raise ValueError(f'Invalid URL: {self.url} with Unknown Scheme: {url.scheme}')
        if url.scheme not in {'https', 'grpcs'}: self.tls = False
        if url.password or url.username: self.api_key = url.password or url.username
        if not self.tmpdata.has_logged(f'tmprl:settings:endpoint:{self.host}'):
            msg = ''
            if self.tls: msg += '|g|TLS|e|: Enabled'
            if self.api_key: msg += ', |g|Auth|e|: Enabled'
            if msg: msg = f" ({msg.lstrip(', ')})"    
            logger.info(f'Endpoint: `|g|{self.host}|e|`{msg}', prefix = 'Temporal', colored = True)
    
    def _handle_config_data_pre_(self, config_data: t.Dict[str, t.Any]):
        """
        Passthrough function to handle config data before it is loaded
        """
        pass
        
    def _handle_config_data_post_(self, config_data: t.Dict[str, t.Any]):
        """
        Passthrough function to handle config data after it is loaded
        """
        pass

    def _load_from_config_file_(self, config_file: File):
        """
        Loads the settings from a config file
        """
        import yaml
        config_file = File(config_file)
        config_text = replace_envvars_in_text(config_file.read_text())
        config_data: t.Dict[str, t.Any] = yaml.safe_load(config_text)
        self._handle_config_data_pre_(config_data)
        if config_data.get('workers'):
            for worker in config_data.pop('workers'):
                self.workers.append(TemporalWorkerConfig(**worker))
        elif config_data.get('worker'):
            self.workers.append(TemporalWorkerConfig(**config_data.pop('worker')))
        if config_data.get('telemetry'):
            self.telemetry.update(config_data.pop('telemetry'))
        self._handle_config_data_post_(config_data)
        for k,v in config_data.items():
            if hasattr(self, k): setattr(self, k, v)


    @property
    def client_kwargs(self) -> t.Dict[str, t.Any]:
        """
        Returns the client kwargs
        """
        kws = {
            'target_host': self.host,
            'namespace': self.namespace,
            'api_key': self.api_key,
            'tls': self.tls,
            'identity': self.identity,
            'lazy': self.lazy,
        }
        return {k: v for k,v in kws.items() if v is not None}
    
    def get_data_converter(
        self,
        converter: t.Optional[str] = None,
        jsonlib: t.Optional[str] = None,
        compression: t.Optional[str] = None,
        compression_level: t.Optional[int] = None,
        **kwargs,
    ) -> 'DataConverter':
        """
        Returns the data converter
        """
        from lzl.ext.temporal.io import get_default_data_converter
        return get_default_data_converter(
            converter = converter,
            jsonlib = jsonlib,
            compression = compression,
            compression_level = compression_level,
            **kwargs,
        )

    @eproperty
    def data_converter(self) -> 'DataConverter':
        """
        Returns the data converter
        """
        return self.get_data_converter(
            converter = self.converter,
            jsonlib = self.data_jsonlib,
            compression = self.data_compression,
            compression_level = self.data_compression_level,
            config = self,
        )
    
    @eproperty
    def tmpdata(self) -> 'TemporaryData':
        """
        Returns the temporary data
        """
        from lzl.io.persistence import TemporaryData
        return TemporaryData.from_module('lzl')
    
    @eproperty
    def registry(self) -> 'TemporalRegistry':
        """
        Returns the Temporal Registry
        """
        from lzl.ext.temporal.registry import registry
        return registry
    
    @eproperty
    def client_cls(self) -> t.Type['TemporalClient']:
        """
        Returns the Temporal Client Class
        """
        if self.client_class: return lazy_import(self.client_class)
        from lzl.ext.temporal.client import TemporalClient
        return TemporalClient
    
    def load_functions(self, *funcs: t.Sequence[t.Union[str, t.Type[t.Any]]], initialize: t.Optional[bool] = None) -> t.List[t.Any]:
        """
        Loads the functions
        """
        _funcs = []
        for func in funcs:
            if isinstance(func, str): func = lazy_import(func)
            if initialize: func = func()
            _funcs.append(func)
        return _funcs

    def build_runtime(
        self,
        runtime: t.Optional[str | t.Type['Runtime']] = None,
        telemetry: t.Optional['TelemetryConfig'] = None,
        **kwargs,
    ) -> t.Optional['Runtime']:
        """
        Builds the Runtime
        """
        if not telemetry and not runtime: return None
        if not runtime:
            from temporalio.runtime import Runtime
            runtime = Runtime
        elif isinstance(runtime, str): runtime = lazy_import(runtime)
        return runtime(telemetry = telemetry, **kwargs)

    async def get_client(
        self,
        host: t.Optional[str] = None,
        api_key: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        converter: t.Optional[str] = None,
        interceptors: t.Sequence[t.Union[t.Type['Interceptor'], str]] | None = None,
        runtime: t.Optional[t.Type['Runtime'] | str] = None,
        telemetry: t.Optional[bool | str] = None,
        telemetry_config: t.Optional[t.Dict[str, t.Any]] = None,
        telemetry_init_kwargs: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs,
    ) -> 'TemporalClient':
        """
        Returns the Temporal Client
        """
        if not host: host = self.host
        if not api_key and self.api_key: api_key = self.api_key
        if not namespace: namespace = self.namespace
        if not converter: converter = self.data_converter
        else: converter = self.get_data_converter(converter = converter)
        
        if interceptors: interceptors = self.load_functions(*interceptors, initialize = True)
        else: interceptors = []

        if telemetry is None or (isinstance(telemetry, str) or telemetry is True):
            telemetry_config, telemetry_interceptor = self.telemetry.get_telemetry_config(
                provider = telemetry,
                init_kwargs = telemetry_init_kwargs,
                config_kwargs = telemetry_config,
                init_interceptor = True,
            )
            if telemetry_config: kwargs['runtime'] = self.build_runtime(runtime = runtime, telemetry = telemetry_config)
            if telemetry_interceptor: interceptors.append(telemetry_interceptor)

        return await self.client_cls.connect(
            host,
            api_key = api_key,
            namespace = namespace,
            data_converter = converter,
            interceptors = interceptors,
            **kwargs,
        )

    
    def get_runtime_config(
        self, 
        config_file: t.Optional[str] = None,
        host: t.Optional[str] = None,
        name: t.Optional[str] = None,
        queue: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        identity: t.Optional[str] = None,
        activities: t.Optional[t.List[str]] = None,
        workflows: t.Optional[t.List[str]] = None,
        interceptors: t.Optional[t.List[str]] = None,
        converter: t.Optional[str] = None,
        telemetry: t.Optional[bool | str] = None,
        telemetry_config: t.Optional[t.Dict[str, t.Any]] = None,
        telemetry_init_kwargs: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs,
    ) -> 'RuntimeConfig':
        """
        Returns the Runtime Config
        """
        if config_file is not None: 
            logger.info(f'Loading Runtime Config from Config File: {config_file}')
            self._load_from_config_file_(config_file)
        if activities and workflows:
            _worker_config = dict(
                name = name or 'default-worker',
                queue = queue,
                identity = identity,
                namespace = namespace,
                activities = activities,
                workflows = workflows,
                **kwargs,
            )
            _worker_config = {k:v for k,v in _worker_config.items() if v is not None}
            new_worker = TemporalWorkerConfig(
                **_worker_config,
            )
            self.workers.append(new_worker)
            
        elif queue is not None: 
            for worker in self.workers:
                worker.queue = queue
        
        converter = self.get_data_converter(converter = converter) if converter else self.data_converter
        interceptors = interceptors or self.interceptors or []
        
        if telemetry is None or (isinstance(telemetry, str) or telemetry is True):
            telemetry_config, telemetry_interceptor = self.telemetry.get_telemetry_config(
                provider = telemetry,
                init_kwargs = telemetry_init_kwargs,
                config_kwargs = telemetry_config,
            )
            if telemetry_config: kwargs['telemetry'] = telemetry_config
            if telemetry_interceptor: interceptors.append(telemetry_interceptor)

        base_kwargs = dict(
            host = host or self.host,
            namespace = namespace or self.namespace,
            factory = self.default_factory,
            interceptors = interceptors,
            converter = converter,
            pre_init = self.pre_init,
            max_concurrent_activities = self.max_concurrent_activities,
            max_concurrent_workflow_tasks = self.max_concurrent_workflow_tasks,
            # metric_bind_address = self.metric_bind_address,
            workers = self.workers,
        )

        if kwargs: base_kwargs.update(kwargs)
        from lzl.ext.temporal.loop.config import RuntimeConfig
        return RuntimeConfig(**base_kwargs)

    class Config(BaseSettings.Config):
        env_prefix = "TEMPORAL_"



_tmprl_settings: t.Optional[TemporalSettings] = None
_tmprl_settings_cls: t.Optional[t.Type[TemporalSettings]] = TemporalSettings

def get_temporal_settings(**kwargs) -> TemporalSettings:
    """
    Returns the Temporal Settings
    """
    global _tmprl_settings
    if _tmprl_settings is None:
        _tmprl_settings = _tmprl_settings_cls(**kwargs)
    return _tmprl_settings

def set_temporal_settings_cls(cls: t.Type[TemporalSettings]):
    """
    Sets the Temporal Settings Class
    """
    global _tmprl_settings_cls
    _tmprl_settings_cls = cls
    
def set_temporal_settings(settings: TemporalSettings):
    """
    Sets the Temporal Settings
    """
    global _tmprl_settings
    # logger.info(f'Setting Temporal Settings: {settings}', prefix = 'Temporal', colored = True)
    _tmprl_settings = settings


config: TemporalSettings = ProxyObject(
    # obj_cls = TemporalSettings
    obj_getter = get_temporal_settings,
)