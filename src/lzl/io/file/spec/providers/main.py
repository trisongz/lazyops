from __future__ import annotations

"""
The File Providers
"""
import abc
import typing as t
from lzl.proxied import ProxyObject
from .s3 import (
    AWSFileSystem,
    AWSAccessor,
    MinioFileSystem,
    MinioAccessor,
    S3CFileSystem,
    S3CAccessor,
    R2FileSystem,
    R2Accessor,
)

AccessorLike = t.Union[
    AWSAccessor,
    MinioAccessor,
    S3CAccessor,
    R2Accessor,
]

FileSystemLike = t.Union[
    AWSFileSystem,
    MinioFileSystem,
    S3CFileSystem,
    R2FileSystem,
]

ProviderMapping: t.Dict[str, t.Tuple[t.Type[FileSystemLike], t.Type[AccessorLike]]] = {
    "s3": (AWSFileSystem, AWSAccessor),
    "minio": (MinioFileSystem, MinioAccessor),
    "s3c": (S3CFileSystem, S3CAccessor),
    "r2": (R2FileSystem, R2Accessor),
}

_ProviderAliases = {
    'aws': 's3',
    'mc': 'minio',
    'mio': 'minio',
    's3fs': 's3',
}

class ProviderFileSystemManager(abc.ABC):
    """
    The File System Manager
    """
    def __init__(self, **kwargs):
        self.accessors: t.Dict[str, AccessorLike] = {}
    
    def get_accessor(self, name: str, _reset: t.Optional[bool] = False, **kwargs) -> AccessorLike:
        """
        Gets the accessor
        """
        if name in _ProviderAliases: name = _ProviderAliases[name]
        if not self.accessors.get(name) or _reset:
            if name not in ProviderMapping:
                raise ValueError(f"Invalid Provider: {name}")
            _fs, _accessor = ProviderMapping[name]
            _fs.build_filesystems()
            _accessor.reload_cfs(**kwargs)
            self.accessors[name] = _accessor
        return self.accessors[name]
    
    def get_filesystem(self, name: str, _reset: t.Optional[bool] = False, **kwargs) -> FileSystemLike:
        """
        Gets the filesystem
        """
        if name in _ProviderAliases: name = _ProviderAliases[name]
        if name not in ProviderMapping:
            raise ValueError(f"Invalid Provider: {name}")
        _fs, _ = ProviderMapping[name]
        if _reset: _fs.build_filesystems(**kwargs)
        return _fs


ProviderManager: ProviderFileSystemManager = ProxyObject(ProviderFileSystemManager)