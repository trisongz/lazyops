"""
The Core File Spec for Cloud Filesystems
"""
import os
from ..path import (
    pathlib,
    PosixPath, 
    WindowsPath, 
    Path, 
    PurePath,
    DEFAULT_ENCODING,
    ON_ERRORS,
    NEWLINE,
    BEGINNING,
    CHUNK_SIZE,
    SEP,
    ENCODING,
    ERRORS,
    FileData,
    FileMode,
    Paths,
    Handle,
)
import typing as t
from .path import (
    CloudFileSystemPath,
    CloudPathT
)
# from .compat
from ..types.base import FilePath, PureFilePosixPath, PureFileWindowsPath
from .paths.aws import (
    FileS3Path,
    FileS3PosixPath,
    FileS3WindowsPath,
    
)
from .paths.minio import (
    FileMinioPath,
    FileMinioPosixPath,
    FileMinioWindowsPath,
)
from .paths.s3c import (
    FileS3CPath,
    FileS3CPosixPath,
    FileS3CWindowsPath,
)
from .paths.r2 import (
    FileR2Path,
    FileR2PosixPath,
    FileR2WindowsPath,
)
from .paths.smb import (
    FileSMBPath,
    FileSMBPosixPath,
    FileSMBWindowsPath,
)
from .paths.cached import (
    FileCachedPath,
    FileCachedPosixPath,
    FileCachedWindowsPath,
)

PathLike = t.TypeVar(
    'PathLike', 
    bound = t.Union[
        str, 
        os.PathLike[str],
        Path,
        FilePath,
        FileS3Path,
        FileMinioPath,
        FileS3CPath,
        FileR2Path,
        FileSMBPath,
        FileCachedPath,
    ]
)

ProviderPathLike = t.TypeVar(
    'ProviderPathLike', 
    bound = t.Union[
        FileS3Path,
        FileMinioPath,
        FileS3CPath,
        FileR2Path,
        FileSMBPath,
        FileCachedPath,
    ]
)

FileLikeT = t.TypeVar(
    'FileLikeT', 
    bound = t.Union[
        Path,
        FilePath,
        FileS3Path,
        FileMinioPath,
        FileS3CPath,
        FileR2Path,
        FileSMBPath,
        FileCachedPath,
    ]
)

FileLike = t.Union[
    Path,
    FilePath,
    FileS3Path,
    FileMinioPath,
    FileS3CPath,
    FileSMBPath,
    FileCachedPath,
]

# FileLikeT = t.TypeVar(
#     'FileLikeT',
#     Path,
#     FilePath,
#     FileS3Path,
#     FileMinioPath,
# )


PREFIXES_TO_FP: t.Dict[str, t.Type[ProviderPathLike]] = {
    's3://': FileS3Path,
    'aws://': FileS3Path,

    'mc://': FileMinioPath,
    'mio://': FileMinioPath,
    'minio://': FileMinioPath,

    's3c://': FileS3CPath,
    's3compat://': FileS3CPath,

    'r2://': FileR2Path,
    'smb://': FileSMBPath,
}

_FILESPEC_CLS: t.Tuple[FileLikeT, ...] = (
    FilePath,
    PureFilePosixPath, 
    PureFileWindowsPath,

    FileS3Path,
    FileS3PosixPath,
    FileS3WindowsPath,

    FileMinioPath,
    FileMinioPosixPath,
    FileMinioWindowsPath,

    FileS3CPath,
    FileS3CPosixPath,
    FileS3CWindowsPath,

    FileR2Path,
    FileR2PosixPath,
    FileR2WindowsPath,

    FileSMBPath,
    FileSMBPosixPath,
    FileSMBWindowsPath,

    FileCachedPath,
    FileCachedPosixPath,
    FileCachedWindowsPath,
)


def as_path(path: PathLike) -> FileLike:
    """
    Given a path-like object, return a path-like object
    
    Create a generic `pathlib.Path`-like abstraction.
    Depending on the input (e.g. `gs://`, `github://`, `ResourcePath`,...), the
    system (Windows, Linux,...), the function will create the right pathlib-like
    abstraction.

    Args:
      path (PathLike): Pathlike object.
    
    Returns:
      A pathlib-like abstraction.
    """
    if isinstance(path, str):
        uri_splits = path.split('://', maxsplit=1)
        if len(uri_splits) > 1:    
            # str is URI (e.g. `gs://`, `github://`,...)
            protocol = uri_splits[0]
            if '::' in protocol:
                return FileCachedPath(path, protocol=protocol)
            return PREFIXES_TO_FP[f'{protocol}://'](path)
        return FilePath(path)
    elif isinstance(path, _FILESPEC_CLS):
        return path
    elif isinstance(path, os.PathLike):
        return FilePath(path)
    else: raise TypeError(f'Invalid path type: {path!r}')


def get_userhome(as_pathz: bool = True):
    h = os.path.expanduser('~')
    return as_path(h) if as_pathz else h

def get_cwd():
    return os.getcwd()


def resolve_relative(filepath: PathLike) -> str:
    """
    If the filepath is a relative path, convert it to an absolute path
    
    Args:
      filepath (PathLike): The path to the file you want to resolve.
    
    Returns:
      A string.
    """
    if not isinstance(filepath, str): filepath = filepath.as_posix()
    if '://' in filepath: return filepath
    if filepath.startswith('~'): filepath = filepath.replace('~', get_userhome(), 1)
    elif filepath.startswith('../'): filepath = filepath.replace('..', get_cwd(), 1)
    elif filepath.startswith('..'): filepath = filepath.replace('..', f'{pathlib.Path(get_cwd()).parent.parent.as_posix()}/', 1)
    elif filepath.startswith('./'): filepath = filepath.replace('.', get_cwd(), 1)
    elif filepath.startswith('.'): filepath = filepath.replace('.', f'{pathlib.Path(get_cwd()).parent.as_posix()}/', 1)
    return filepath


def get_pathlike(filepath: PathLike, resolve: bool = False) -> FileLike:
    if resolve: filepath = resolve_relative(filepath)
    if isinstance(filepath, str): filepath = as_path(filepath)
    return filepath


def get_filelike(path: PathLike) -> FileLike:
    """
    Transforms the path into a FileLike
    """
    if hasattr(path, 'is_fsspec'): return path
    if hasattr(path, 'as_posix'): return get_pathlike(path.as_posix())
    if isinstance(path, str): return get_pathlike(path)
    if hasattr(path, 'file') and hasattr(getattr(path, 'file'), 'name'): 
        return get_pathlike(path.file.name)
    return get_pathlike(path.name) if hasattr(path, 'name') else path
