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
    FileMode,
    DEFAULT_ENCODING,
    ON_ERRORS,
    NEWLINE,
    IterableAIOFile,
)
from ..utils import logger, get_fsspec_file

if t.TYPE_CHECKING:
    from ..providers.main import R2Accessor
    from ..main import FileLike, PathLike


class FileR2PurePath(CloudFileSystemPurePath):
    _prefix: str = 'r2'
    _provider: str = 'CloudFlare'
    _win_pathz: t.ClassVar['PureFileR2WindowsPath'] = 'PureFileR2WindowsPath'
    _posix_pathz: t.ClassVar['PureFileR2PosixPath'] = 'PureFileR2PosixPath'


class PureFileR2PosixPath(PureCloudFileSystemPosixPath):
    """PurePath subclass for non-Windows systems.
    On a POSIX system, instantiating a PurePath should return this object.
    However, you can also instantiate it directly on any system.
    """
    _flavour = _pathz_posix_flavour
    _pathlike = posixpath
    __slots__ = ()


class PureFileR2WindowsPath(PureCloudFileSystemWindowsPath):
    """PurePath subclass for Windows systems.
    On a Windows system, instantiating a PurePath should return this object.
    However, you can also instantiate it directly on any system.
    """
    _flavour = _pathz_windows_flavour
    _pathlike = ntpath
    __slots__ = ()


_R2PathT = t.TypeVar('_R2PathT', bound = 'FileR2Path')

class FileR2Path(CloudFileSystemPath):
    """
    Our customized class that incorporates both sync and async methods
    """
    _flavour = _pathz_default_flavor
    _accessor: 'R2Accessor' = None
    _pathlike = posixpath
    _prefix = 'r2'
    _provider = 'CloudFlare'

    _win_pathz: t.ModuleType['FileR2WindowsPath'] = 'FileR2WindowsPath'
    _posix_pathz: t.ModuleType['FileR2PosixPath'] = 'FileR2PosixPath'

    def _init(self, template: t.Optional['FileR2Path'] = None):
        self._accessor = self._get_provider_accessor(self._prefix)
        self._closed = False
        self._fileio = None

    def __new__(cls, *parts, **kwargs):
        if cls is FileR2Path or issubclass(cls, FileR2Path): 
            cls = cls._posix_pathz if os.name != 'nt' else cls._win_pathz
            cls = globals()[cls]
        self = cls._from_parts(parts, init=False)
        if not self._flavour.is_supported:
            name: str = cls.__name__
            raise NotImplementedError(f"cannot instantiate {name} on your system")
        self._init()
        return self
    

    def aopen(self, mode: FileMode = 'r', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, block_size: int = 10 * 1024 * 1024, compression: str = None, **kwargs: t.Any) -> IterableAIOFile: 
        """
        Asyncronously Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        compression = infer doesn't work all that well.
        """
        return get_fsspec_file(
            self._accessor,
            self.fspath_,
            mode = mode,
            buffering = buffering,
            encoding = encoding,
            errors = errors,
            newline = newline,
            block_size = block_size,
            compression = compression,
            **kwargs,
        )

    def upload_file(self, dest: 'PathLike', filename: t.Optional[str] = None, overwrite: bool = True, **kwargs):
        """
        Upload a file to S3

        Utilize boto3
        """
        if not overwrite and dest.exists(): raise FileExistsError(f"{dest} already exists and overwrite is False")
        filename = filename or self.name
        self._accessor.boto.upload_file(
            Bucket = self.bucket_,
            Key = self.get_path_key(filename),
            Filename = dest.as_posix(),
        )
        return self.parent.joinpath(filename)
    
    def download_file(
        self, 
        output_file: t.Optional['PathLike'] = None,
        output_dir: t.Optional['PathLike'] = None,
        filename: t.Optional[str] = None,
        overwrite: bool = True,
        callbacks: t.Optional[t.List[t.Any]] = None,
        **kwargs
        ):
        """
        Downloads a file from S3 to a path
        """
        assert output_file or output_dir, "Must provide either output_file or output_dir"
        output_file = output_file or output_dir.joinpath(filename or self.name)
        assert overwrite or not output_file.exists(), f"{output_file} already exists and overwrite is False"
        s3t = self._accessor.s3t()
        s3t.download(
            self.bucket_,
            self.get_path_key(self.name),
            output_file.as_posix(),
            subscribers = callbacks
        )
        s3t.shutdown()
        return output_file

    async def async_upload_file(self, dest: 'PathLike', filename: t.Optional[str] = None,  overwrite: bool = True, **kwargs):
        """
        Upload a file to S3

        Utilize boto3
        """
        if not overwrite and await dest.aexists(): raise FileExistsError(f"{dest} already exists and overwrite is False")
        filename = filename or self.name
        s3t = self._accessor.s3t
        s3t.upload(
            dest.as_posix(),
            self.bucket_,
            self.get_path_key(filename)
        )
        s3t.shutdown()
        #await to_thread(
        #    self._accessor.boto.upload_file, Bucket = self._bucket, Key = self.get_path_key(filename), Filename = dest.as_posix()
        #)
        return self.parent.joinpath(filename)

    def batch_upload_files(
        self, 
        files: t.Optional[t.List['PathLike']] = None,
        glob_path: t.Optional[str] = None,
        overwrite: bool = False,
        skip_existing: bool = True,
        callbacks: t.Optional[t.List[t.Any]] = None,
        **kwargs
    ):
        """
        Handles batch uploading of files

        https://stackoverflow.com/questions/56639630/how-can-i-increase-my-aws-s3-upload-speed-when-using-boto3
        """
        assert files or glob_path, "Must provide either files or glob_path"
        if glob_path: files = list(self.glob(glob_path))
        results = []
        s3t = self._accessor.s3t()
        for file in files:
            if not overwrite and skip_existing and file.exists(): continue
            s3t.upload(
                file.as_posix(),
                self.bucket_,
                self.get_path_key(file.name),
                subscribers = callbacks
            )
            results.append(self.parent.joinpath(file.name))
        s3t.shutdown()
        return results
    
    def batch_download_files(
        self,
        glob_path: str,
        output_dir: 'PathLike',
        overwrite: bool = False,
        skip_existing: bool = True,
        callbacks: t.Optional[t.List[t.Any]] = None,
        **kwargs
    ):
        """
        Handles batch downloading of files
        """
        files = list(self.glob(glob_path))
        results = []
        s3t = self._accessor.s3t()
        for file in files:
            if not overwrite and skip_existing and file.exists(): continue
            output_file = output_dir.joinpath(file.name)
            s3t.download(
                self.bucket_,
                self.get_path_key(file.name),
                output_file.as_posix(),
                subscribers = callbacks
            )
            results.append(output_file)
        s3t.shutdown()
        return results


class FileR2PosixPath(PosixPath, FileR2Path, PureFileR2PosixPath):
    __slots__ = ()


class FileR2WindowsPath(WindowsPath, FileR2Path, PureFileR2WindowsPath):
    __slots__ = ()

    def is_mount(self) -> int:
        raise NotImplementedError("FileR2Path.is_mount() is unsupported on this system")

    async def async_is_mount(self) -> int:
        raise NotImplementedError("FileR2Path.async_is_mount() is unsupported on this system")


register_pathlike(
    [
        FileR2Path, 
        FileR2PurePath, 
        
        FileR2PosixPath, 
        PureFileR2PosixPath, 

        FileR2WindowsPath,
        PureFileR2WindowsPath
    ]
)

register_pydantictype(FileR2Path)