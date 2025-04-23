from __future__ import annotations

import os
import json
import pathlib
import typing as t
from lzl.logging import logger
from lzl.proxied import ProxyObject
from lzo.utils import load_env_vars
from lzo.types import (
    BaseSettings, eproperty, model_validator, field_validator, PrivateAttr
)
from lzo.registry.mixins import RegisteredSettings
from .providers import (
    ConfigMixin,
    AWSConfig,
    GCPConfig,
    MinioConfig,
    S3CompatConfig,
    CloudflareR2Config,
    ProviderConfig,
)
from typing import Optional, Dict, Any, List, Union, Tuple, TYPE_CHECKING

# Maps Provider Class to its Default Scheme and Base Env Prefix
_DEFAULT_PROVIDER_MAP: t.Dict[t.Type[ProviderConfig], t.Tuple[str, str]] = {
    AWSConfig: ('s3', 'AWS_'),
    GCPConfig: ('gs', 'GCP_'),
    MinioConfig: ('mc', 'MINIO_'),
    S3CompatConfig: ('s3c', 'S3C_'),
    CloudflareR2Config: ('r2', 'R2_'),
}

# Maps Provider Class Name (lowercase) to its Class
_PROVIDER_CLASSES: t.Dict[str, t.Type[ProviderConfig]] = {
    cls.__name__.lower().replace('config', ''): cls for cls in _DEFAULT_PROVIDER_MAP
}

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

    # Define ENV Prefix Mappings (e.g., "AWS_PROD:s3prod,AWS_DEV:s3dev")
    aws_env_prefixes: Optional[str] = None
    gcp_env_prefixes: Optional[str] = None
    minio_env_prefixes: Optional[str] = None
    s3c_env_prefixes: Optional[str] = None
    r2_env_prefixes: Optional[str] = None

    # Internal storage for provider configurations keyed by URI scheme
    _provider_configs: Dict[str, ProviderConfig] = PrivateAttr(default_factory=dict)

    class Config:
        env_prefix = "FILEIO_"
        case_sensitive = False

    @model_validator(mode='after')
    def load_all_provider_configs(self) -> 'FileIOConfig':
        """
        Loads default and environment-defined provider configurations.
        """
        loaded_schemes = set()

        for provider_cls, (default_scheme, base_prefix) in _DEFAULT_PROVIDER_MAP.items():
            provider_name = provider_cls.__name__.lower().replace('config', '')
            env_prefixes_var = f"{provider_name}_env_prefixes"
            
            # 1. Load Default Config
            try:
                default_config = provider_cls(
                    _env_prefix = base_prefix,
                    _uri_scheme = default_scheme,
                    **load_env_vars(base_prefix)
                )
                default_config.set_env() # Set env vars for this instance
                self._provider_configs[default_scheme] = default_config
                loaded_schemes.add(default_scheme)
                logger.debug(f"Loaded default {provider_name} config for scheme '{default_scheme}'")
            except Exception as e:
                logger.warning(f"Failed to load default {provider_name} config: {e}", exc_info=True)

            # 2. Load Additional Configs from ENV_PREFIXES
            env_prefixes_str = getattr(self, env_prefixes_var, None)
            if env_prefixes_str:
                prefixes = [item.strip() for item in env_prefixes_str.split(',')]
                for prefix_map in prefixes:
                    if ':' not in prefix_map:
                        logger.warning(f"Invalid format in {env_prefixes_var}: '{prefix_map}'. Expected 'PREFIX:scheme'. Skipping.")
                        continue
                    
                    env_prefix, uri_scheme = prefix_map.split(':', 1)
                    env_prefix = env_prefix.strip().rstrip('_') + '_' # Ensure trailing underscore
                    uri_scheme = uri_scheme.strip()

                    if uri_scheme in loaded_schemes:
                        logger.warning(f"Scheme '{uri_scheme}' defined in {env_prefixes_var} conflicts with an already loaded scheme. Skipping.")
                        continue

                    try:
                        config = provider_cls(
                            _env_prefix = env_prefix,
                            _uri_scheme = uri_scheme,
                            **load_env_vars(env_prefix)
                        )
                        config.set_env() # Set env vars for this instance
                        self._provider_configs[uri_scheme] = config
                        loaded_schemes.add(uri_scheme)
                        logger.info(f"Loaded additional {provider_name} config for scheme '{uri_scheme}' using prefix '{env_prefix}'")
                    except Exception as e:
                        logger.warning(f"Failed to load {provider_name} config for scheme '{uri_scheme}' with prefix '{env_prefix}': {e}", exc_info=True)
        
        return self

    def get_provider_config_by_scheme(self, scheme: str) -> Optional[ProviderConfig]:
        """
        Retrieves the provider configuration for a given URI scheme.
        """
        return self._provider_configs.get(scheme)

    def create_adc(
        self, 
        data: Union[str, Dict[str, Any]], 
        path: str = None,
        scheme: str = 'gs' # Default to the primary GCP scheme
    ):
        """
        Create a new ADC based on the passed data and writes it to 
        path or GOOGLE_APPLICATION_CREDENTIALS for the specified scheme config.
        """
        gcp_config = self.get_provider_config_by_scheme(scheme)
        if not isinstance(gcp_config, GCPConfig):
            logger.error(f"No GCP configuration found for scheme '{scheme}' to create ADC.")
            return

        if isinstance(data, str): data = json.loads(data)
        target_path: pathlib.Path = pathlib.Path(path) if path else gcp_config.google_application_credentials
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(data, indent = 2, ensure_ascii=False))
        gcp_config.google_application_credentials = target_path
        # Optionally, re-set environment for this specific instance if needed immediately
        gcp_config.set_env() 


    def get_boto_values(self, scheme: str = 's3') -> Optional[str]:
        """
        Returns the boto config values for the specified AWS/S3-like scheme.
        Defaults to the primary 's3' scheme.
        """
        aws_config = self.get_provider_config_by_scheme(scheme)
        gcp_config = self.get_provider_config_by_scheme('gs') # Assume default 'gs' for GSUtil part

        if not isinstance(aws_config, (AWSConfig, MinioConfig, S3CompatConfig, CloudflareR2Config)):
             logger.warning(f"Cannot generate boto content: No AWS/S3-like config found for scheme '{scheme}'.")
             return None

        t = "[Credentials]\n"
        # Use attributes specific to AWS-like configs
        aws_key_id = getattr(aws_config, 'aws_access_key_id', getattr(aws_config, 'minio_access_key', getattr(aws_config, 's3c_access_key', getattr(aws_config, 'r2_access_key_id', None))))
        aws_secret = getattr(aws_config, 'aws_secret_access_key', getattr(aws_config, 'minio_secret_key', getattr(aws_config, 's3c_secret_key', getattr(aws_config, 'r2_secret_access_key', None))))
        
        if aws_key_id:
            t += f"aws_access_key_id = {aws_key_id}\n"
        if aws_secret:
            t += f"aws_secret_access_key = {aws_secret}\n"
        
        if isinstance(gcp_config, GCPConfig) and gcp_config.google_application_credentials.exists():
            t += f"gs_service_key_file = {gcp_config.google_application_credentials.as_posix()}\n"
        
        t += "\n[Boto]\n"
        t += "https_validate_certificates = True\n"
        t += "\n[GSUtil]\n"
        t += "content_language = en\n"
        t += "default_api_version = 2\n"
        if isinstance(gcp_config, GCPConfig) and gcp_config.project: 
            t += f"default_project_id = {gcp_config.project}\n"
        return t
    

    def write_botofile(
        self, 
        overwrite: bool = False, 
        scheme: str = 's3', # Default to primary AWS scheme
        **kwargs
    ):
        """
        Writes the boto config file using settings from the specified scheme's config.
        Uses the boto_config_path defined within that specific config instance.
        """
        config = self.get_provider_config_by_scheme(scheme)
        if not config:
            logger.error(f"Cannot write boto file: No config found for scheme '{scheme}'.")
            return

        boto_path = config.boto_config_path
        if not boto_path:
             logger.warning(f"No 'boto_config_path' defined for scheme '{scheme}' config. Cannot write boto file.")
             return

        boto_values = self.get_boto_values(scheme=scheme)
        if not boto_values:
            logger.error(f"Could not generate boto content for scheme '{scheme}'.")
            return

        if not config.boto_config_exists or overwrite:
            logger.info(f"Writing boto config for scheme '{scheme}' to {boto_path.as_posix()}")
            boto_path.parent.mkdir(parents=True, exist_ok=True)
            boto_path.write_text(boto_values)
            # Optionally update env var if this config expects it
            config.set_env() 
    

    def update_config(self, **kwargs):
        """
        Update the main config and/or specific provider configs by scheme.
        Top-level keys update FileIOConfig.
        Keys matching provider schemes update that provider's config.
        e.g., update_config(num_workers=8, s3={'aws_region': 'us-west-2'})
        """
        provider_updates = {}
        main_updates = {}

        for k, v in kwargs.items():
            if k in self._provider_configs:
                provider_updates[k] = v
            elif hasattr(self, k):
                main_updates[k] = v
            else:
                logger.warning(f"Key '{k}' not found in FileIOConfig or loaded provider schemes. Skipping update.")

        # Update main config first
        for k, v in main_updates.items():
             if isinstance(getattr(self, k, None), pathlib.Path):
                 setattr(self, k, pathlib.Path(v))
             else:
                 setattr(self, k, v)

        # Update provider configs
        for scheme, updates in provider_updates.items():
            config = self._provider_configs.get(scheme)
            if config and isinstance(updates, dict):
                try:
                    config.update_config(**updates)
                    logger.info(f"Updated configuration for provider scheme '{scheme}'.")
                except Exception as e:
                    logger.error(f"Failed to update config for scheme '{scheme}': {e}", exc_info=True)
            elif not config:
                 logger.warning(f"Attempted to update non-existent provider config for scheme '{scheme}'.")
            elif not isinstance(updates, dict):
                 logger.warning(f"Update value for scheme '{scheme}' is not a dictionary. Skipping.")


    def set_env(self):
        """
        Set environment variables for ALL loaded provider configurations.
        """
        logger.debug(f"Setting environment variables for {len(self._provider_configs)} provider configurations.")
        for scheme, config in self._provider_configs.items():
            try:
                config.set_env()
                logger.debug(f"Set environment variables for scheme '{scheme}'.")
            except Exception as e:
                logger.error(f"Failed to set environment for scheme '{scheme}': {e}", exc_info=True)

    
    # Renamed from get_provider_config
    def get_fsspec_config_by_scheme(self, scheme: str, **auth_override) -> Optional[Tuple[Dict[str, Any], ProviderConfig]]:
        """
        Retrieves the fsspec config dictionary and the provider config object
        for the specified scheme. Allows overriding auth settings temporarily.
        """
        provider_spec = self.get_provider_config_by_scheme(scheme)
        if not provider_spec: 
            logger.error(f"Provider config for scheme '{scheme}' not found.")
            return None
        
        # If auth overrides are provided, create a temporary copy to avoid modifying the original
        if auth_override:
            temp_spec = provider_spec.model_copy(deep=True)
            try:
                temp_spec.update_auth(**auth_override)
                return temp_spec.build_fs_config(), temp_spec
            except Exception as e:
                 logger.error(f"Failed to apply auth override for scheme '{scheme}': {e}", exc_info=True)
                 # Fallback to original if override fails? Or return None? Returning original for now.
                 return provider_spec.build_fs_config(), provider_spec
        else:
            return provider_spec.build_fs_config(), provider_spec
