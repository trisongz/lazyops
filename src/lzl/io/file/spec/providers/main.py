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
from .cached import (
    CachedFileSystem,
    CachedAccessor,
)

AccessorLike = t.Union[
    AWSAccessor,
    MinioAccessor,
    S3CAccessor,
    R2Accessor,
    CachedAccessor,
]

FileSystemLike = t.Union[
    AWSFileSystem,
    MinioFileSystem,
    S3CFileSystem,
    R2FileSystem,
    CachedFileSystem,
]

ProviderMapping: t.Dict[str, t.Tuple[t.Type[FileSystemLike], t.Type[AccessorLike]]] = {
    "s3": (AWSFileSystem, AWSAccessor),
    "minio": (MinioFileSystem, MinioAccessor),
    "s3c": (S3CFileSystem, S3CAccessor),
    "r2": (R2FileSystem, R2Accessor),
    "smb": (CachedFileSystem, CachedAccessor), # Placeholder
}

# Config type to (FS, Accessor) mapping
_ConfigToProvider: t.Dict[str, t.Tuple[t.Type[FileSystemLike], t.Type[AccessorLike]]] = {
    'AWSConfig': (AWSFileSystem, AWSAccessor),
    'MinioConfig': (MinioFileSystem, MinioAccessor),
    'S3CompatConfig': (S3CFileSystem, S3CAccessor),
    'CloudflareR2Config': (R2FileSystem, R2Accessor),
    'SMBConfig': (CachedFileSystem, CachedAccessor), # Placeholder
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
        if "::" in name:
            # Handle Cached/Chained Protocol
            if not self.accessors.get(name) or _reset:
                # Create dynamic classes to isolate state (fs instances) per protocol string
                class DynamicCachedFileSystem(CachedFileSystem):
                    pass
                
                class DynamicCachedAccessor(CachedAccessor):
                    class CloudFileSystem(DynamicCachedFileSystem):
                        pass
                
                DynamicCachedFileSystem.build_cached(name, **kwargs)
                DynamicCachedAccessor.reload_cfs()
                self.accessors[name] = DynamicCachedAccessor
            return self.accessors[name]

        if name in _ProviderAliases: name = _ProviderAliases[name]
        
        # Check if we have the accessor
        if self.accessors.get(name) and not _reset:
            return self.accessors[name]

        # Standard Providers
        if name in ProviderMapping:
            _fs, _accessor = ProviderMapping[name]
        
        else:
            # Check Custom Providers
            from ...utils.registry import fileio_settings
            if name in fileio_settings._custom_providers:
                config = fileio_settings._custom_providers[name]
                config_type = config.__class__.__name__
                if config_type not in _ConfigToProvider:
                    raise ValueError(f"Unsupported Config Type for Dynamic Provider: {config_type}")
                
                base_fs, base_accessor = _ConfigToProvider[config_type]
                
                # Create Dynamic Classes
                # We need to construct the class name carefully
                # e.g. MinioFileSystem -> Mc2FileSystem
                
                _fs_name = name.title().replace('_', '')
                _fs = type(f"{_fs_name}FileSystem", (base_fs,), {
                    'fs_name': name,
                    'fsconfig': config,
                    'fs': None,
                    'fsa': None,
                    # '_settings': fileio_settings # Should inherit
                })
                
                _accessor = type(f"{_fs_name}Accessor", (base_accessor,), {
                    'fsconfig': config,
                    'CloudFileSystem': _fs,
                })
                
                # We need to register this provider with supported providers in cloudfs
                # This is handled dynamically in build_filesystems if we patch it or if we update the list
                from .. import cloudfs
                if name not in cloudfs._SupportedProviders:
                    cloudfs._SupportedProviders.append(name)
                    # Also need to map alias if it's treating it as a provider type
                    # But here the 'fs_name' matches 'name', so we just need to know 
                    # what "kind" it is for build_s3c/etc.
                    
                    # Inspecting cloudfs.py:
                    # if self.fs_name in _SupportedProviders:
                    #     provider = _MappedProviderAliases.get(self.fs_name, self.fs_name)
                    #     return self.build_s3c(provider = provider, ... )
                    
                    # So if fs_name is "mc2", provider becomes "mc2".
                    # build_s3c(provider="mc2") uses get_provider_config("mc2").
                    # This should work if FileIOConfig.get_provider_config handles "mc2".
                    pass

            else:
                 raise ValueError(f"Invalid Provider: {name}")

        _fs.build_filesystems()
        _accessor.reload_cfs(**kwargs)
        self.accessors[name] = _accessor
        return self.accessors[name]
    
    def get_filesystem(self, name: str, _reset: t.Optional[bool] = False, **kwargs) -> FileSystemLike:
        """
        Gets the filesystem
        """
        if "::" in name:
            return self.get_accessor(name, _reset=_reset, **kwargs).filesys

        if name in _ProviderAliases: name = _ProviderAliases[name]
        if name not in ProviderMapping:
            raise ValueError(f"Invalid Provider: {name}")
        _fs, _ = ProviderMapping[name]
        if _reset: _fs.build_filesystems(**kwargs)
        return _fs


ProviderManager: ProviderFileSystemManager = ProxyObject(ProviderFileSystemManager)