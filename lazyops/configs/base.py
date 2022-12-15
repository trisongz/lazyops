from __future__ import absolute_import

"""
Base Configs
"""
import pathlib
import contextlib
from typing import Optional, Union, TYPE_CHECKING
from lazyops.types.models import BaseSettings
from lazyops.types.classprops import lazyproperty

from lazyops.imports._fileio import (
    File, 
    FileLike, 
    _fileio_available, 
)

from lazyops.imports._aiokeydb import (
    aiokeydb, 
    resolve_aiokeydb,
    _aiokeydb_available, 
)

if TYPE_CHECKING:
    from lazyops.configs.cloud import BotoSettings, AwsSettings, GcpSettings, MinioSettings
    from lazyops.configs.k8s import K8sSettings


class DefaultSettings(BaseSettings):

    ## General Variables
    api_host: Optional[str] = None
    api_port: Optional[int] = None
    
    app_name: Optional[str] = None
    app_host: Optional[str] = None
    app_port: Optional[int] = None
    
    ## Directory Variables
    app_dir: Optional[Union[str, pathlib.Path]] = None
    data_dir: Optional[Union[str, pathlib.Path]] = None
    model_dir: Optional[Union[str, pathlib.Path]] = None

    ## Context Variables
    in_docker: Optional[bool] = None

    ## Logging Variables
    log_level: Optional[str] = None
    log_format: Optional[str] = None
    
    ## Debug Variables
    debug_enabled: Optional[bool] = None

    ## Multithreading Variables
    max_workers: Optional[int] = None

    ## Huggingface Variables
    hf_home: Optional[Union[str, pathlib.Path]] = None
    hf_token: Optional[str] = None
    huggingface_token: Optional[str] = None

    huggingface_hub_cache: Optional[Union[str, pathlib.Path]] = None
    transformers_cache: Optional[Union[str, pathlib.Path]] = None
    sentence_transformers_home: Optional[Union[str, pathlib.Path]] = None

    """
    Host Variables
    """
    @lazyproperty
    def host_name(self) -> str:
        from lazyops.utils.system import get_host_name
        return get_host_name()

    @lazyproperty
    def host_ip(self):
        from lazyops.utils.system import get_host_ip
        return get_host_ip()
    
    @lazyproperty
    def cpu_count(self) -> int:
        from lazyops.utils.system import get_cpu_count
        return get_cpu_count()
    
    @lazyproperty
    def num_workers(self) -> int:
        return self.max_workers or (self.cpu_count * 2)
    

    """
    Directories
    """

    @lazyproperty
    def home(self) -> str:
        return pathlib.Path.home().as_posix()
    
    @lazyproperty
    def home_path(self) -> FileLike:
        return File(self.home) if _fileio_available else pathlib.Path(self.home)
    
    @lazyproperty
    def context_dir(self) -> str:
        if self.in_colab: return '/content'
        return '/' if self.is_remote else pathlib.Path.cwd().as_posix()
    
    @lazyproperty
    def context_path(self) -> FileLike:
        return File(self.context_dir) if _fileio_available else pathlib.Path(self.context_dir)

    @lazyproperty
    def app_path(self) -> FileLike:
        app_dir = self.app_dir or self.context_path.joinpath('app')
        return File(app_dir) if _fileio_available else pathlib.Path(app_dir)
    
    @lazyproperty
    def data_path(self) -> FileLike:
        data_dir = self.data_dir or self.context_path.joinpath('data')
        return File(data_dir) if _fileio_available else pathlib.Path(data_dir)
    
    @lazyproperty
    def model_path(self) -> FileLike:
        model_dir = self.model_dir or self.data_path.joinpath('models')
        return File(model_dir) if _fileio_available else pathlib.Path(model_dir)
    

    """
    Context / Env
    """

    ## Torch Variables
    @lazyproperty
    def torch_device(self):
        from lazyops.utils.system import get_torch_device
        return get_torch_device()
    
    @lazyproperty
    def torch_device_name(self):
        from lazyops.utils.system import get_torch_device_name
        return get_torch_device_name()
    
    @lazyproperty
    def in_colab(self) -> bool:
        with contextlib.suppress(ImportError):
            import google.colab
            return True
        return False
    
    @lazyproperty
    def in_k8s(self) -> bool:
        return self.k8s.in_cluster
    
    @lazyproperty
    def in_api(self) -> bool:
        return self.api_host is not None and self.api_port is not None
    
    @lazyproperty
    def in_app(self) -> bool:
        return self.app_host is not None and self.app_port is not None
    
    @lazyproperty
    def is_local(self) -> bool:
        return not any(self.in_k8s, self.in_k8s, self.in_api, self.in_docker)
    
    @lazyproperty
    def is_remote(self) -> bool:
        return self.in_k8s or self.in_api or self.in_docker
    
    """
    Huggingface Variables
    """
    
    @lazyproperty
    def hf_home_path(self) -> FileLike:
        hf_home = self.hf_home or self.model_path.joinpath('.hf')
        return File(hf_home) if _fileio_available else pathlib.Path(hf_home)

    @lazyproperty
    def hf_hub_cache_path(self) -> FileLike:
        if self.huggingface_hub_cache:
            return File(self.huggingface_hub_cache) if _fileio_available else pathlib.Path(self.huggingface_hub_cache)
        return self.hf_home_path
    
    @lazyproperty
    def huggingface_path(self) -> pathlib.Path:
        return self.home_path.joinpath('.huggingface')
    
    @lazyproperty
    def huggingface_token_path(self) -> pathlib.Path:
        return self.huggingface_path.joinpath('token')
    

    @lazyproperty
    def huggingface_token_exists(self) -> bool:
        return self.huggingface_token_path.exists()
    
    @lazyproperty
    def huggingface_auth_token(self) -> str:
        return self.hf_token or self.huggingface_token

    """
    Nested Cloud Settings
    """

    @lazyproperty
    def boto(self) -> 'BotoSettings':
        from lazyops.configs.cloud import BotoSettings
        return BotoSettings()

    @lazyproperty
    def aws(self) -> 'AwsSettings':
        from lazyops.configs.cloud import AwsSettings
        return AwsSettings()
    
    @lazyproperty
    def gcp(self) -> 'GcpSettings':
        from lazyops.configs.cloud import GcpSettings
        return GcpSettings()
    
    @lazyproperty
    def minio(self) -> 'MinioSettings':
        from lazyops.configs.cloud import MinioSettings
        return MinioSettings()
    
    """
    Nested Settings
    """

    @lazyproperty
    def k8s(self) -> 'K8sSettings':
        from lazyops.configs.k8s import K8sSettings
        return K8sSettings()
    
    @lazyproperty
    def keydb(self) -> 'aiokeydb.KeyDBSettings':
        if not _aiokeydb_available:
            resolve_aiokeydb()
        return aiokeydb.KeyDBClient.get_settings()
    