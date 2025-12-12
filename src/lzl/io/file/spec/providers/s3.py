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
    from ..compat.r2.filesys import R2FileSystem
    from s3transfer.manager import TransferManager
    from ...configs.providers import (
        AWSConfig,
        MinioConfig,
        S3CompatConfig,
        CloudflareR2Config,
    )


def _patch_s3_mkdir(cls):
    _orig_mkdir = cls.mkdir
    _orig_amkdir = cls.amkdir
    
    def _get_bucket(path: str) -> str:
        # returns the first part of the path
        return path.split('/', 1)[0]
    
    def mkdir(path: str, create_parents: bool = True, exist_ok: bool = True, **kwargs):
        try:
            return _orig_mkdir(path, create_parents=create_parents, exist_ok=exist_ok, **kwargs)
        except (OSError, Exception) as e:
            # s3fs raises OSError or others
            msg = str(e)
            if "NoSuchBucket" in msg or "The specified location-constraint is not valid" in msg or "Bucket does not exist" in msg:
                bucket = _get_bucket(path)
                created = False
                try: 
                    # Attempt to create bucket using s3fs
                    # s3fs.mkdir(bucket) creates the bucket.
                    cls.CloudFileSystem.fs.mkdir(bucket)
                    created = True
                except Exception: 
                    pass
                
                if not created and cls.CloudFileSystem.boto:
                    # Fallback to boto
                    try:
                        # We might need LocationConstraint
                        config = cls.CloudFileSystem.fsconfig
                        params = {'Bucket': bucket}
                        region = getattr(config, 'region', None) if config else None
                        
                        if region and region != 'us-east-1':
                            params['CreateBucketConfiguration'] = {'LocationConstraint': region}
                        
                        cls.CloudFileSystem.boto.create_bucket(**params)
                        created = True
                    except Exception:
                        pass
                
                # Retry original operation
                return _orig_mkdir(path, create_parents=create_parents, exist_ok=exist_ok, **kwargs)
            raise

    async def amkdir(path: str, create_parents: bool = True, exist_ok: bool = True, **kwargs):
        try:
            return await _orig_amkdir(path, create_parents=create_parents, exist_ok=exist_ok, **kwargs)
        except (OSError, Exception) as e:
            msg = str(e)
            if "NoSuchBucket" in msg or "The specified location-constraint is not valid" in msg or "Bucket does not exist" in msg:
                bucket = _get_bucket(path)
                try: 
                    # Try to create bucket using aiobotocore client directly
                    fsa = cls.CloudFileSystem.fsa
                    
                    if hasattr(fsa, 's3') and fsa.s3:
                         s3_client = fsa.s3
                         if s3_client is not None:
                            config = cls.CloudFileSystem.fsconfig
                            params = {'Bucket': bucket}
                            region = getattr(config, 'region', None) if config else None

                            if region and region != 'us-east-1':
                                params['CreateBucketConfiguration'] = {'LocationConstraint': region}
                            
                            await s3_client.create_bucket(**params)

                    elif hasattr(fsa, '_mkdir'):
                        # Fallback to internal mkdir if s3 client not exposed (unlikely)
                        await fsa._mkdir(bucket)
                    
                except Exception: 
                    pass
                # Retry
                return await _orig_amkdir(path, create_parents=create_parents, exist_ok=exist_ok, **kwargs)
            raise

    cls.mkdir = mkdir
    cls.amkdir = amkdir

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

    @classmethod
    def reload_cfs(cls, **kwargs):
        super().reload_cfs(**kwargs)
        _patch_s3_mkdir(cls)


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

    @classmethod
    def reload_cfs(cls, **kwargs):
        super().reload_cfs(**kwargs)
        _patch_s3_mkdir(cls)


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

    @classmethod
    def reload_cfs(cls, **kwargs):
        super().reload_cfs(**kwargs)
        _patch_s3_mkdir(cls)

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
    
    # R2 usually needs explicit bucket creation too? 
    # But sticking to S3 ones for now.
    # If R2 uses s3fs-like, it might also benefit.
    # Leaving standard.


