from __future__ import annotations

""""
Cloud Filesystem
"""

import atexit
import functools
import typing as t
from lzl.require import LazyLib
from ..path import NormalAccessor
from ..utils.logs import logger
from .utils import (
    rewrite_async_syntax,
    create_method_fs,
    create_async_method_fs,
    create_staticmethod,
    create_async_coro,
)

if t.TYPE_CHECKING:
    from ..configs.main import FileIOConfig, ProviderConfig
    from fsspec.spec import AbstractFileSystem
    from fsspec.asyn import AsyncFileSystem
    from s3transfer.manager import TransferManager
    from boto3.session import Session

    _FST = t.TypeVar('_FST', bound=AbstractFileSystem)
    _ASFST = t.TypeVar('_ASFST', bound=AsyncFileSystem)

_MappedProviderAliases: t.Dict[str, str] = {
    's3fs': 'aws',
    'mc': 'minio',
}

_SupportedProviders: t.List[str] = [
    'aws',
    'gcp',
    'minio',
    's3c',
    'r2',
]

class CloudFileSystemMeta(type):
    """
    The Cloud File System
    """

    fs: t.Optional['_FST'] = None
    fsa: t.Optional['_ASFST'] = None
    fs_name: t.Optional[str] = None
    fsconfig: t.Optional['ProviderConfig'] = None

    boto: t.Optional['Session'] = None

    _s3t: t.Optional[t.Callable[..., 'TransferManager']] = None
    s3t: t.Optional['TransferManager'] = None
    # s3t: t.Optional[t.Union['TransferManager', t.Callable[..., 'TransferManager']]] = None
    
    _settings: t.Optional['FileIOConfig'] = None
    

    @property
    def settings(cls) -> 'FileIOConfig':
        """
        Returns the settings of the Cloud File System
        """
        if cls._settings is None:
            from lzl.io.file.utils import get_settings
            cls._settings = get_settings()
        return cls._settings
    
    def is_ready(cls) -> bool:
        """
        Returns whether the Cloud File System is ready
        """
        return bool(cls.fsa and cls.fs)
    

    def build_s3c(
        cls,
        provider: t.Optional[str] = 'aws',
        **auth_config: t.Any,
    ):
        """
        Builds the S3 Client
        """
        LazyLib.import_lib('s3fs')
        LazyLib.import_lib('boto3')

        import s3fs
        import boto3
        import boto3.s3.transfer as s3transfer
        from botocore.config import Config as BotoConfig

        fsspec_fs = s3fs.S3FileSystem
        if provider == 'r2':
            from .compat.r2 import R2FileSystem
            fsspec_fs = R2FileSystem

        config, pconfig = cls.settings.get_provider_config(provider, **auth_config)
        cls.fs = fsspec_fs(asynchronous = False, **config)
        cls.fsa = rewrite_async_syntax(fsspec_fs(asynchronous=True, **config))

        boto_config = BotoConfig(**pconfig.get_boto_config())
        cls.boto = boto3.client(
            's3',
            config = boto_config,
            **pconfig.get_boto_client_config()
        )
        transfer_config = s3transfer.TransferConfig(
            use_threads = True,
            max_concurrency = cls.settings.max_pool_connections
        )
        create_s3t = functools.partial(
            s3transfer.create_transfer_manager,
            cls.boto, 
            transfer_config
        )
        cls._s3t = create_s3t
        # cls.s3t = create_s3t()
        # if provider == 'r2':
        #     s3tm = create_s3t()
        #     cls.s3t = s3tm
        #     cls.fs.s3tm = s3tm
        #     cls.fsa.s3tm = s3tm
        # else:
        #     cls.s3t = property(create_s3t)
        cls.fsconfig = pconfig.model_copy()


    def build_filesystems(self, force: bool = False, **auth_config):
        """
        Lazily inits the filesystems
        """
        if self.fs is not None and self.fsa is not None and not force: 
            return
        
        if self.fs_name in _SupportedProviders:
            provider = _MappedProviderAliases.get(self.fs_name, self.fs_name)
            return self.build_s3c(provider = provider, **auth_config)
        raise NotImplementedError(f'Cloud File System `{self.fs_name}` is not supported')


    def reload_filesystem(cls):
        """ 
        Reinitializes the Filesystem
        """
        raise NotImplementedError



class BaseFileSystemAccessor(NormalAccessor):
    """
    Base File System Accessor
    """

    class CloudFileSystem(metaclass = CloudFileSystemMeta):
        pass


    info: t.Callable = create_staticmethod(CloudFileSystem, 'info')
    metadata: t.Callable = create_staticmethod(CloudFileSystem, 'metadata')
    stat: t.Callable = create_staticmethod(CloudFileSystem, 'stat')
    size: t.Callable = create_staticmethod(CloudFileSystem, 'size')
    exists: t.Callable = create_staticmethod(CloudFileSystem, 'exists')
    is_dir: t.Callable = create_staticmethod(CloudFileSystem, 'isdir')
    is_file: t.Callable = create_staticmethod(CloudFileSystem, 'isfile')
    copy: t.Callable = create_staticmethod(CloudFileSystem, 'copy')
    copy_file: t.Callable = create_staticmethod(CloudFileSystem, 'cp_file')
    get_file: t.Callable = create_staticmethod(CloudFileSystem, 'get_file')
    put_file: t.Callable = create_staticmethod(CloudFileSystem, 'put_file')
    metadata: t.Callable = create_staticmethod(CloudFileSystem, ['metadata', 'info'])
    checksum: t.Callable = create_staticmethod(CloudFileSystem, 'checksum')

    get: t.Callable = create_staticmethod(CloudFileSystem, 'get')
    put: t.Callable = create_staticmethod(CloudFileSystem, 'put')

    open: t.Callable = create_method_fs(CloudFileSystem, 'open')
    listdir: t.Callable = create_staticmethod(CloudFileSystem, 'ls')    
    walk: t.Callable = create_staticmethod(CloudFileSystem, 'walk')

    glob: t.Callable = create_method_fs(CloudFileSystem, 'glob')
    find: t.Callable = create_method_fs(CloudFileSystem, 'find')
    touch: t.Callable = create_method_fs(CloudFileSystem, 'touch')
    cat: t.Callable = create_method_fs(CloudFileSystem, 'cat')
    cat_file: t.Callable = create_method_fs(CloudFileSystem, 'cat_file')
    
    
    pipe: t.Callable = create_method_fs(CloudFileSystem, 'pipe')
    pipe_file: t.Callable = create_method_fs(CloudFileSystem, 'pipe_file')
    
    mkdir: t.Callable = create_method_fs(CloudFileSystem, 'mkdir')
    makedirs: t.Callable = create_method_fs(CloudFileSystem, ['makedirs', 'mkdirs'])
    unlink: t.Callable = create_method_fs(CloudFileSystem, 'rm_file')
    rmdir: t.Callable = create_method_fs(CloudFileSystem, 'rmdir')
    rename: t.Callable = create_method_fs(CloudFileSystem, 'rename')
    replace: t.Callable = create_method_fs(CloudFileSystem, 'rename')
    remove: t.Callable = create_method_fs(CloudFileSystem, 'rm')
    rm: t.Callable = create_staticmethod(CloudFileSystem, 'rm')
    rm_file: t.Callable = create_staticmethod(CloudFileSystem, 'rm_file')
    
    modified: t.Callable = create_method_fs(CloudFileSystem, 'modified')
    url: t.Callable = create_method_fs(CloudFileSystem, 'url')
    ukey: t.Callable = create_method_fs(CloudFileSystem, 'ukey')
    setxattr: t.Callable = create_method_fs(CloudFileSystem, 'setxattr')
    invalidate_cache: t.Callable = create_method_fs(CloudFileSystem, 'invalidate_cache')
    
    filesys: '_FST' = CloudFileSystem.fs
    afilesys: '_ASFST' = CloudFileSystem.fsa
    fsconfig: t.Optional['ProviderConfig'] = CloudFileSystem.fsconfig

    boto: t.Optional['Session'] = CloudFileSystem.boto
    _s3t: t.Optional[t.Callable[..., 'TransferManager']] = CloudFileSystem._s3t
    s3t: t.Optional['TransferManager'] = None 
    # CloudFileSystem.s3t
    # s3t: t.Optional[t.Union['TransferManager', t.Callable[..., 'TransferManager']]] = CloudFileSystem.s3t
    
    
    # Async Methods
    astat: t.Callable = create_async_coro(CloudFileSystem, 'stat')
    atouch: t.Callable = create_async_coro(CloudFileSystem, 'touch')
    aukey: t.Callable = create_async_coro(CloudFileSystem, 'ukey')
    asize: t.Callable = create_async_coro(CloudFileSystem, 'size')
    # aurl: t.Callable = create_async_coro(CloudFileSystem, 'url')
    # asetxattr: t.Callable = create_async_coro(CloudFileSystem, 'setxattr')
    aurl: t.Callable = create_async_method_fs(CloudFileSystem, 'url')
    asetxattr: t.Callable = create_async_method_fs(CloudFileSystem, 'setxattr')

    amodified: t.Callable = create_async_coro(CloudFileSystem, 'modified')
    ainvalidate_cache: t.Callable = create_async_coro(CloudFileSystem, 'invalidate_cache')
    arename: t.Callable = create_async_coro(CloudFileSystem, 'rename')
    areplace: t.Callable = create_async_coro(CloudFileSystem, 'rename')

    ainfo: t.Callable = create_async_method_fs(CloudFileSystem, 'ainfo')
    ametadata: t.Callable = create_async_method_fs(CloudFileSystem, 'ametadata')
    aexists: t.Callable = create_async_method_fs(CloudFileSystem, 'aexists')
    aglob: t.Callable = create_async_method_fs(CloudFileSystem, 'aglob')
    afind: t.Callable = create_async_method_fs(CloudFileSystem, 'afind')
    ais_dir: t.Callable = create_async_method_fs(CloudFileSystem, 'aisdir')
    ais_file: t.Callable = create_async_method_fs(CloudFileSystem, 'ais_file')
    acopy: t.Callable = create_async_method_fs(CloudFileSystem, 'acopy')
    acopy_file: t.Callable = create_async_method_fs(CloudFileSystem, 'acp_file')

    apipe: t.Callable = create_async_method_fs(CloudFileSystem, 'apipe')
    apipe_file: t.Callable = create_async_method_fs(CloudFileSystem, 'apipe_file')

    aget: t.Callable = create_async_coro(CloudFileSystem, 'aget')
    aget_file: t.Callable = create_async_coro(CloudFileSystem, 'aget_file')
    
    aput: t.Callable = create_async_method_fs(CloudFileSystem, 'aput')
    aput_file: t.Callable = create_async_method_fs(CloudFileSystem, 'aput_file')
    # ametadata: t.Callable = create_async_method_fs(CloudFileSystem, 'ametadata')
    aopen: t.Callable = create_async_method_fs(CloudFileSystem, '_open')
    amkdir: t.Callable = create_async_method_fs(CloudFileSystem, 'amkdir')
    amakedirs: t.Callable = create_async_method_fs(CloudFileSystem, 'amakedirs')
    aunlink: t.Callable = create_async_method_fs(CloudFileSystem, 'arm_file')
    armdir: t.Callable = create_async_method_fs(CloudFileSystem, 'armdir')
    aremove: t.Callable = create_async_method_fs(CloudFileSystem, 'arm')
    arm: t.Callable = create_async_method_fs(CloudFileSystem, 'arm')
    arm_file: t.Callable = create_async_coro(CloudFileSystem, 'arm_file')
    alistdir: t.Callable = create_async_method_fs(CloudFileSystem, ['alistdir', 'alist_objects'])
    awalk: t.Callable = create_async_method_fs(CloudFileSystem, 'awalk')

    is_fsspec: bool = True


    @classmethod
    def reload_cfs(cls, **kwargs):
        """
        Reloads the Cloud File System
        """
        cls.CloudFileSystem.build_filesystems(**kwargs)
        cls.info: t.Callable = create_staticmethod(cls.CloudFileSystem, 'info')
        cls.stat: t.Callable = create_staticmethod(cls.CloudFileSystem, 'stat')
        cls.size: t.Callable = create_staticmethod(cls.CloudFileSystem, 'size')
        cls.exists: t.Callable = create_staticmethod(cls.CloudFileSystem, 'exists')
        cls.is_dir: t.Callable = create_staticmethod(cls.CloudFileSystem, 'isdir')
        cls.is_file: t.Callable = create_staticmethod(cls.CloudFileSystem, 'isfile')
        cls.copy: t.Callable = create_staticmethod(cls.CloudFileSystem, 'copy')
        cls.copy_file: t.Callable = create_staticmethod(cls.CloudFileSystem, 'cp_file')
        cls.get_file: t.Callable = create_staticmethod(cls.CloudFileSystem, 'get_file')
        cls.put_file: t.Callable = create_staticmethod(cls.CloudFileSystem, 'put_file')
        cls.metadata: t.Callable = create_staticmethod(cls.CloudFileSystem, ['metadata', 'info'])

        cls.open: t.Callable = create_method_fs(cls.CloudFileSystem, 'open')
        cls.listdir: t.Callable = create_staticmethod(cls.CloudFileSystem, 'ls')    
        cls.walk: t.Callable = create_staticmethod(cls.CloudFileSystem, 'walk')
        cls.glob: t.Callable = create_staticmethod(cls.CloudFileSystem, 'glob')
        cls.get: t.Callable = create_staticmethod(cls.CloudFileSystem, 'get')
        cls.put: t.Callable = create_staticmethod(cls.CloudFileSystem, 'put')
        
        cls.checksum: t.Callable = create_method_fs(cls.CloudFileSystem, 'checksum')
        cls.cat: t.Callable = create_staticmethod(cls.CloudFileSystem, 'cat')
        cls.cat_file: t.Callable = create_staticmethod(cls.CloudFileSystem, 'cat_file')
        
        cls.pipe: t.Callable = create_staticmethod(cls.CloudFileSystem, 'pipe')
        cls.pipe_file: t.Callable = create_staticmethod(cls.CloudFileSystem, 'pipe_file')
    

        cls.find: t.Callable = create_method_fs(cls.CloudFileSystem, 'find')
        cls.touch: t.Callable = create_method_fs(cls.CloudFileSystem, 'touch')
        
        
        cls.mkdir: t.Callable = create_method_fs(cls.CloudFileSystem, 'mkdir')
        cls.makedirs: t.Callable = create_method_fs(cls.CloudFileSystem, ['makedirs', 'mkdirs'])
        cls.unlink: t.Callable = create_method_fs(cls.CloudFileSystem, 'rm_file')
        cls.rmdir: t.Callable = create_method_fs(cls.CloudFileSystem, 'rmdir')
        cls.rename : t.Callable = create_method_fs(cls.CloudFileSystem, 'rename')
        cls.replace : t.Callable = create_method_fs(cls.CloudFileSystem, 'rename')
        cls.rm : t.Callable = create_staticmethod(cls.CloudFileSystem, 'rm')
        cls.rm_file : t.Callable = create_staticmethod(cls.CloudFileSystem, 'rm_file')
        
        cls.remove : t.Callable = create_method_fs(cls.CloudFileSystem, 'rm')
        cls.modified: t.Callable = create_method_fs(cls.CloudFileSystem, 'modified')
        cls.setxattr: t.Callable = create_method_fs(cls.CloudFileSystem, 'setxattr')
        cls.url: t.Callable = create_method_fs(cls.CloudFileSystem, 'url')
        cls.ukey: t.Callable = create_method_fs(cls.CloudFileSystem, 'ukey')
        cls.invalidate_cache: t.Callable = create_method_fs(cls.CloudFileSystem, 'invalidate_cache')
        
        cls.filesys = cls.CloudFileSystem.fs
        cls.afilesys = cls.CloudFileSystem.fsa
        cls.fsconfig = cls.CloudFileSystem.fsconfig

        cls.boto = cls.CloudFileSystem.boto
        # cls.s3t = None #  cls.CloudFileSystem.s3t
        cls._s3t = cls.CloudFileSystem._s3t
        
        # Async Methods
        cls.astat: t.Callable = create_async_coro(cls.CloudFileSystem, 'stat')
        cls.atouch: t.Callable = create_async_coro(cls.CloudFileSystem, 'touch')
        cls.aukey: t.Callable = create_async_coro(cls.CloudFileSystem, 'ukey')
        
        # cls.aurl: t.Callable = create_async_coro(cls.CloudFileSystem, 'url')
        cls.asetxattr: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'setxattr')
        cls.aurl: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'url')
        # cls.asetxattr: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'setxattr')

        cls.amodified: t.Callable = create_async_coro(cls.CloudFileSystem, 'modified')
        cls.ainvalidate_cache: t.Callable = create_async_coro(cls.CloudFileSystem, 'invalidate_cache')
        cls.arename: t.Callable = create_async_coro(cls.CloudFileSystem, 'rename')
        cls.areplace: t.Callable = create_async_coro(cls.CloudFileSystem, 'rename')

        cls.ainfo: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'ainfo')
        cls.asize: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'size')
        cls.aexists: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'aexists')

        cls.aglob: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'aglob')
        cls.afind: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'afind')
        
        cls.acat: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'acat')
        cls.acat_file: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'acat_file')
        
        cls.apipe: t.Callable = create_async_coro(cls.CloudFileSystem, 'apipe')
        cls.apipe_file: t.Callable = create_async_coro(cls.CloudFileSystem, 'apipe_file')
        
        cls.ais_dir: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'aisdir')
        cls.ais_file: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'aisfile')
        cls.acopy: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'acopy')
        cls.acopy_file: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'acp_file')
        cls.aget: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'aget')
        cls.aget_file: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'aget_file')
        cls.aput: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'aput')
        cls.aput_file: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'aput_file')
        cls.ametadata: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'ametadata')
        cls.aopen: t.Callable = create_async_method_fs(cls.CloudFileSystem, '_open')
        cls.amkdir: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'amkdir')
        cls.amakedirs: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'amakedirs')
        cls.aunlink: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'arm_file')
        cls.arm_file: t.Callable = create_async_coro(cls.CloudFileSystem, 'arm_file')
        cls.armdir: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'armdir')
        cls.aremove: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'arm')
        cls.arm: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'arm')
        cls.alistdir: t.Callable = create_async_method_fs(cls.CloudFileSystem, ['alistdir', 'alist_objects'])
        cls.awalk: t.Callable = create_async_method_fs(cls.CloudFileSystem, 'awalk')

    @classmethod
    def get_s3t(cls) -> 'TransferManager':
        """
        Returns the s3t transfer manager
        """
        if cls.s3t is None:
            cls.s3t = cls._s3t()
            atexit.register(cls._atexit_)
        return cls.s3t
    

    @classmethod
    def _atexit_(cls):
        """
        Cleans up the Cloud File System
        """
        if cls.s3t is not None:
            logger.info('Shutting Down S3 Transfer Manager')
            cls.s3t.shutdown()
            cls.s3t = None
    