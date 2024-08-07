
"""
Common Cloud Provider Settings

pulled from `fileio.utils.configs`
"""
import os
import json
import pathlib

from typing import Optional, Union, Dict, Any
from lazyops.types.models import BaseSettings, validator
from lazyops.types.classprops import lazyproperty

from lazyops.imports._fileio import (
    File, 
    FileLike, 
    _fileio_available, 
    require_fileio,
)

# AWS
class BotoSettings(BaseSettings):
    boto_config: Optional[Union[str, pathlib.Path]] = None
    boto_path: Optional[Union[str, pathlib.Path]] = None

    @lazyproperty
    def path(self) -> FileLike:
        p = self.boto_config or self.boto_path
        if p is None: return None
        if _fileio_available: return File(p)
        if isinstance(p, str): 
            p = pathlib.Path(p)
        return p
    
    @lazyproperty
    def exists(self) -> bool:
        return False if self.path is None else self.path.exists()

    def set_env(self):
        """
        Update the Env variables for the current session
        """
        if self.exists:
            os.environ["BOTO_CONFIG"] = self.path.as_posix()
            os.environ["BOTO_PATH"] = self.path.as_posix()
    
class AwsSettings(BaseSettings):
    aws_access_token: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = "us-east-1"
    set_s3_endpoint: Optional[bool] = True
    s3_config: Optional[Union[str, Dict[str, Any]]] = None
    s3_bucket: Optional[str] = None
    s3_backup_bucket: Optional[str] = None

    @validator("s3_config", pre=True)
    def validate_s3_config(cls, v):
        if v is None: return {}
        return json.loads(v) if isinstance(v, str) else v
    
    @lazyproperty
    def s3_endpoint(self):
        return f'https://s3.{self.aws_region}.amazonaws.com'
    
    @lazyproperty
    @require_fileio()
    def s3_bucket_path(self):
        if self.s3_bucket is None: return None
        bucket = self.s3_bucket
        if not bucket.startswith('s3://'): bucket = f's3://{bucket}'
        return File(bucket)
    
    @lazyproperty
    @require_fileio()
    def s3_backup_bucket_path(self):
        if self.s3_backup_bucket is None: return None
        bucket = self.s3_backup_bucket
        if not bucket.startswith('s3://'): bucket = f's3://{bucket}'
        return File(bucket)
    
    def set_env(self):
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
    


# GCP

class GcpSettings(BaseSettings):
    gcp_project: Optional[str] = None
    gcloud_project: Optional[str] = None
    google_cloud_project: Optional[str] = None
    google_application_credentials: Optional[Union[str, pathlib.Path]] = None

    gcs_client_config: Optional[Union[str, Dict[str, Any]]] = None
    gcs_config: Optional[Union[str, Dict[str, Any]]] = None

    gs_bucket: Optional[str] = None
    gs_backup_bucket: Optional[str] = None

    @validator("google_application_credentials")
    def validate_google_application_credentials(cls, v):
        if v is None: return pathlib.Path.home().joinpath('adc.json')
        if _fileio_available: return File(v)
        if isinstance(v, str): v = pathlib.Path(v)
        return v
    
    @validator("gcs_client_config")
    def validate_gcs_client_config(cls, v) -> Dict:
        if v is None: return {}
        return json.loads(v) if isinstance(v, str) else v
    
    @validator("gcs_config")
    def validate_gcs_config(cls, v) -> Dict:
        if v is None: return {}
        return json.loads(v) if isinstance(v, str) else v

    @lazyproperty
    def adc_exists(self):
        return self.google_application_credentials.exists()
    
    @lazyproperty
    def project(self):
        return self.gcp_project or self.gcloud_project or self.google_cloud_project
    
    @lazyproperty
    @require_fileio()
    def gs_bucket_path(self):
        if self.gs_bucket is None: return None
        bucket = self.gs_bucket
        if not bucket.startswith('gs://'): bucket = f'gs://{bucket}'
        return File(bucket)
    
    @lazyproperty
    @require_fileio()
    def gs_backup_bucket_path(self):
        if self.gs_backup_bucket is None: return None
        bucket = self.gs_backup_bucket
        if not bucket.startswith('gs://'): bucket = f'gs://{bucket}'
        return File(bucket)
    
    def set_env(self):
        if self.adc_exists:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.google_application_credentials.as_posix()
        if self.project:
            os.environ["GOOGLE_CLOUD_PROJECT"] = self.project
    

# Minio

class MinioSettings(BaseSettings):
    minio_endpoint: Optional[str] = None
    minio_access_key: Optional[str] = None
    minio_secret_key: Optional[str] = None
    minio_access_token: Optional[str] = None
    minio_secure: Optional[bool] = True
    minio_region: Optional[str] = None
    minio_config: Optional[Union[str, Dict[str, Any]]] = None
    minio_signature_ver: Optional[str] = 's3v4'

    minio_bucket: Optional[str] = None
    minio_backup_bucket: Optional[str] = None

    @validator("minio_config", pre=True)
    def validate_minio_config(cls, v):
        if v is None: return {}
        return json.loads(v) if isinstance(v, str) else v
    
    @lazyproperty
    @require_fileio()
    def minio_bucket_path(self):
        if self.minio_bucket is None: return None
        bucket = self.minio_bucket
        if not bucket.startswith('minio://'): bucket = f'minio://{bucket}'
        return File(bucket)
    
    @lazyproperty
    @require_fileio()
    def minio_backup_bucket_path(self):
        if self.minio_backup_bucket is None: return None
        bucket = self.minio_backup_bucket
        if not bucket.startswith('minio://'): bucket = f'minio://{bucket}'
        return File(bucket)
    
    def set_env(self):
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








