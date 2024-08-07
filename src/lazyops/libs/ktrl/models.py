from __future__ import annotations

"""
Base Ktrl Models and Schemas
"""

import yaml
from lazyops.utils import Timer
from lazyops.utils.logs import logger
from typing import Any, Dict, Optional, List, Tuple, Set, Union, Type, TYPE_CHECKING
from kr8s.objects import new_class, object_from_spec

if TYPE_CHECKING:
    import kopf
    from kr8s.asyncio import objects as obj
    from lazyops.libs.kz.client import KubernetesContext
    from lazyops.libs.kopf_resources import Resource


Certificate = new_class(
    kind = 'Certificate',
    version = 'cert-manager.io/v1',
    namespaced=True,
)


class BaseKtrl:
    """
    The Base Ktrl Class
    """

    APP_NAME = 'ktrl'
    CRD_OBJECT: Optional[Type['Resource']] = None

    def __init__(
        self,
        **kwargs,
    ):
        """
        Initializes the Ktrl Object
        """
        from lazyops.libs.ktrl.config import get_ktrl_settings
        self.settings = get_ktrl_settings()
        self.ctx: Optional['KubernetesContext'] = None
        self.t = Timer()
        self.paused = False
        self.namespaces: Optional[List[str]] = []
        self.kwargs = kwargs
        self.post_init(**kwargs)

    @property
    def has_crd(self) -> bool:
        """
        Returns whether the CRD is installed
        """
        return self.CRD_OBJECT is not None


    def post_init(self, **kwargs):
        """
        Post Initialization
        """
        pass

    async def configure(self) -> None:
        """
        Configure the Operator
        """
        if self.ctx is not None: return
        from lazyops.libs.kz.client import Kubernetes
        self.ctx = Kubernetes.get_or_init(
            name = self.settings.ctx_name, 
            kubeconfig = self.settings.kubeconfig
        )
        await self.ctx.ainit()
        logger.info('Configured Kubernetes Context')
        self.namespaces = await self.gather_namespaces()
        logger.info(self.namespaces, colored = True, prefix = 'Namespaces')
        if self.has_crd: await self.ensure_crd()
        await self.post_configure()

    async def post_configure(self, **kwargs):
        """
        Post Configuration
        """
        pass

    def convert_body(self, body: 'kopf.Body') -> Dict[str, Any]:
        """
        Converts the body to a dictionary
        """
        data = dict(body)
        _ = data.pop('status', None)
        data['metadata'] = {
            k: v for k, v in data['metadata'].items() if k in \
            {'name', 'namespace', 'labels', 'annotations'}
        }
        return data
    

    async def gather_namespaces(self) -> List[str]:
        """
        Gathers the namespaces
        """
        await self.configure()
        namespaces: List['obj.Namespace'] = await self.ctx.aget('namespaces')
        namespaces = [ns.name for ns in namespaces]
        if self.settings.disabled_namespaces:
            namespaces = [ns for ns in namespaces if ns not in self.settings.disabled_namespaces]
        if self.settings.enabled_namespaces:
            for ns in self.settings.enabled_namespaces:
                if ns not in namespaces:
                    namespaces.append(ns)
        return namespaces
    

    async def ensure_crd(self):
        """
        Ensures the CRD is installed
        """
        crd_obj = await object_from_spec(
            yaml.safe_load(self.settings.templates_path.joinpath('crd.yaml').read_text()), 
            api = self.ctx.aclient, 
            allow_unknown_type = True, 
            _asyncio = True
        )
        if await crd_obj.exists():
            await crd_obj.patch(crd_obj.raw)
            logger.info('CRD Updated', colored = True, prefix = self.APP_NAME)
            return
        await crd_obj.create()
        logger.info('CRD Created', colored = True, prefix = self.APP_NAME)
    