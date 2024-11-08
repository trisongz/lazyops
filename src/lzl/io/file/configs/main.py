from __future__ import annotations

import json
import pathlib
from lzl.logging import logger
from lzl.proxied import ProxyObject
from lzo.utils import load_env_vars
from lzo.types import BaseSettings, eproperty, model_validator, field_validator
from lzo.registry.mixins import RegisteredSettings
from .providers import (
    ConfigMixin,
    AWSConfig,
    GCPConfig,
    MinioConfig,
    S3CompatConfig,
    CloudflareR2Config,
)
from typing import Optional, Dict, Any, List, Union, Tuple, TYPE_CHECKING

ProviderConfig = Union[AWSConfig, GCPConfig, MinioConfig, S3CompatConfig, CloudflareR2Config]

class FileIOConfig(BaseSettings, RegisteredSettings.configure_registered(module = 'file')):
    """
    FileIOConfig
    """

    read_chunk_size: Optional[int] = 1024 * 64 # 64KB
    url_chunk_size: Optional[int] = 1024 * 128 # 128KB
    max_pool_connections: Optional[int] = 100
    
    num_workers: Optional[int] = 12
    checksum_cache_ttl: Optional[int] = 60 * 60 * 24 * 1 # 1 days
    enable_progress_bar: Optional[bool] = False
    tfio_enabled: Optional[bool] = False

    class Config:
        env_prefix = "FILEIO_"
        case_sensitive = False

    @eproperty
    def aws(self) -> AWSConfig:
        """
        Returns the AWS Config
        """
        return AWSConfig()
    
    @eproperty
    def gcp(self) -> GCPConfig:
        """
        Returns the GCP Config
        """
        return GCPConfig()
    
    @eproperty
    def minio(self) -> MinioConfig:
        """
        Returns the Minio Config
        """
        return MinioConfig()
    
    @eproperty
    def s3c(self) -> S3CompatConfig:
        """
        Returns the S3Compat Config
        """
        return S3CompatConfig()
    
    @eproperty
    def r2(self) -> CloudflareR2Config:
        """
        Returns the Cloudflare R2 Config
        """
        return CloudflareR2Config()
    

    def create_adc(
        self, 
        data: Union[str, Dict[str, Any]], 
        path: str = None
    ):
        """
        Create a new ADC based on the passed data and writes it to 
        path or GOOGLE_APPLICATION_CREDENTIALS
        """
        if isinstance(data, str): data = json.loads(data)
        path: pathlib.Path = pathlib.Path(path) if path else self.gcp.google_application_credentials
        path.write_text(json.dumps(data, indent = 2, ensure_ascii=False))
        self.gcp.google_application_credentials = path


    def get_boto_values(self):
        """
        Returns the boto config values
        """
        t = "[Credentials]\n"
        if self.aws.aws_access_key_id:
            t += f"aws_access_key_id = {self.aws.aws_access_key_id}\n"
        if self.aws.aws_secret_access_key:
            t += f"aws_secret_access_key = {self.aws.aws_secret_access_key}\n"
        if self.gcp.google_application_credentials.exists():
            t += f"gs_service_key_file = {self.gcp.google_application_credentials.as_posix()}\n"
        t += "\n[Boto]\n"
        t += "https_validate_certificates = True\n"
        t += "\n[GSUtil]\n"
        t += "content_language = en\n"
        t += "default_api_version = 2\n"
        if self.gcp.project: t += f"default_project_id = {self.gcp.project}\n"
        return t
    

    def write_botofile(
        self, 
        overwrite: bool = False, 
        **kwargs
    ):
        """
        Writes the boto config file to the path specified in the boto_config_path
        """
        if not self.aws.boto_config_exists or overwrite:
            logger.info(f"Writing boto config to {self.aws.boto_config_path.as_posix()}")
            self.aws.boto_config_path.write_text(self.get_boto_values())
    

    def update_config(self, **kwargs):
        """
        Update the config with the passed kwargs
        """
        for k, v in kwargs.items():
            if not hasattr(self, k): continue
            value = getattr(self, k)
            if isinstance(value, ConfigMixin):
                value.update_config(**v)
                continue
            if isinstance(value, pathlib.Path):
                value = pathlib.Path(v)
            setattr(self, k, value)

    def set_env(self):
        """
        Set the environment variables
        """
        self.aws.set_env()
        self.gcp.set_env()
        self.minio.set_env()
        self.s3c.set_env()
        self.r2.set_env()

    
    def update_auth(self, update_fs: bool = True, **config):
        """
        Updates the auth settings and optionally updates the fs
        """
        self.update_config(**config)
        self.set_env()


    def get_provider_config(self, provider: str, update_fs: bool = False, **auth_config) -> Tuple[Dict[str, Any], ProviderConfig]:
        """
        Updates the auth settings for the specified provider
        and returns the provider config
        """
        if not hasattr(self, provider): 
            raise ValueError(f"Provider {provider} not found")
        provider_spec: ConfigMixin = getattr(self, provider)
        if auth_config: provider_spec.update_auth(update_fs = update_fs, **auth_config)
        return provider_spec.build_fs_config(), provider_spec
