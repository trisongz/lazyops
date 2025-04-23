from __future__ import annotations

""""
Cloud Filesystem Abstraction Layer
"""

import os
import atexit
import functools
import typing as t
from urllib.parse import urlparse
from lzl.require import LazyLib
from lzl.logging import logger
from ..path import NormalAccessor # Keep inheriting for local file methods
# from ..utils.logs import logger # Already imported from lzl.logging
from .utils import rewrite_async_syntax # Keep this specific utility

if t.TYPE_CHECKING:
    from ..configs.main import FileIOConfig, ProviderConfig
    from fsspec.spec import AbstractFileSystem
    from fsspec.asyn import AsyncFileSystem
    from s3transfer.manager import TransferManager
    from boto3.session import Session
    from ..types import FileLikePath

    _FST = t.TypeVar('_FST', bound=AbstractFileSystem)
    _ASFST = t.TypeVar('_ASFST', bound=AsyncFileSystem)

# --- Filesystem Instance Management ---

class FilesystemBundle(t.NamedTuple):
    """Holds related filesystem objects for a specific scheme."""
    scheme: str
    fs: t.Optional[_FST] = None
    fsa: t.Optional[_ASFST] = None
    boto: t.Optional[Session] = None
    _s3t_creator: t.Optional[t.Callable[..., TransferManager]] = None
    s3t: t.Optional[TransferManager] = None
    config: t.Optional[ProviderConfig] = None


class CloudFileManager:
    """Manages cloud filesystem instances keyed by URI scheme."""
    _instances: t.Dict[str, FilesystemBundle] = {}
    _settings: t.Optional['FileIOConfig'] = None
    _creating: t.Set[str] = set() # To prevent recursive creation loops

    @property
    def settings(self) -> 'FileIOConfig':
        """Lazily retrieves the global FileIOConfig."""
        if self._settings is None:
            from ..utils import get_settings # Use the central settings getter
            self._settings = get_settings()
        return self._settings

    def get_bundle(self, scheme: str, create: bool = True) -> t.Optional[FilesystemBundle]:
        """Gets the FilesystemBundle for a scheme, optionally creating it."""
        if scheme not in self._instances and create:
            if scheme in self._creating:
                logger.warning(f"Recursive creation detected for scheme: {scheme}")
                return None
            self._creating.add(scheme)
            try:
                self._create_bundle(scheme)
            finally:
                 self._creating.remove(scheme)

        bundle = self._instances.get(scheme)
        # Lazy S3T creation logic added back
        if bundle and bundle._s3t_creator and not bundle.s3t:
            # Lazily create S3 Transfer Manager
            try:
                logger.debug(f"Lazily creating S3 Transfer Manager for scheme: {scheme}")
                s3t = bundle._s3t_creator()
                # Update the bundle in the dictionary
                self._instances[scheme] = bundle._replace(s3t=s3t, _s3t_creator=None) # Clear creator after creation
                atexit.register(self._atexit_s3t, scheme) # Register specific shutdown
                logger.debug(f"Registered S3 Transfer Manager shutdown for scheme: {scheme}")
                return self._instances[scheme] # Return updated bundle
            except Exception as e:
                 logger.error(f"Failed to create S3 Transfer Manager for scheme {scheme}: {e}", exc_info=True)
                 # Return bundle without s3t if creation fails
                 return bundle
        return bundle

    def _create_bundle(self, scheme: str):
        """Creates and stores the filesystem instances for a given scheme."""
        logger.info(f"Attempting to create filesystem bundle for scheme: {scheme}")
        config_tuple = self.settings.get_fsspec_config_by_scheme(scheme)
        if not config_tuple:
            # Don't raise error, just log and return, get_bundle handles None
            logger.warning(f"Configuration for scheme '{scheme}' not found. Cannot create bundle.")
            self._instances[scheme] = None # Mark as checked but not found
            return

        fsspec_config, provider_config = config_tuple
        provider_name = provider_config.__class__.__name__.lower().replace('config', '') # e.g., 'aws'

        fs = None
        fsa = None
        boto_client = None
        s3t_creator = None

        try:
            # --- Filesystem Creation Logic ---
            if provider_name in ['aws', 'minio', 's3c', 'r2']:
                LazyLib.import_lib('s3fs', require_missing=True)
                import s3fs
                fs_cls = s3fs.S3FileSystem
                if provider_name == 'r2':
                    # Attempt to import R2 compatibility layer if needed
                    try:
                        from .compat.r2 import R2FileSystem
                        fs_cls = R2FileSystem
                        logger.debug(f"Using R2FileSystem for scheme: {scheme}")
                    except ImportError:
                         logger.warning("R2FileSystem not found in .compat.r2, falling back to s3fs.S3FileSystem for R2.")
                
                fs = fs_cls(asynchronous=False, **fsspec_config)
                fsa = rewrite_async_syntax(fs_cls(asynchronous=True, **fsspec_config))
                logger.debug(f"Created s3fs instances for scheme: {scheme}")

                # --- Boto3 Client and S3 Transfer Manager ---
                if hasattr(provider_config, 'get_boto_config') and hasattr(provider_config, 'get_boto_client_config'):
                    LazyLib.import_lib('boto3', require_missing=True)
                    LazyLib.import_lib('botocore.config', require_missing=True)
                    import boto3
                    import boto3.s3.transfer as s3transfer
                    from botocore.config import Config as BotoConfig

                    try:
                        boto_conf = BotoConfig(**provider_config.get_boto_config())
                        boto_client = boto3.client(
                            's3', config=boto_conf, **provider_config.get_boto_client_config()
                        )
                        logger.debug(f"Created boto3 client for scheme: {scheme}")
                        transfer_conf = s3transfer.TransferConfig(
                             use_threads = True, # Make this configurable?
                             max_concurrency = self.settings.max_pool_connections # Use global setting
                        )
                        # Store the creator function for lazy instantiation
                        s3t_creator = functools.partial(
                            s3transfer.create_transfer_manager, boto_client, transfer_conf
                        )
                        logger.debug(f"Prepared S3 Transfer Manager creator for scheme: {scheme}")
                    except Exception as e:
                         logger.error(f"Failed during boto3/s3t setup for scheme {scheme}: {e}", exc_info=True)
                         boto_client = None # Ensure partial setup doesn't persist
                         s3t_creator = None

            elif provider_name == 'gcp':
                LazyLib.import_lib('gcsfs', require_missing=True)
                import gcsfs
                fs = gcsfs.GCSFileSystem(asynchronous=False, **fsspec_config)
                fsa = rewrite_async_syntax(gcsfs.GCSFileSystem(asynchronous=True, **fsspec_config))
                logger.debug(f"Created gcsfs instances for scheme: {scheme}")
            
            # Add other providers (Azure, etc.) here if needed

            else:
                logger.error(f"Unsupported provider type '{provider_name}' for scheme '{scheme}'.")
                self._instances[scheme] = None # Mark as checked but not supported
                return

            # Store the created bundle
            self._instances[scheme] = FilesystemBundle(
                scheme=scheme, fs=fs, fsa=fsa, boto=boto_client, _s3t_creator=s3t_creator, config=provider_config
            )
            logger.info(f"Successfully created filesystem bundle for scheme: {scheme}")

        except Exception as e:
             logger.error(f"Failed to create filesystem bundle for scheme '{scheme}': {e}", exc_info=True)
             self._instances[scheme] = None # Mark as failed

    def get_fs(self, scheme: str) -> t.Optional[_FST]:
        """Gets the synchronous filesystem instance for the scheme."""
        bundle = self.get_bundle(scheme)
        return bundle.fs if bundle else None

    def get_fsa(self, scheme: str) -> t.Optional[_ASFST]:
        """Gets the asynchronous filesystem instance for the scheme."""
        bundle = self.get_bundle(scheme)
        return bundle.fsa if bundle else None

    def get_s3t(self, scheme: str) -> t.Optional[TransferManager]:
        """Gets the S3 Transfer Manager for the scheme (if applicable and created)."""
        bundle = self.get_bundle(scheme) # Ensures lazy creation if needed
        return bundle.s3t if bundle else None
    
    def get_config(self, scheme: str) -> t.Optional[ProviderConfig]:
        """Gets the ProviderConfig for the scheme."""
        bundle = self.get_bundle(scheme)
        return bundle.config if bundle else None

    def _atexit_s3t(self, scheme: str):
        """Shutdown hook for a specific S3 Transfer Manager."""
        bundle = self._instances.get(scheme)
        if bundle and bundle.s3t:
            logger.info(f"Shutting down S3 Transfer Manager for scheme: {scheme}")
            try:
                 bundle.s3t.shutdown()
                 # Avoid modifying bundle in place during shutdown?
                 # self._instances[scheme] = bundle._replace(s3t=None) # Mark as shut down
            except Exception as e:
                 logger.error(f"Error shutting down S3 Transfer Manager for {scheme}: {e}", exc_info=True)

# Instantiate the manager (singleton pattern)
cloud_file_manager = CloudFileManager()

# --- Helper Functions for Dynamic Accessor Methods ---

def _extract_scheme_and_path(path_obj_or_str: t.Union[str, 'FileLikePath']) -> t.Tuple[str, str, t.Any]:
    """
    Extracts scheme, adjusted path for fsspec, and original path object.
    Returns: (scheme, adjusted_path, original_path)
    """
    original_path = path_obj_or_str
    if hasattr(path_obj_or_str, 'scheme') and hasattr(path_obj_or_str, 'path_as_fsspec'):
        # Assumes FileLikePath object duck typing
        scheme = path_obj_or_str.scheme
        adjusted_path = path_obj_or_str.path_as_fsspec
        return scheme, adjusted_path, original_path
    elif isinstance(path_obj_or_str, str):
        if '://' in path_obj_or_str:
            parts = path_obj_or_str.split('://', 1)
            scheme = parts[0]
            # Basic adjustment: remove scheme. fsspec usually handles bucket/key from path string.
            # For s3, s3://bucket/key -> bucket/key
            # For gs, gs://bucket/key -> bucket/key
            # For file, file:///path -> /path
            # urlparse can help handle file:// paths better
            parsed = urlparse(path_obj_or_str)
            adjusted_path = f"{parsed.netloc}{parsed.path}".lstrip('/') if parsed.netloc else parsed.path.lstrip('/')
            # Handle edge case for file scheme where path might be relative or absolute
            if scheme == 'file': 
                # If original path was file:///abs/path, netloc is empty, path is /abs/path
                # If original path was file://rel/path, netloc is rel, path is /path (urlparse quirk)
                # If original path was file:/abs/path, netloc empty, path /abs/path
                # If original path was /abs/path (no scheme), scheme is 'file', adjusted_path is /abs/path
                # We want absolute paths to start with /, relative paths not to.
                # The most reliable way is to use the original path for 'file'
                adjusted_path = original_path # Use original path for NormalAccessor
            
            return scheme, adjusted_path, original_path
        else:
            # Assume local file path if no scheme provided
            # Pass original path, NormalAccessor handles it
            return 'file', path_obj_or_str, original_path
    else:
        raise TypeError(f"Unsupported path type for scheme extraction: {type(path_obj_or_str)}")


def create_dynamic_sync_method(manager: CloudFileManager, method_name: str):
    """Creates a wrapper for synchronous fsspec methods."""
    def sync_wrapper(path_obj_or_str, *args, **kwargs):
        scheme, adjusted_path, original_path = _extract_scheme_and_path(path_obj_or_str)

        if scheme == 'file':
            # Delegate to NormalAccessor for local files using the original path
            if hasattr(NormalAccessor, method_name):
                 actual_method = getattr(NormalAccessor, method_name)
                 # NormalAccessor methods expect the standard path, not adjusted
                 return actual_method(original_path, *args, **kwargs)
            else:
                 # NormalAccessor might not have all fsspec methods (e.g., checksum)
                 # Should we attempt to use fsspec 'file' backend here? 
                 # For now, raise error for missing methods on NormalAccessor.
                 raise NotImplementedError(f"Sync method '{method_name}' not available for local 'file' scheme via NormalAccessor.")

        fs = manager.get_fs(scheme)
        if not fs:
            raise ValueError(f"Synchronous filesystem for scheme '{scheme}' not available or failed to initialize.")
        
        try:
            actual_method = getattr(fs, method_name)
        except AttributeError:
             raise NotImplementedError(f"Sync method '{method_name}' not found on filesystem for scheme '{scheme}'.")
        
        # Pass the fsspec-adjusted path to the filesystem method
        return actual_method(adjusted_path, *args, **kwargs)
    
    # Try to preserve docstrings if possible
    sync_wrapper.__doc__ = f"Dynamically calls '{method_name}' on the appropriate sync filesystem based on path scheme."
    sync_wrapper.__name__ = method_name
    return sync_wrapper


def create_dynamic_async_method(manager: CloudFileManager, fsspec_method_names: t.List[str]):
    """Creates a wrapper for asynchronous fsspec methods."""
    requested_name = fsspec_method_names[0] # Name used for docstring/error reporting

    async def async_wrapper(path_obj_or_str, *args, **kwargs):
        scheme, adjusted_path, original_path = _extract_scheme_and_path(path_obj_or_str)

        if scheme == 'file':
             # Async local file operations are complex, delegate or raise
             # Consider using aiofiles if needed, but fsspec doesn't guarantee async file ops
             raise NotImplementedError(f"Async method '{requested_name}' not currently supported for local 'file' scheme.")

        fsa = manager.get_fsa(scheme)
        if not fsa:
            raise ValueError(f"Asynchronous filesystem for scheme '{scheme}' not available or failed to initialize.")

        actual_method = None
        tried_names = []
        for name in fsspec_method_names:
            tried_names.append(name)
            if hasattr(fsa, name):
                actual_method = getattr(fsa, name)
                break
        
        if not actual_method:
            raise NotImplementedError(f"Async method '{requested_name}' (tried: {tried_names}) not found on filesystem for scheme '{scheme}'.")

        # Pass the fsspec-adjusted path
        return await actual_method(adjusted_path, *args, **kwargs)

    async_wrapper.__doc__ = f"Dynamically calls async method '{requested_name}' (e.g., {fsspec_method_names}) on the appropriate async filesystem."
    async_wrapper.__name__ = requested_name # Keep original name for identification
    return async_wrapper


# --- Base Accessor using Dynamic Methods ---

class BaseFileSystemAccessor(NormalAccessor):
    """
    Provides a unified accessor interface for file operations, dynamically
    routing calls to the appropriate filesystem (local or cloud) based on
    the path's URI scheme. Inherits local file methods from NormalAccessor.
    """
    
    # Use the dynamic creators for cloud methods
    # Pass the target fsspec method name(s)

    # Sync Methods (delegated to cloud_file_manager or NormalAccessor)
    info = create_dynamic_sync_method(cloud_file_manager, 'info')
    metadata = create_dynamic_sync_method(cloud_file_manager, 'metadata') # Often alias for info
    stat = create_dynamic_sync_method(cloud_file_manager, 'stat')
    size = create_dynamic_sync_method(cloud_file_manager, 'size')
    exists = create_dynamic_sync_method(cloud_file_manager, 'exists')
    isdir = create_dynamic_sync_method(cloud_file_manager, 'isdir') # Map accessor name to fsspec name
    is_dir = isdir # Alias
    isfile = create_dynamic_sync_method(cloud_file_manager, 'isfile') # Map accessor name to fsspec name
    is_file = isfile # Alias
    copy = create_dynamic_sync_method(cloud_file_manager, 'copy')
    cp = copy # Alias
    copy_file = create_dynamic_sync_method(cloud_file_manager, 'cp_file') # Map accessor name to fsspec name
    cp_file = copy_file # Alias
    get = create_dynamic_sync_method(cloud_file_manager, 'get')
    get_file = create_dynamic_sync_method(cloud_file_manager, 'get_file')
    put = create_dynamic_sync_method(cloud_file_manager, 'put')
    put_file = create_dynamic_sync_method(cloud_file_manager, 'put_file')
    checksum = create_dynamic_sync_method(cloud_file_manager, 'checksum')
    open = create_dynamic_sync_method(cloud_file_manager, 'open')
    ls = create_dynamic_sync_method(cloud_file_manager, 'ls') # Map accessor name to fsspec name
    listdir = ls # Alias
    walk = create_dynamic_sync_method(cloud_file_manager, 'walk')
    glob = create_dynamic_sync_method(cloud_file_manager, 'glob')
    find = create_dynamic_sync_method(cloud_file_manager, 'find')
    touch = create_dynamic_sync_method(cloud_file_manager, 'touch')
    cat = create_dynamic_sync_method(cloud_file_manager, 'cat')
    cat_file = create_dynamic_sync_method(cloud_file_manager, 'cat_file')
    pipe = create_dynamic_sync_method(cloud_file_manager, 'pipe')
    pipe_file = create_dynamic_sync_method(cloud_file_manager, 'pipe_file')
    mkdir = create_dynamic_sync_method(cloud_file_manager, 'mkdir')
    mkdirs = create_dynamic_sync_method(cloud_file_manager, 'mkdirs') # fsspec uses mkdirs or makedirs
    makedirs = mkdirs # Alias
    # Map rm/unlink/rmdir to appropriate fsspec methods (rm, rm_file, rmdir)
    rm = create_dynamic_sync_method(cloud_file_manager, 'rm') 
    remove = rm # Alias
    rm_file = create_dynamic_sync_method(cloud_file_manager, 'rm_file')
    unlink = rm_file # Alias for consistency with os module
    rmdir = create_dynamic_sync_method(cloud_file_manager, 'rmdir')
    rename = create_dynamic_sync_method(cloud_file_manager, 'rename') # fsspec often uses mv or rename
    replace = rename # Alias for consistency with os module
    modified = create_dynamic_sync_method(cloud_file_manager, 'modified')
    url = create_dynamic_sync_method(cloud_file_manager, 'url')
    ukey = create_dynamic_sync_method(cloud_file_manager, 'ukey')
    setxattr = create_dynamic_sync_method(cloud_file_manager, 'setxattr')
    invalidate_cache = create_dynamic_sync_method(cloud_file_manager, 'invalidate_cache')

    # Async Methods (delegated to cloud_file_manager)
    # Provide list of potential fsspec async method names
    ainfo = create_dynamic_async_method(cloud_file_manager, ['info', 'stat']) # Async info might be just stat
    astat = ainfo # Alias
    ametadata = ainfo # Alias
    asize = create_dynamic_async_method(cloud_file_manager, ['size'])
    aexists = create_dynamic_async_method(cloud_file_manager, ['exists'])
    aisdir = create_dynamic_async_method(cloud_file_manager, ['isdir'])
    ais_dir = aisdir
    aisfile = create_dynamic_async_method(cloud_file_manager, ['isfile'])
    ais_file = aisfile
    acopy = create_dynamic_async_method(cloud_file_manager, ['copy', 'cp'])
    acp = acopy
    acopy_file = create_dynamic_async_method(cloud_file_manager, ['cp_file'])
    acp_file = acopy_file
    aget = create_dynamic_async_method(cloud_file_manager, ['get'])
    aget_file = create_dynamic_async_method(cloud_file_manager, ['get_file'])
    aput = create_dynamic_async_method(cloud_file_manager, ['put'])
    aput_file = create_dynamic_async_method(cloud_file_manager, ['put_file'])
    achecksum = create_dynamic_async_method(cloud_file_manager, ['checksum'])
    # Note: fsspec async open is often _open
    aopen = create_dynamic_async_method(cloud_file_manager, ['_open']) 
    als = create_dynamic_async_method(cloud_file_manager, ['ls', 'listdir']) # s3fs uses ls, gcsfs uses listdir?
    alistdir = als
    awalk = create_dynamic_async_method(cloud_file_manager, ['walk'])
    aglob = create_dynamic_async_method(cloud_file_manager, ['glob'])
    afind = create_dynamic_async_method(cloud_file_manager, ['find'])
    atouch = create_dynamic_async_method(cloud_file_manager, ['touch'])
    acat = create_dynamic_async_method(cloud_file_manager, ['cat'])
    acat_file = create_dynamic_async_method(cloud_file_manager, ['cat_file'])
    apipe = create_dynamic_async_method(cloud_file_manager, ['pipe'])
    apipe_file = create_dynamic_async_method(cloud_file_manager, ['pipe_file'])
    amkdir = create_dynamic_async_method(cloud_file_manager, ['mkdir'])
    amakedirs = create_dynamic_async_method(cloud_file_manager, ['mkdirs', 'makedirs']) # fsspec uses mkdirs or makedirs
    amkdirs = amakedirs
    arm = create_dynamic_async_method(cloud_file_manager, ['rm'])
    aremove = arm
    arm_file = create_dynamic_async_method(cloud_file_manager, ['rm_file'])
    aunlink = arm_file
    armdir = create_dynamic_async_method(cloud_file_manager, ['rmdir'])
    arename = create_dynamic_async_method(cloud_file_manager, ['rename', 'mv']) # fsspec often uses mv or rename
    areplace = arename
    amodified = create_dynamic_async_method(cloud_file_manager, ['modified'])
    aurl = create_dynamic_async_method(cloud_file_manager, ['url'])
    aukey = create_dynamic_async_method(cloud_file_manager, ['ukey'])
    asetxattr = create_dynamic_async_method(cloud_file_manager, ['setxattr'])
    ainvalidate_cache = create_dynamic_async_method(cloud_file_manager, ['invalidate_cache'])


    is_fsspec: bool = True # Indicates this accessor potentially uses fsspec

    # Method to get underlying filesystem - useful for advanced usage
    @classmethod
    def get_filesystem(cls, scheme: str) -> t.Optional[AbstractFileSystem]:
         """Gets the underlying sync fsspec filesystem instance for a scheme."""
         return cloud_file_manager.get_fs(scheme)

    @classmethod
    def get_async_filesystem(cls, scheme: str) -> t.Optional[AsyncFileSystem]:
         """Gets the underlying async fsspec filesystem instance for a scheme."""
         return cloud_file_manager.get_fsa(scheme)
    
    @classmethod
    def get_s3_transfer_manager(cls, scheme: str) -> t.Optional[TransferManager]:
         """Gets the S3 Transfer Manager instance for an S3-like scheme."""
         return cloud_file_manager.get_s3t(scheme)

    @classmethod
    def get_provider_config(cls, scheme: str) -> t.Optional[ProviderConfig]:
         """Gets the ProviderConfig instance for a scheme."""
         return cloud_file_manager.get_config(scheme)


# Ensure manager is initialized (optional, depends on import time vs first use)
# try:
#      cloud_file_manager.settings 
# except Exception as e:
#      logger.error(f"Error during initial CloudFileManager setup: {e}", exc_info=True)
