from __future__ import annotations

"""
Kubernetes Client based on kr8s
"""
import os
import abc
import kr8s
import httpx
import base64
import functools
import contextlib
from pathlib import Path
from lazyops.libs.proxyobj.wraps import proxied
from lazyops.libs.proxyobj import ProxyObject
from lazyops.libs.logging import logger
from typing import Optional, Dict, TYPE_CHECKING
from .context import KubernetesContext
    
# @proxied
class KubernetesClient(abc.ABC):
    """
    The Kubernetes Client
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the Kubernetes Client

        - For use in Kubernetes, the client will automatically use the in-cluster configuration
        - For use outside of Kubernetes, the client will use the kubeconfigs directory
          env: KUBECONFIGS_DIR
        """
        from lazyops.utils.system import is_in_kubernetes
        self.in_k8s = is_in_kubernetes()
        self.kconfigs_path = None
        if not self.in_k8s:
            if kctx_dir := os.getenv('KUBECONFIGS_DIR', os.getenv('KUBECONFIG_DIR', os.path.expanduser('~/.kube'))):
                self.kconfigs_path = Path(kctx_dir)
        self._ctxs: Dict[str, KubernetesContext] = {}
        self._default: Optional[str] = None
        self._kwargs = kwargs

    
    def find_kubeconfig_ctx(self, name: str) -> Optional[Path]:
        """
        Find a kubeconfig context
        """
        if self.kconfigs_path:
            for ctx_fname in self.kconfigs_path.iterdir():
                if name in ctx_fname.name:
                    logger.info(f'Using kubeconfig: `{ctx_fname.name}`')
                    return ctx_fname
        return None

    def get_or_init(
        self,
        name: Optional[str] = None, 
        url: Optional[str] = None,
        kubeconfig: Optional[str] = None,
        service_account: Optional[str] = None,
        context: Optional[str] = None,
        namespace: Optional[str] = None,
        set_as_default: Optional[bool] = False,
        **kwargs
    ) -> KubernetesContext:
        """
        Get or initialize a context
        """
        name = name if name is not None else (self._default or 'default')
        if name not in self._ctxs:
            if name != 'default' and not kubeconfig:
                kubeconfig = self.find_kubeconfig_ctx(name)
            self._ctxs[name] = KubernetesContext(
                name = name,
                url = url,
                kubeconfig = kubeconfig,
                service_account = service_account,
                context = context,
                namespace = namespace,
                **kwargs
            )
            if self._default is None or set_as_default:
                self._default = name
        return self._ctxs[name]

    @property
    def ctx(self) -> KubernetesContext:
        """
        Returns the default context
        """
        if self._default is None:
            return self.get_or_init()
        return self._ctxs[self._default]
    
    async def ainit(self) -> None:
        """
        Initialize the client
        """
        if not self._ctxs:
            await self.ctx.ainit()
        else:
            for ctx in self._ctxs.values():
                await ctx.ainit()

    def __getitem__(self, name: str) -> KubernetesContext:
        """
        Get a context
        """
        return self._ctxs[name]
    

Kubernetes: KubernetesClient = ProxyObject(
    obj_cls = KubernetesClient,
)