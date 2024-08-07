"""
K8s Configs
"""
import pathlib

from typing import Optional, Union
from lazyops.types.models import BaseSettings, validator
from lazyops.types.classprops import lazyproperty

class K8sSettings(BaseSettings):
    namespace: Optional[str] = None
    kubeconfig: Optional[Union[str, pathlib.Path]] = None
    kubernetes_service_host: Optional[str] = None
    kubernetes_service_port: Optional[int] = None

    @validator("kubeconfig", pre=True)
    def validate_kubeconfig(cls, v):
        if v is not None: return v
        from lazyops.utils.system import (
            get_k8s_kubeconfig
        )
        return get_k8s_kubeconfig()
    
    @validator("namespace", pre=True)
    def validate_namespace(cls, v):
        if v is not None: return v
        from lazyops.utils.system import (
            get_k8s_namespace
        )
        return get_k8s_namespace()

    @lazyproperty
    def in_k8s(self) -> bool:
        from lazyops.utils.system import (
            is_in_kubernetes
        )
        return is_in_kubernetes()
    
    @lazyproperty
    def in_cluster(self) -> bool:
        return (
            self.kubernetes_service_host is not None and self.kubernetes_service_port is not None
        ) or self.in_k8s
    
