from __future__ import annotations

"""
Cached File System
"""

import os
import typing as t
from ..cloudfs import CloudFileSystemMeta, BaseFileSystemAccessor
from ...configs.main import FileIOConfig

if t.TYPE_CHECKING:
    from ...configs.main import ProviderConfig

class CachedFileSystem(metaclass = CloudFileSystemMeta):
    """
    Cached File System
    """
    
    @classmethod
    def build_cached(
        cls,
        protocol: str,
        **kwargs
    ):
        """
        Builds the Cached File System
        """
        import fsspec
        
        # protocol is like 'simplecache::s3'
        parts = protocol.split("::")
        cache_proto = parts[0]
        target_proto = parts[1] if len(parts) > 1 else None
        
        # Get target config
        target_kwargs = {}
        if target_proto:
            try:
                # Guess provider name
                provider = target_proto
                if provider == 's3': provider = 'aws'
                
                fs_config, _ = cls.settings.get_provider_config(provider)
                target_kwargs = fs_config
            except Exception:
                pass
        
        # Inject Env Vars for Cache Storage
        if cache_proto == 'simplecache':
            cache_storage = os.getenv('DATA_CACHE_DIR') or os.getenv('FILE_CACHE_DIR')
            if cache_storage:
                if 'cache_storage' not in kwargs:
                    kwargs['cache_storage'] = cache_storage

        # Build the filesystem
        # We must use the cache protocol (e.g. 'simplecache'), not the full 'simplecache::s3' string
        # and pass the target protocol/options explicitly.
        
        if target_proto:
            kwargs['target_protocol'] = target_proto
            kwargs['target_options'] = target_kwargs
        
        cls.fs = fsspec.filesystem(cache_proto, **kwargs)
        
        # Async
        from ..utils import rewrite_async_syntax
        cls.fsa = rewrite_async_syntax(fsspec.filesystem(cache_proto, asynchronous=True, **kwargs))
        
        # Config?
        cls.fsconfig = None 


class CachedAccessor(BaseFileSystemAccessor):
    """
    Cached File System Accessor
    """
    class CloudFileSystem(CachedFileSystem):
        pass
    
    @classmethod
    def reload_cfs(cls, protocol: str = None, **kwargs):
        """
        Reloads the Cloud File System
        """
        if protocol:
            cls.CloudFileSystem.build_cached(protocol, **kwargs)
        
        # Re-bind methods (same as BaseFileSystemAccessor.reload_cfs but pointing to new FS)
        super().reload_cfs()