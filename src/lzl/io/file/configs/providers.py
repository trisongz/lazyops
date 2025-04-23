from __future__ import annotations


import os
import json
import pathlib
import multiprocessing as mp
from lzo.types import BaseSettings, eproperty, model_validator, field_validator, Literal

from typing import Optional, Dict, Any, List, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..spec.providers.main import ProviderFileSystemManager

class ConfigMixin(BaseSettings):
    """
    A Config Mixin
    """
    authz_config_dir: Optional[pathlib.Path] = None
    boto_config: Optional[pathlib.Path] = None
    max_workers: Optional[int] = None
    max_pool_connections: Optional[int] = 100

    write_chunking_enabled: Optional[bool] = False
    write_chunking_size: Optional[int] = 1024 * 1024 * 10 # 10 MB
    # if the object size is larger than this, it will use an alternate method
    write_chunking_large_size: Optional[int] = 1024 * 1024 * 50 # 50 MB 

    # Use the transfer manager by default (faster)
    write_chunking_manager_default: Optional[bool] = True 
    
    read_chunking_enabled: Optional[bool] = False
    read_chunking_size: Optional[int] = 1024 * 1024 * 10 # 10 MB
    # if the object size is larger than this, it will use an alternate method
    read_chunking_large_size: Optional[int] = 1024 * 1024 * 50 # 50 MB
    read_chunking_manager_default: Optional[bool] = True

    @field_validator("authz_config_dir", mode = 'before')
    def validate_authz_config_dir(cls, value: Optional[pathlib.Path]) -> pathlib.Path:
        """
        Validates the authz config dir
        """
        return pathlib.Path("~/.auth").expanduser() if value is None else value
    
    @eproperty
    def num_workers(self):
        """
        The number of workers
        """
        return self.max_workers or min(2, round(mp.cpu_count() // 2))

    @eproperty
    def boto_config_path(self) -> pathlib.Path:
        """
        Returns the boto config path
        """
        if self.boto_config is None:
            return pathlib.Path('/root/.boto') if self.in_colab else pathlib.Path("~/.boto").expanduser()
        return self.boto_config

    @eproperty
    def boto_config_exists(self):
        """
        Returns whether the boto config exists
        """
        return self.boto_config_path.exists()

    @eproperty
    def user_home(self) -> pathlib.Path:
        """
        Returns the user home directory
        """
        if self.in_colab:
            return pathlib.Path("/content")
        return pathlib.Path("~").expanduser()
    
    @eproperty
    def in_colab(self) -> bool:
        """
        Checks if the code is running in Google Colab
        """
        from lzl.require import LazyLib
        return LazyLib.is_available('google.colab')
    
    @eproperty
    def provider_fsm(self) -> 'ProviderFileSystemManager':
        """
        Returns the Provider File System Manager
        """
        from ..spec.providers.main import ProviderManager
        return ProviderManager
    
    def set_env(self):
        """
        Sets the environment variables for boto
        """
        if self.boto_config_exists:
            os.environ["BOTO_CONFIG"] = self.boto_config_path.as_posix()
            os.environ["BOTO_PATH"] = self.boto_config_path.as_posix()
    
    def update_config(self, **kwargs):
        """
        Updates the settings
        """
        for k, v in kwargs.items():
            if not hasattr(self, k):  continue
            if isinstance(getattr(self, k), pathlib.Path):
                setattr(self, k, pathlib.Path(v))
            else:
                setattr(self, k, v)

    def update_fs(self, **kwargs):
        """
        Updates the fs config
        """
        pass

    def update_auth(self, update_fs: bool = True, **config):
        """
        Updates the auth
        """
        self.update_config(**config)
        self.set_env()
        if update_fs: self.update_fs(**config)
    
    
    def build_fs_config(self) -> Dict[str, Any]:
        """
        Builds the fsspec config dict
        """
        return {}

    def get_boto_config(self) -> Dict[str, Any]:
        """
        Returns the boto config
        """
        raise NotImplementedError
    

    def get_boto_client_config(self) -> Dict[str, Any]:
        """
        Returns the boto client config
        """
        raise NotImplementedError
    
    class Config:
        case_sensitive = False
        extra = 'allow'

class AWSConfig(ConfigMixin):
    """
    The AWS Config
    """
    aws_access_token: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = "us-east-1"
    aws_s3_endpoint: Optional[str] = None
    set_s3_endpoint: Optional[bool] = False

    s3_use_accelerate_endpoint: Optional[bool] = False
    s3_config: Optional[Union[str, Dict[str, Any]]] = None
    s3_fs_config: Optional[Union[str, Dict[str, Any]]] = None

    @field_validator("s3_config", mode = 'before')
    def validate_s3_config(cls, value: Optional[Union[str, Dict[str, Any]]]) -> Union[str, Dict[str, Any]]:
        """
        Validates the S3 Config
        """
        if value is None: return {}
        if isinstance(value, str):
            value = json.loads(value)
        return value
    
    @field_validator('aws_s3_endpoint', mode='before')
    def validate_aws_s3_endpoint(cls, value: Optional[str]) -> str:
        """
        Validates the AWS S3 Endpoint
        """
        if value is None: return None
        if not value.startswith('http'):
            # Check if there's a port specified
            prefix = 'https'
            if ':' in value:
                # Likely a http endpoint
                if not value.endswith(':443'): 
                    prefix = 'http'
            value = f'{prefix}://{value}'
        return value
    
    @eproperty
    def s3_endpoint(self) -> str:
        """
        The S3 Endpoint
        """
        if self.aws_s3_endpoint: return self.aws_s3_endpoint
        return f'https://s3.{self.aws_region}.amazonaws.com'
    
    @eproperty
    def has_custom_endpoint(self) -> bool:
        """
        Returns whether the endpoint is custom
        """
        return self.aws_s3_endpoint is not None
    
    def set_env(self):
        """
        Sets the environment variables
        """
        super().set_env()
        if self.aws_access_key_id:
            os.environ['AWS_ACCESS_KEY_ID'] = self.aws_access_key_id
        if self.aws_secret_access_key:
            os.environ['AWS_SECRET_ACCESS_KEY'] = self.aws_secret_access_key
        if self.aws_region:
            os.environ['AWS_REGION'] = self.aws_region
        if self.aws_access_token:
            os.environ['AWS_ACCESS_TOKEN'] = self.aws_access_token
        if self.set_s3_endpoint:
            os.environ['S3_ENDPOINT'] = self.s3_endpoint

    def update_fs(self, **kwargs):
        """
        Updates the fs config
        """
        self.provider_fsm.get_accessor('aws', _reset = True)

    def build_fs_config(self) -> Dict[str, Any]:
        """
        Builds the s3fs config dict
        """
        config = {
            **(self.s3_fs_config or {})
        }
        if self.aws_access_key_id:
            config["key"] = self.aws_access_key_id
            # config['aws_access_key_id'] = self.aws_access_key_id
        if self.aws_secret_access_key:
            config["secret"] = self.aws_secret_access_key
            # config['aws_secret_access_key'] = self.aws_secret_access_key
        if self.aws_access_token:
            config["token"] = self.aws_access_token
        if not (config.get('key') and config.get('secret')) and not self.boto_config_exists:
            config['anon'] = True
        if self.set_s3_endpoint:
            config['client_kwargs'] = {'endpoint_url': self.s3_endpoint, 'region_name': self.aws_region}
        if self.s3_config:
            config['config_kwargs'] = self.s3_config
        return config

    def get_boto_config(self) -> Dict[str, Any]:
        """
        Returns the boto config
        """
        return {
            'region_name': self.aws_region,
            'max_pool_connections': self.max_pool_connections,
            's3': {
                'use_accelerate_endpoint': self.s3_use_accelerate_endpoint,
            }
        }
    
    def get_boto_client_config(self) -> Dict[str, Any]:
        """
        Returns the boto client config
        """
        base = {
            'aws_access_key_id': self.aws_access_key_id,
            'aws_secret_access_key': self.aws_secret_access_key,
        }
        if self.has_custom_endpoint:
            base['endpoint_url'] = self.s3_endpoint
            base['region_name'] = self.aws_region
        return base
        


class GCPConfig(ConfigMixin):
    """
    The GCP Config
    """

    gcp_project: Optional[str] = None
    gcloud_project: Optional[str] = None
    google_cloud_project: Optional[str] = None
    google_application_credentials: Optional[pathlib.Path] = None

    gcs_client_config: Optional[Union[str, Dict[str, Any]]] = None
    gcs_config: Optional[Union[str, Dict[str, Any]]] = None
    gcs_fs_config: Optional[Union[str, Dict[str, Any]]] = None


    @field_validator('gcs_config', 'gcs_client_config', mode='before')
    def validate_gcs_client_config(cls, value: Optional[Union[str, Dict[str, Any]]]) -> Union[str, Dict[str, Any]]:
        """
        Validates the GCS Client Config
        """
        if value is None: return {}
        if isinstance(value, str):
            value = json.loads(value)
        return value
    
    @model_validator(mode = 'after')
    def validate_gcp(self):
        """
        Validates the GCP Config
        """
        if not self.google_application_credentials:
            self.google_application_credentials = self.user_home.joinpath('adc.json')    
        return self
    
    @eproperty
    def adc_exists(self) -> bool:
        """
        Returns whether the ADC exists
        """
        return self.google_application_credentials.exists()
    
    
    @eproperty
    def project(self):
        return self.gcp_project or self.gcloud_project or self.google_cloud_project
    
    def set_env(self):
        """
        Sets the environment variables
        """
        if self.adc_exists:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.google_application_credentials.as_posix()
        if self.project:
            os.environ['GOOGLE_CLOUD_PROJECT'] = self.project
    

    def update_fs(self, **kwargs):
        """
        Updates the fs config
        """
        self.provider_fsm.get_accessor('gcs', _reset = True)


    def build_fs_config(self) -> Dict[str, Any]:
        """
        Builds the gcsfs config kwargs
        """
        config = {
            **(self.gcs_fs_config or {})
        }
        if self.adc_exists: config['token'] = self.google_application_credentials.as_posix()
        if self.project: config['project'] = self.project
        if self.gcs_client_config: config['client_config'] = self.gcs_client_config
        if self.gcs_config: config['config_kwargs'] = self.gcs_config
        return config


class MinioConfig(ConfigMixin):
    """
    The Minio Config
    """
    minio_endpoint: Optional[str] = None
    minio_access_key: Optional[str] = None
    minio_secret_key: Optional[str] = None
    minio_access_token: Optional[str] = None
    minio_secure: Optional[bool] = True
    minio_region: Optional[str] = 'us-east-1'
    minio_signature_ver: Optional[str] = 's3v4'
    minio_addressing_style: Optional[Literal['virtual', 'path', 'auto']] = 'auto'
    
    minio_config: Optional[Union[str, Dict[str, Any]]] = None
    minio_fs_config: Optional[Union[str, Dict[str, Any]]] = None

    write_chunking_enabled: Optional[bool] = True
    read_chunking_enabled: Optional[bool] = True
    write_chunking_manager_default: Optional[bool] = True
    read_chunking_manager_default: Optional[bool] = True
    

    @field_validator("minio_fs_config",'minio_config',  mode = 'before')
    def validate_minio_fs_config(cls, value: Optional[Union[str, Dict[str, Any]]]) -> Union[str, Dict[str, Any]]:
        """
        Validates the Minio FS Config
        """
        if value is None: return {}
        if isinstance(value, str):
            value = json.loads(value)
        return value
    

    def set_env(self):
        """
        Sets the environment variables
        """
        if self.minio_endpoint:
            os.environ["MINIO_ENDPOINT"] = self.minio_endpoint
        if self.minio_access_key:
            os.environ["MINIO_ACCESS_KEY"] = self.minio_access_key
        if self.minio_secret_key:
            os.environ["MINIO_SECRET_KEY"] = self.minio_secret_key
        if self.minio_secure:
            os.environ["MINIO_SECURE"] = str(self.minio_secure)
        if self.minio_region:
            os.environ["MINIO_REGION"] = self.minio_region
        if self.minio_signature_ver:
            os.environ["MINIO_SIGNATURE_VER"] = self.minio_signature_ver


    def build_fs_config(self) -> Dict[str, Any]:
        """
        Builds the s3fs config dict
        """
        config: Dict[str, Union[str, Dict[str, Any], Any]] = {
            "client_kwargs": {
                "endpoint_url": self.minio_endpoint,
                "region_name": self.minio_region,
            },
            "config_kwargs": {
                "signature_version": self.minio_signature_ver,
                "s3": {
                    "addressing_style": self.minio_addressing_style,
                }
            },
            **(self.minio_fs_config or {})
        }
        if self.minio_access_key:
            config["key"] = self.minio_access_key
        if self.minio_secret_key:
            config["secret"] = self.minio_secret_key
        if self.minio_access_token:
            config["token"] = self.minio_access_token
        if self.minio_config:
            config["config_kwargs"].update(self.minio_config)
        return config
    
    def update_fs(self, **kwargs):
        """
        Updates the fs config
        """
        self.provider_fsm.get_accessor('minio', _reset = True)


    def get_boto_config(self) -> Dict[str, Any]:
        """
        Returns the boto config
        """
        return {
            'signature_version': self.minio_signature_ver,
            'max_pool_connections': self.max_pool_connections,
            's3': {
                'addressing_style': self.minio_addressing_style,
            }
        }
    
    def get_boto_client_config(self) -> Dict[str, Any]:
        """
        Returns the boto client config
        """
        return {
            'aws_access_key_id': self.minio_access_key,
            'aws_secret_access_key': self.minio_secret_key,
            'region_name': self.minio_region,
            'endpoint_url': self.minio_endpoint,
            
        }
        
        

class S3CompatConfig(ConfigMixin):
    """
    The S3 Compat Config
    """

    s3c_endpoint: Optional[str] = None
    s3c_access_key: Optional[str] = None
    s3c_secret_key: Optional[str] = None
    s3c_access_token: Optional[str] = None
    s3c_secure: Optional[bool] = True
    s3c_region: Optional[str] = None
    s3c_addressing_style: Optional[Literal['virtual', 'path', 'auto']] = 'auto'
    s3c_signature_ver: Optional[str] = 's3v4'

    s3c_config: Optional[Union[str, Dict[str, Any]]] = None
    s3c_fs_config: Optional[Union[str, Dict[str, Any]]] = None

    @model_validator(mode = 'before')
    def map_depreciated_values(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps the depreciated values
        """
        fields = list(cls.model_fields.keys())
        for k in fields:
            dep_k = k.replace('s3c', 's3_compat', 1)
            if dep_k in values:
                val = values.pop(dep_k)
                if k not in values:
                    values[k] = val
        
        # Just handle the config stuff too
        if values.get('s3c_config'):
            if isinstance(values['s3c_config'], str):
                values['s3c_config'] = json.loads(values['s3c_config'])
        if values.get('s3c_fs_config'):
            if isinstance(values['s3c_fs_config'], str):
                values['s3c_fs_config'] = json.loads(values['s3c_fs_config'])
        return values
    
    def set_env(self):
        """
        Set environment variables for the S3C client.
        """
        # Handle the old env vars
        if self.s3c_endpoint:
            os.environ["S3_COMPAT_ENDPOINT"] = self.s3c_endpoint
            os.environ['S3C_ENDPOINT'] = self.s3c_endpoint
        if self.s3c_access_key:
            os.environ["S3_COMPAT_ACCESS_KEY"] = self.s3c_access_key
            os.environ['S3C_ACCESS_KEY'] = self.s3c_access_key
        if self.s3c_secret_key:
            os.environ["S3_COMPAT_SECRET_KEY"] = self.s3c_secret_key
            os.environ['S3C_SECRET_KEY'] = self.s3c_secret_key
        if self.s3c_access_token:
            os.environ["S3_COMPAT_ACCESS_TOKEN"] = self.s3c_access_token
            os.environ['S3C_ACCESS_TOKEN'] = self.s3c_access_token
        if self.s3c_secure:
            os.environ["S3_COMPAT_SECURE"] = str(self.s3c_secure)
            os.environ['S3C_SECURE'] = str(self.s3c_secure)
        if self.s3c_region:
            os.environ["S3_COMPAT_REGION"] = self.s3c_region
            os.environ['S3C_REGION'] = self.s3c_region
        if self.s3c_signature_ver:
            os.environ["S3_COMPAT_SIGNATURE_VER"] = self.s3c_signature_ver
            os.environ['S3C_SIGNATURE_VER'] = self.s3c_signature_ver
    
    def build_fs_config(self) -> Dict[str, Any]:
        """
        Builds the s3fs config dict
        """
        config: Dict[str, Union[str, Dict[str, Any], Any]] = {
            "client_kwargs": {
                "endpoint_url": self.s3c_endpoint,
                "region_name": self.s3c_region,
            },
            "config_kwargs": {
                "signature_version": self.s3c_signature_ver,
                "s3": {
                    "addressing_style": self.s3c_addressing_style,
                }
            },
            **(self.s3c_fs_config or {})
        }
        if self.s3c_access_key:
            config["key"] = self.s3c_access_key
        if self.s3c_secret_key:
            config["secret"] = self.s3c_secret_key
        if self.s3c_access_token:
            config["token"] = self.s3c_access_token
        if self.s3c_config:
            config["config_kwargs"].update(self.s3c_config)
        return config
    

    def update_fs(self, **kwargs):
        """
        Updates the fs config
        """
        self.provider_fsm.get_accessor('s3c', _reset = True)

    
    def get_boto_config(self) -> Dict[str, Any]:
        """
        Returns the boto config
        """
        return {
            'signature_version': self.s3c_signature_ver,
            'max_pool_connections': self.max_pool_connections,
            's3': {
                'addressing_style': self.s3c_addressing_style,
            }
        }
    
    def get_boto_client_config(self) -> Dict[str, Any]:
        """
        Returns the boto client config
        """
        return {
            'aws_access_key_id': self.s3c_access_key,
            'aws_secret_access_key': self.s3c_secret_key,
            'region_name': self.s3c_region,
            'endpoint_url': self.s3c_endpoint,
        }
        

class CloudflareR2Config(ConfigMixin):
    """
    The Cloudflare R2 Config
    """
    r2_account_id: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[str] = None
    r2_access_token: Optional[str] = None
    r2_region: Optional[str] = None

    r2_endpoint: Optional[str] = None
    r2_config: Optional[Union[str, Dict[str, Any]]] = None
    r2_fs_config: Optional[Union[str, Dict[str, Any]]] = None

    @model_validator(mode = 'before')
    def build_r2_values(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Builds the r2 values
        """
        if values.get("r2_config") is not None:
            values["r2_config"] = json.loads(values["r2_config"]) if isinstance(values["r2_config"], str) else values["r2_config"]
        if values.get("r2_fs_config") is not None:
            values["r2_fs_config"] = json.loads(values["r2_fs_config"]) if isinstance(values["r2_fs_config"], str) else values["r2_fs_config"]
        if values.get("r2_endpoint") is not None:
            values["r2_endpoint"] = values["r2_endpoint"].rstrip("/")
            if not values["r2_endpoint"].startswith("http"):
                values["r2_endpoint"] =  "https://" + values["r2_endpoint"]
        elif values.get("r2_account_id"):
            values["r2_endpoint"] = f"https://{values['r2_account_id']}.r2.cloudflarestorage.com"
        return values

    def set_env(self):
        """
        Sets the environment variables
        """
        if self.r2_endpoint:
            os.environ["R2_ENDPOINT"] = self.r2_endpoint
        if self.r2_account_id:
            os.environ["R2_ACCOUNT_ID"] = self.r2_account_id
        if self.r2_access_key_id:
            os.environ["R2_ACCESS_KEY_ID"] = self.r2_access_key_id
        if self.r2_secret_access_key:
            os.environ["R2_SECRET_ACCESS_KEY"] = self.r2_secret_access_key
        if self.r2_access_token:
            os.environ["R2_ACCESS_TOKEN"] = str(self.r2_access_token)
    
    def build_fs_config(self) -> Dict[str, Any]:
        """
        Builds the s3fs config dict
        """
        config: Dict[str, Union[str, Dict[str, Any], Any]] = {
            "client_kwargs": {
                "endpoint_url": self.r2_endpoint,
                "region_name": self.r2_region,
            },
            "config_kwargs": {},
            "fixed_upload_size": True,
            **(self.r2_fs_config or {})
        }
        if self.r2_access_key_id:
            config["key"] = self.r2_access_key_id
        if self.r2_secret_access_key:
            config["secret"] = self.r2_secret_access_key
        if self.r2_access_token:
            config["token"] = self.r2_access_token
        if self.r2_config:
            config["config_kwargs"].update(self.r2_config)
        return config


    def update_fs(self, **kwargs):
        """
        Updates the fs config
        """
        self.provider_fsm.get_accessor('r2', _reset = True)


    def get_boto_config(self) -> Dict[str, Any]:
        """
        Returns the boto config
        """
        return {
            'max_pool_connections': self.max_pool_connections,
        }
    
    def get_boto_client_config(self) -> Dict[str, Any]:
        """
        Returns the boto client config
        """
        return {
            'aws_access_key_id': self.r2_access_key_id,
            'aws_secret_access_key': self.r2_secret_access_key,
            'region_name': self.r2_region,
            'endpoint_url': self.r2_endpoint,
        }
        
