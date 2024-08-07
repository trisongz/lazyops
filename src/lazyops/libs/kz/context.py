from __future__ import annotations

"""
Kubernetes Context based on kr8s
"""
import os
import abc
import kr8s
import httpx
import base64
import functools
import contextlib
from typing import Optional, Dict, Any, List, Union, Generator, Literal, Type, AsyncGenerator, overload, TYPE_CHECKING
from .types import objects, aobjects
if TYPE_CHECKING:
    from kr8s import Api as ClientAPI
    from kr8s.asyncio import Api as AsyncClientAPI
    from .types import ObjectT, ObjectListT, aObjectT, aObjectListT



class KubernetesContext(abc.ABC):
    """
    A Single Kubernetes Context
    """

    def __init__(
        self, 
        name: Optional[str] = None, 
        url: Optional[str] = None,
        kubeconfig: Optional[str] = None,
        service_account: Optional[str] = None,
        context: Optional[str] = None,
        namespace: Optional[str] = None,
        **kwargs
    ):
        self.name = name
        self.url = url
        self.kubeconfig = kubeconfig
        self.service_account = service_account
        self.context = context
        self.namespace = namespace
        self._client: Optional[ClientAPI] = None
        self._aclient: Optional[AsyncClientAPI] = None
        self._ainitialized: bool = False
        self._kwargs = kwargs
        self.objects: Dict[str, Union['objects.APIObject', 'aobjects.APIObject']] = {}

    @property
    def client(self) -> ClientAPI:
        """
        Returns the client
        """
        if self._client is None:
            import kr8s
            self._client = kr8s.api(
                url = self.url,
                kubeconfig = self.kubeconfig,
                serviceaccount = self.service_account,
                context = self.context,
                namespace = self.namespace,
            )
        return self._client
    
    @property
    def aclient(self) -> AsyncClientAPI:
        """
        Returns the async client
        """
        if self._aclient is None:
            import kr8s
            self._aclient = kr8s.asyncio.api(
                url = self.url,
                kubeconfig = self.kubeconfig,
                serviceaccount = self.service_account,
                context = self.context,
                namespace = self.namespace,
            )
        return self._aclient
    

    def raise_if_not_ainit(self):
        """
        Raises if the async client is not initialized
        """
        if not self._ainitialized:
            raise ValueError("The async client is not initialized")
    
    async def ainit(self):
        """
        Initialize the async client
        """
        if not self._ainitialized:
            self._aclient = await self.aclient
            self._ainitialized = True


    @contextlib.asynccontextmanager
    async def call_api(
        self, 
        method: str = "GET",
        version: str = "v1",
        base: str = "",
        namespace: str = None,
        url: str = "",
        raise_for_status: bool = True,
        stream: bool = False,
        **kwargs,
    ) -> AsyncGenerator[httpx.Response, None]:
        """
        [Async] Call the API
        """
        await self.ainit()
        async with self.aclient.call_api(
            method = method,
            version = version,
            base = base,
            namespace = namespace,
            url = url,
            raise_for_status = raise_for_status,
            stream = stream,
            **kwargs
        ) as response:
            yield response
    
    @property
    def Pod(self) -> Type['objects.Pod']:
        """
        Returns the Pod object
        """
        if 'pod' not in self.objects:
            _pod = objects.Pod
            _pod.__init__ = functools.partialmethod(_pod.__init__, api = self.client)
            self.objects['pod'] = _pod
        return self.objects['pod']
    
    @property
    def aPod(self) -> Type['aobjects.Pod']:
        """
        Returns the async Pod object
        """
        self.raise_if_not_ainit()
        if 'apod' not in self.objects:
            _pod = aobjects.Pod
            _pod.__init__ = functools.partialmethod(_pod.__init__, api = self.aclient)
            self.objects['apod'] = _pod
        return self.objects['apod']
    

    @property
    def Service(self) -> Type['objects.Service']:
        """
        Returns the Service object
        """
        if 'service' not in self.objects:
            _service = objects.Service
            _service.__init__ = functools.partialmethod(_service.__init__, api = self.client)
            self.objects['service'] = _service
        return self.objects['service']
    
    @property
    def aService(self) -> Type['aobjects.Service']:
        """
        Returns the async Service object
        """
        self.raise_if_not_ainit()
        if 'aservice' not in self.objects:
            _service = aobjects.Service
            _service.__init__ = functools.partialmethod(_service.__init__, api = self.aclient)
            self.objects['aservice'] = _service
        return self.objects['aservice']
    

    @overload
    def get(
        self,
        name: Literal['pods'] = 'pods',
        namespace: Optional[str] = kr8s.ALL,
        label_selector: Union[str, Dict] = None,
        field_selector: Union[str, Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> List['objects.Pod']:
        ...

    @overload
    def get(
        self,
        name: Literal['services'] = 'services',
        namespace: Optional[str] = kr8s.ALL,
        label_selector: Union[str, Dict] = None,
        field_selector: Union[str, Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> List['objects.Service']:
        ...


    def get(
        self,
        name: str,
        *args,
        namespace: Optional[str] = kr8s.ALL,
        **kwargs,
    ) -> Union['ObjectT', 'ObjectListT']:
        """
        Get an object
        """
        return kr8s.get(name, *args, namespace = namespace, api = self.client, **kwargs)


    @overload
    async def aget(
        self,
        name: Literal['pods'] = 'pods',
        namespace: Optional[str] = kr8s.ALL,
        label_selector: Union[str, Dict] = None,
        field_selector: Union[str, Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> List['aobjects.Pod']:
        ...

    @overload
    async def aget(
        self,
        name: Literal['services'] = 'services',
        namespace: Optional[str] = kr8s.ALL,
        label_selector: Union[str, Dict] = None,
        field_selector: Union[str, Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> List['aobjects.Service']:
        ...

    @overload
    async def aget(
        self,
        name: Literal['deployments'] = 'deployments',
        namespace: Optional[str] = kr8s.ALL,
        label_selector: Union[str, Dict] = None,
        field_selector: Union[str, Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> List['aobjects.Deployment']:
        ...

    @overload
    async def aget(
        self,
        name: Literal['statefulsets'] = 'statefulsets',
        namespace: Optional[str] = kr8s.ALL,
        label_selector: Union[str, Dict] = None,
        field_selector: Union[str, Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> List['aobjects.StatefulSet']:
        ...

    @overload
    async def aget(
        self,
        name: Literal['configmaps'] = 'configmaps',
        namespace: Optional[str] = kr8s.ALL,
        label_selector: Union[str, Dict] = None,
        field_selector: Union[str, Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> List['aobjects.ConfigMap']:
        ...

    @overload
    async def aget(
        self,
        name: Literal['secrets'] = 'secrets',
        namespace: Optional[str] = kr8s.ALL,
        label_selector: Union[str, Dict] = None,
        field_selector: Union[str, Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> List['aobjects.Secret']:
        ...

    @overload
    async def aget(
        self,
        name: Literal['persistentvolumes'] = 'persistentvolumes',
        namespace: Optional[str] = kr8s.ALL,
        label_selector: Union[str, Dict] = None,
        field_selector: Union[str, Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> List['aobjects.PersistentVolume']:
        ...

    @overload
    async def aget(
        self,
        name: Literal['persistentvolumeclaims'] = 'persistentvolumeclaims',
        namespace: Optional[str] = kr8s.ALL,
        label_selector: Union[str, Dict] = None,
        field_selector: Union[str, Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> List['aobjects.PersistentVolumeClaim']:
        ...
    
    
    async def aget(
        self,
        name: str,
        *args,
        namespace: Optional[str] = kr8s.ALL,
        **kwargs,
    ) -> Union['aObjectT', 'aObjectListT']:
        """
        Get an object
        """
        await self.ainit()
        return await kr8s.asyncio.get(name, *args, namespace = namespace, api = self.aclient, **kwargs)
