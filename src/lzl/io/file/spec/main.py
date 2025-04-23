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
    ]
)

ProviderPathLike = t.TypeVar(
    'ProviderPathLike', 
    bound = t.Union[
        FileS3Path,
        FileMinioPath,
        FileS3CPath,
        FileR2Path,
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
    ]
)

FileLike = t.Union[
    Path,
    FilePath,
    FileS3Path,
    FileMinioPath,
    FileS3CPath,
]

# FileLikeT = t.TypeVar(
#     'FileLikeT',
#     Path,
#     FilePath,
#     FileS3Path,
#     FileMinioPath,
# )

# --- Path Type Resolution ---

# Base mapping of known schemes/aliases to their primary implementation class
# This will be dynamically extended by configurations found in FileIOConfig
SCHEME_TO_PATH_CLASS: t.Dict[str, t.Type[FileLikeT]] = {
    's3': FileS3Path,
    'aws': FileS3Path,
    # 'gs': FileGCSPath, # Assuming FileGCSPath exists or needs creation
    # 'gcs': FileGCSPath,
    'mc': FileMinioPath,
    'mio': FileMinioPath,
    'minio': FileMinioPath,
    's3c': FileS3CPath,
    's3compat': FileS3CPath,
    'r2': FileR2Path,
    'file': FilePath, # Explicitly map 'file' scheme to local FilePath
}

# Function to populate the map dynamically (call this once, e.g., upon import or first use)
_SCHEME_MAP_POPULATED = False
def populate_scheme_map():
    global _SCHEME_MAP_POPULATED, SCHEME_TO_PATH_CLASS
    if _SCHEME_MAP_POPULATED: return
    
    try:
        from ..utils import fileio_settings, logger # Use the central settings getter
        from ..configs.providers import (
             AWSConfig, GCPConfig, MinioConfig, S3CompatConfig, CloudflareR2Config
        )
        config = fileio_settings
        if config._provider_configs: # Check if configs are loaded
            logger.debug(f"Dynamically populating SCHEME_TO_PATH_CLASS from {len(config._provider_configs)} loaded provider configs.")
            for scheme, provider_config in config._provider_configs.items():
                if scheme not in SCHEME_TO_PATH_CLASS:
                    # Map the scheme to the *class* associated with the provider type
                    path_cls = None
                    if isinstance(provider_config, MinioConfig):
                        path_cls = FileMinioPath
                    elif isinstance(provider_config, AWSConfig):
                        path_cls = FileS3Path
                    elif isinstance(provider_config, S3CompatConfig):
                         path_cls = FileS3CPath
                    elif isinstance(provider_config, CloudflareR2Config):
                         path_cls = FileR2Path
                    # Add elif for GCPConfig -> FileGCSPath when available
                    # elif isinstance(provider_config, GCPConfig):
                    #     path_cls = FileGCSPath 
                    
                    if path_cls:
                        SCHEME_TO_PATH_CLASS[scheme] = path_cls
                        logger.debug(f"Mapped scheme '{scheme}' -> {path_cls.__name__}")
                    else:
                         logger.warning(f"No corresponding Path class found for scheme '{scheme}' with config type {type(provider_config).__name__}. Skipping dynamic mapping.")
        _SCHEME_MAP_POPULATED = True
    except Exception as e:
        logger.error(f"Failed to dynamically populate SCHEME_TO_PATH_CLASS: {e}", exc_info=True)
        # Proceed without dynamic population? Or raise? For now, log error.

# Ensure the map is populated when the module is loaded or first used.
# Calling it here might be too early if settings aren't loaded yet.
# It might be better called within as_path or get_filelike ensure settings exist.
# populate_scheme_map()


# Original prefix map (keep for reference or potential fallback? -> Remove)
# PREFIXES_TO_FP: t.Dict[str, t.Type[ProviderPathLike]] = { ... }

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
    # Add FileGCSPath etc. when available
)


def as_path(path: PathLike) -> FileLike:
    """
    Given a path-like object, return the appropriate FileLike object based on its scheme.
    
    Create a generic `pathlib.Path`-like abstraction.
    Depending on the input (e.g., `gs://`, `mc1://`, `s3://`, local path), the
    system (Windows, Linux,...), the function will create the right pathlib-like
    abstraction.

    Args:
      path (PathLike): Pathlike object (string, os.PathLike, existing FileLike).
    
    Returns:
      A FileLike object (e.g., FilePath, FileS3Path, FileMinioPath).
    """
    # Ensure the scheme map is populated before proceeding
    populate_scheme_map()

    if isinstance(path, _FILESPEC_CLS):
        # Already a known FileLike type, return directly
        return path
    
    path_str = None
    if isinstance(path, str):
        path_str = path
    elif hasattr(path, 'as_posix'): # Handle pathlib.Path or similar
        path_str = path.as_posix()
    elif isinstance(path, os.PathLike):
         path_str = os.fspath(path)
    # Add handling for other potential input types if needed, like file objects?
    # Previous get_filelike had: if hasattr(path, 'file') ... -> get_pathlike(path.file.name)
    # Previous get_filelike had: if hasattr(path, 'name') ... -> get_pathlike(path.name)

    if path_str is not None:
        scheme = None
        if '://' in path_str:
            scheme = path_str.split('://', 1)[0].lower() # Use lowercase scheme
        
        # Check the scheme map
        PathClass = SCHEME_TO_PATH_CLASS.get(scheme)
        
        if PathClass:
            # Found a specific class for the scheme
            return PathClass(path_str)
        else:
            # Default to local FilePath if scheme is None, 'file', or unknown
            if scheme is not None and scheme != 'file':
                 from ..utils import logger
                 logger.warning(f"Unknown scheme '{scheme}' in path '{path_str}'. Treating as local path.")
            return FilePath(path_str)
            
    # If input wasn't a string, PathLike, or known FileLike, raise error
    raise TypeError(f'Invalid input type for as_path: {type(path)}')

# Remove old get_filelike helper functions
# def get_userhome(as_pathz: bool = True): ...
# def get_cwd(): ...
# def resolve_relative(filepath: PathLike) -> str: ...
# def get_pathlike(filepath: PathLike, resolve: bool = False) -> FileLike: ...

def get_filelike(path: PathLike) -> FileLike:
    """
    Transforms various path-like inputs into a FileLike object (e.g., FilePath, FileS3Path).

    This function attempts to intelligently handle strings (including URIs),
    os.PathLike objects, and existing FileLike objects.
    
    Args:
        path: The input path representation.
    
    Returns:
        A FileLike object.
    
    Raises:
        TypeError: If the input path cannot be converted.
    """
    # Optimization: If it already has 'is_fsspec', assume it's a compatible cloud path object.
    # Note: This assumes our dynamically created path objects will have this.
    # We might need to add `is_fsspec = True` to the cloud path base class.
    if hasattr(path, 'is_fsspec'): 
        return path 

    # Handle common cases directly before falling back to string conversion in as_path
    if isinstance(path, _FILESPEC_CLS):
        return path
    if isinstance(path, (str, os.PathLike)): # Let as_path handle strings and os.PathLike
        return as_path(path)
    
    # Attempt to extract path from common object attributes (like file handles)
    extracted_path = None
    if hasattr(path, 'file') and hasattr(getattr(path, 'file', None), 'name'): 
        extracted_path = getattr(path.file, 'name', None)
        from ..utils import logger
        logger.debug(f"Extracted path '{extracted_path}' from object attribute path.file.name")
    elif hasattr(path, 'name') and isinstance(getattr(path, 'name', None), str): 
        extracted_path = path.name
        from ..utils import logger
        logger.debug(f"Extracted path '{extracted_path}' from object attribute path.name")

    if extracted_path is not None:
         return as_path(extracted_path)

    # If we couldn't handle it, raise an error
    raise TypeError(f'Unable to convert input type {type(path)} to a FileLike object.')
