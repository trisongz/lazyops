from __future__ import annotations

"""
TemporalIO Config
"""

import typing as t
from urllib.parse import urlparse
from lzo.types import BaseSettings, model_validator, Field
from lzl.types import eproperty
from lzl.proxied import ProxyObject
from .utils import logger

if t.TYPE_CHECKING:
    from lzl.io.persistence import TemporaryData
    from temporalio.converter import DataConverter
    from .registry import TemporalRegistry

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
    lazy: t.Optional[bool] = Field(None, description = "If true, the client will not connect until the first call is attempted. If false, the client will connect immediately.")
    default_task_queue: t.Optional[str] = Field(None, description = "The default task queue to use for this client.")

    converter: t.Optional[str] = Field("serialized", description = "The converter to use for the client")
    data_jsonlib: t.Optional[str] = Field(None, description = "The JSON library to use for data conversion")
    data_compression: t.Optional[str] = Field(None, description = "The compression to use for data conversion")
    data_compression_level: t.Optional[int] = Field(None, description = "The compression level to use for data conversion")

    @model_validator(mode = 'after')
    def validate_settings(self):
        """
        Validates the settings
        """
        if self.url is not None:
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
        return self

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
    
    @eproperty
    def data_converter(self) -> 'DataConverter':
        """
        Returns the data converter
        """
        from lzl.ext.temporal.io import get_default_data_converter
        return get_default_data_converter(
            converter = self.converter,
            jsonlib = self.data_jsonlib,
            compression = self.data_compression,
            compression_level = self.data_compression_level,
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

    class Config(BaseSettings.Config):
        env_prefix = "TEMPORAL_"

_tmprl_settings: t.Optional[TemporalSettings] = None

def get_temporal_settings(**kwargs) -> TemporalSettings:
    """
    Returns the Temporal Settings
    """
    global _tmprl_settings
    if _tmprl_settings is None:    
        _tmprl_settings = TemporalSettings(**kwargs)
    return _tmprl_settings


config: TemporalSettings = ProxyObject(
    # obj_cls = TemporalSettings
    obj_getter = get_temporal_settings,
)