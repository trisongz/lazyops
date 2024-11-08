from __future__ import annotations

"""
S3 Compatible Providers
"""

import typing as t
from ..cloudfs import CloudFileSystemMeta, BaseFileSystemAccessor

if t.TYPE_CHECKING:
    import s3fs
    import boto3
    import boto3.session
    from ..compat.r2 import R2FileSystem
    from s3transfer.manager import TransferManager
    from ...configs.providers import (
        AWSConfig,
        MinioConfig,
        S3CompatConfig,
        CloudflareR2Config,
    )


class AWSFileSystem(metaclass = CloudFileSystemMeta):
    fs: 's3fs.S3FileSystem' = None
    fsa: 's3fs.S3FileSystem' = None
    fsconfig: t.Optional['AWSConfig'] = None

    fs_name: str = 'aws'
    

class AWSAccessor(BaseFileSystemAccessor):
    """
    AWS File System Accessor
    """
    fsconfig: t.Optional['AWSConfig'] = None

    class CloudFileSystem(AWSFileSystem):
        pass


class MinioFileSystem(metaclass = CloudFileSystemMeta):
    fs: 's3fs.S3FileSystem' = None
    fsa: 's3fs.S3FileSystem' = None
    fsconfig: t.Optional['MinioConfig'] = None

    fs_name: str = 'minio'
    

class MinioAccessor(BaseFileSystemAccessor):
    """
    Minio File System Accessor
    """
    fsconfig: t.Optional['MinioConfig'] = None


    class CloudFileSystem(MinioFileSystem):
        pass


class S3CFileSystem(metaclass = CloudFileSystemMeta):
    fs: 's3fs.S3FileSystem' = None
    fsa: 's3fs.S3FileSystem' = None
    fsconfig: t.Optional['S3CompatConfig'] = None
    
    fs_name: str = 's3c'
    

class S3CAccessor(BaseFileSystemAccessor):
    """
    S3C File System Accessor
    """
    fsconfig: t.Optional['S3CompatConfig'] = None

    class CloudFileSystem(S3CFileSystem):
        pass

class R2FileSystem(metaclass = CloudFileSystemMeta):
    fs: 'R2FileSystem' = None
    fsa: 'R2FileSystem' = None
    fs_name: str = 'r2'
    config: t.Optional['CloudflareR2Config'] = None

class R2Accessor(BaseFileSystemAccessor):
    """
    R2 File System Accessor
    """
    fsconfig: t.Optional['CloudflareR2Config'] = None

    class CloudFileSystem(R2FileSystem):
        pass

