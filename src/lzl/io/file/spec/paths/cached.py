from __future__ import annotations

import os
import ntpath
import posixpath
import typing as t
from ..path import (
    CloudFileSystemPath,
    CloudFileSystemPurePath,
    PureCloudFileSystemPosixPath,
    PureCloudFileSystemWindowsPath,
    _pathz_default_flavor,
    _pathz_posix_flavour,
    _pathz_windows_flavour,
    PosixPath, 
    WindowsPath,
    register_pathlike,
    register_pydantictype,
    CloudPathT,
)

if t.TYPE_CHECKING:
    from ..providers.cached import CachedAccessor
    from ..main import FileLike, PathLike


class FileCachedPurePath(CloudFileSystemPurePath):
    # _prefix will be set dynamically or via subclassing?
    # PurePath uses _prefix to parse parts.
    # But for chained protocols, prefix is complex.
    pass

class PureFileCachedPosixPath(PureCloudFileSystemPosixPath):
    _flavour = _pathz_posix_flavour
    _pathlike = posixpath
    __slots__ = ()

class PureFileCachedWindowsPath(PureCloudFileSystemWindowsPath):
    _flavour = _pathz_windows_flavour
    _pathlike = ntpath
    __slots__ = ()


class FileCachedPath(CloudFileSystemPath):
    """
    Class for Cached/Chained Filesystems (e.g. simplecache::s3://)
    """
    _flavour = _pathz_default_flavor
    _accessor: 'CachedAccessor' = None
    _pathlike = posixpath
    # _prefix is strictly used for splitting?
    
    _win_pathz: t.ModuleType['FileCachedWindowsPath'] = 'FileCachedWindowsPath'
    _posix_pathz: t.ModuleType['FileCachedPosixPath'] = 'FileCachedPosixPath'

    def _init(self, template: t.Optional['FileCachedPath'] = None):
        # Parse the full protocol from string?
        # Path initialization: Path("simplecache::s3://bucket/key")
        # parts will be ['simplecache::s3:', 'bucket', 'key'] on Posix?
        # fsspec chained protocol looks like 'simplecache::s3://bucket/key'.
        # pathlib might split it differently.
        
        # self._prefix needs to be 'simplecache::s3' etc.
        # But we don't know it statically.
        
        # If initialized via as_path, we can inject it?
        # Or we rely on parsing the first part.
        
        # For now, assume as_path calls this with correct parts.
        # We need to extract the full protocol string to get the accessor.
        pass 
        # self._accessor is set below because we override __new__ or _init?
        # CloudFileSystemPath._init calls self._get_provider_accessor(self._prefix).
        
        # Problem: self._prefix is None on the class.
        # We need to detect it from parts?
        
        parts = self._parts
        # Example parts: ['simplecache::s3:', 'bucket', 'key'] (if root is empty)
        # or ['simplecache::s3://bucket/key']
        
        # We need to find the protocol separator.
        # as_path splits by ://
        # if path is "simplecache::s3://bucket/key"
        # uri_splits[0] = "simplecache::s3"
        # So prefix is "simplecache::s3".
        
        # We need to set self._prefix on the instance before calling super()._init?
        # PurePath doesn't store prefix on instance usually, checks class.
        # But CloudFileSystemPath uses self._prefix.
        
        if not self._prefix:
            # Try to infer?
            # This is tricky with pathlib inheritance.
            pass
    
    def _init_accessor(self):
        # Custom init to get accessor based on actual protocol
        # We assume the first part of the path contains the protocol info if it was parsed that way?
        # No, parts are path components.
        
        # If we use File("simplecache::s3://..."), as_path creates FileCachedPath.
        # But FileCachedPath needs to know the protocol.
        # We can store it on the instance.
        pass

    @classmethod
    def _get_provider_accessor(cls, prefix: str) -> 'CachedAccessor':
        from ..providers.main import ProviderManager
        return ProviderManager.get_accessor(prefix)

    def __new__(cls, *parts, **kwargs):
        # Handle protocol extraction
        # If passed a string with ::, extract protocol
        protocol = kwargs.pop('protocol', None)
        
        if cls is FileCachedPath or issubclass(cls, FileCachedPath): 
            cls = cls._posix_pathz if os.name != 'nt' else cls._win_pathz
            cls = globals()[cls]
        
        self = cls._from_parts(parts, init=False)
        
        if not self._flavour.is_supported:
            raise NotImplementedError(f"cannot instantiate {cls.__name__} on your system")
        
        # Determine protocol if not set
        if not protocol:
            # Try to find it in parts[0] ?
            # If created via as_path("simplecache::s3://..."), 
            # The drive/root logic might be confused.
            
            # Let's assume user passes `protocol` arg if invoking directly,
            # or we patch as_path to set it.
            pass
            
        self._protocol = protocol
        self._init()
        return self

    def _init(self, template: t.Optional['FileCachedPath'] = None):
        if template:
            self._protocol = getattr(template, '_protocol', None)
            self._accessor = template._accessor
        else:
            if self._protocol:
                self._accessor = self._get_provider_accessor(self._protocol)
                self._prefix = self._protocol # Set prefix for other methods
            else:
                # Fallback or error?
                pass
        
        self._closed = False
        self._fileio = None
        self._extra: t.Dict[str, t.Any] = {}
        
    @property
    def fss3tm(self):
        raise NotImplementedError('S3 Transfer Manager is not Supported for Cached File System')


class FileCachedPosixPath(PosixPath, FileCachedPath, PureFileCachedPosixPath):
    __slots__ = ()

class FileCachedWindowsPath(WindowsPath, FileCachedPath, PureFileCachedWindowsPath):
    __slots__ = ()
    def is_mount(self) -> int:
        raise NotImplementedError("FileCachedPath.is_mount() is unsupported on this system")
    async def async_is_mount(self) -> int:
        raise NotImplementedError("FileCachedPath.async_is_mount() is unsupported on this system")

register_pathlike(
    [
        FileCachedPath,
        FileCachedPurePath,
        FileCachedPosixPath,
        PureFileCachedPosixPath,
        FileCachedWindowsPath,
        PureFileCachedWindowsPath
    ]
)
