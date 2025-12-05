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
    from ..providers.main import SMBAccessor
    from ..main import FileLike, PathLike


class FileSMBPurePath(CloudFileSystemPurePath):
    _prefix: str = 'smb'
    _provider: str = 'SMB'
    _win_pathz: t.ClassVar['PureFileSMBWindowsPath'] = 'PureFileSMBWindowsPath'
    _posix_pathz: t.ClassVar['PureFileSMBPosixPath'] = 'PureFileSMBPosixPath'


class PureFileSMBPosixPath(PureCloudFileSystemPosixPath):
    """PurePath subclass for non-Windows systems.
    On a POSIX system, instantiating a PurePath should return this object.
    However, you can also instantiate it directly on any system.
    """
    _flavour = _pathz_posix_flavour
    _pathlike = posixpath
    __slots__ = ()


class PureFileSMBWindowsPath(PureCloudFileSystemWindowsPath):
    """PurePath subclass for Windows systems.
    On a Windows system, instantiating a PurePath should return this object.
    However, you can also instantiate it directly on any system.
    """
    _flavour = _pathz_windows_flavour
    _pathlike = ntpath
    __slots__ = ()



class FileSMBPath(CloudFileSystemPath):
    """
    Our customized class that incorporates both sync and async methods for SMB
    """
    _flavour = _pathz_default_flavor
    _accessor: 'SMBAccessor' = None
    _pathlike = posixpath
    _prefix = 'smb'
    _provider = 'SMB'

    _win_pathz: t.ModuleType['FileSMBWindowsPath'] = 'FileSMBWindowsPath'
    _posix_pathz: t.ModuleType['FileSMBPosixPath'] = 'FileSMBPosixPath'

    def _init(self, template: t.Optional['FileSMBPath'] = None):
        self._accessor = self._get_provider_accessor(self._prefix)
        self._closed = False
        self._fileio = None
        self._extra: t.Dict[str, t.Any] = {}

    def __new__(cls, *parts, **kwargs):
        if cls is FileSMBPath or issubclass(cls, FileSMBPath): 
            cls = cls._posix_pathz if os.name != 'nt' else cls._win_pathz
            cls = globals()[cls]
        self = cls._from_parts(parts, init=False)
        if not self._flavour.is_supported:
            name: str = cls.__name__
            raise NotImplementedError(f"cannot instantiate {name} on your system")
        self._init()
        return self
    
    @property
    def fss3tm(self):
        """
        S3 Transfer Manager is not supported for SMB
        """
        raise NotImplementedError('S3 Transfer Manager is not Supported for SMB File System')


class FileSMBPosixPath(PosixPath, FileSMBPath, PureFileSMBPosixPath):
    __slots__ = ()


class FileSMBWindowsPath(WindowsPath, FileSMBPath, PureFileSMBWindowsPath):
    __slots__ = ()

    def is_mount(self) -> int:
        raise NotImplementedError("FileSMBPath.is_mount() is unsupported on this system")

    async def async_is_mount(self) -> int:
        raise NotImplementedError("FileSMBPath.async_is_mount() is unsupported on this system")


register_pathlike(
    [
        FileSMBPath, 
        FileSMBPurePath, 
        
        FileSMBPosixPath, 
        PureFileSMBPosixPath, 

        FileSMBWindowsPath,
        PureFileSMBWindowsPath
    ]
)

register_pydantictype(FileSMBPath)