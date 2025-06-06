from __future__ import annotations

"""
Kubernetes Context based on kr8s
"""
import os
import abc
import base64
import functools
import contextlib
import typing as t
from lzl import load

if load.TYPE_CHECKING:
    import kr8s
    import httpx
else:
    kr8s = load.LazyLoad("kr8s", install_missing=True)
    httpx = load.LazyLoad("httpx", install_missing=True)

if t.TYPE_CHECKING:
    from kr8s import Api as ClientAPI
    from kr8s.asyncio import Api as AsyncClientAPI
    from .types import objects, aobjects, ObjectT, ObjectListT, aObjectT, aObjectListT



class KubernetesContext(abc.ABC):
    """
    A Single Kubernetes Context
    """

    def __init__(
        self, 
        name: t.Optional[str] = None, 
        url: t.Optional[str] = None,
        kubeconfig: t.Optional[str] = None,
        service_account: t.Optional[str] = None,
        context: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        **kwargs
    ):
        self.name = name
        self.url = url
        self.kubeconfig = kubeconfig
        self.service_account = service_account
        self.context = context
        self.namespace = namespace
        self._client: t.Optional['ClientAPI'] = None
        self._aclient: t.Optional['AsyncClientAPI'] = None
        self._ainitialized: bool = False
        self._kwargs = kwargs
        self.objects: t.Dict[str, t.Union['objects.APIObject', 'aobjects.APIObject']] = {}

    @property
    def client(self) -> 'ClientAPI':
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
    def aclient(self) -> 'AsyncClientAPI':
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
    ) -> t.AsyncGenerator['httpx.Response', None]:
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
    def Pod(self) -> t.Type['objects.Pod']:
        """
        Returns the Pod object
        """
        if 'pod' not in self.objects:
            _pod = objects.Pod
            _pod.__init__ = functools.partialmethod(_pod.__init__, api = self.client)
            self.objects['pod'] = _pod
        return self.objects['pod']
    
    @property
    def aPod(self) -> t.Type['aobjects.Pod']:
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
    def Service(self) -> t.Type['objects.Service']:
        """
        Returns the Service object
        """
        if 'service' not in self.objects:
            _service = objects.Service
            _service.__init__ = functools.partialmethod(_service.__init__, api = self.client)
            self.objects['service'] = _service
        return self.objects['service']
    
    @property
    def aService(self) -> t.Type['aobjects.Service']:
        """
        Returns the async Service object
        """
        self.raise_if_not_ainit()
        if 'aservice' not in self.objects:
            _service = aobjects.Service
            _service.__init__ = functools.partialmethod(_service.__init__, api = self.aclient)
            self.objects['aservice'] = _service
        return self.objects['aservice']
    

    @t.overload
    def get(
        self,
        name: t.Literal['pods'] = 'pods',
        namespace: t.Optional[str] = 'all',
        label_selector: t.Union[str, t.Dict] = None,
        field_selector: t.Union[str, t.Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> t.Generator['objects.Pod']:
        ...

    @t.overload
    def get(
        self,
        name: t.Literal['services'] = 'services',
        namespace: t.Optional[str] = 'all',
        label_selector: t.Union[str, t.Dict] = None,
        field_selector: t.Union[str, t.Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> t.Generator['objects.Service']:
        ...


    def get(
        self,
        name: str,
        *args,
        namespace: t.Optional[str] = 'all',
        **kwargs,
    ) -> t.Generator[t.Union['ObjectT', 'ObjectListT']]:
        """
        Get an object
        """
        return kr8s.get(name, *args, namespace = namespace, api = self.client, **kwargs)


    @t.overload
    async def aget(
        self,
        name: t.Literal['pods'] = 'pods',
        namespace: t.Optional[str] = 'all',
        label_selector: t.Union[str, t.Dict] = None,
        field_selector: t.Union[str, t.Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> t.Generator['aobjects.Pod']:
        ...

    @t.overload
    async def aget(
        self,
        name: t.Literal['services'] = 'services',
        namespace: t.Optional[str] = 'all',
        label_selector: t.Union[str, t.Dict] = None,
        field_selector: t.Union[str, t.Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> t.AsyncGenerator['aobjects.Service']:
        ...

    @t.overload
    async def aget(
        self,
        name: t.Literal['deployments'] = 'deployments',
        namespace: t.Optional[str] = 'all',
        label_selector: t.Union[str, t.Dict] = None,
        field_selector: t.Union[str, t.Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> t.AsyncGenerator['aobjects.Deployment']:
        ...

    @t.overload
    async def aget(
        self,
        name: t.Literal['statefulsets'] = 'statefulsets',
        namespace: t.Optional[str] = 'all',
        label_selector: t.Union[str, t.Dict] = None,
        field_selector: t.Union[str, t.Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> t.AsyncGenerator['aobjects.StatefulSet']:
        ...

    @t.overload
    async def aget(
        self,
        name: t.Literal['configmaps'] = 'configmaps',
        namespace: t.Optional[str] = 'all',
        label_selector: t.Union[str, t.Dict] = None,
        field_selector: t.Union[str, t.Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> t.AsyncGenerator['aobjects.ConfigMap']:
        ...

    @t.overload
    async def aget(
        self,
        name: t.Literal['secrets'] = 'secrets',
        namespace: t.Optional[str] = 'all',
        label_selector: t.Union[str, t.Dict] = None,
        field_selector: t.Union[str, t.Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> t.AsyncGenerator['aobjects.Secret']:
        ...

    @t.overload
    async def aget(
        self,
        name: t.Literal['persistentvolumes'] = 'persistentvolumes',
        namespace: t.Optional[str] = 'all',
        label_selector: t.Union[str, t.Dict] = None,
        field_selector: t.Union[str, t.Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> t.AsyncGenerator['aobjects.PersistentVolume']:
        ...

    @t.overload
    async def aget(
        self,
        name: t.Literal['persistentvolumeclaims'] = 'persistentvolumeclaims',
        namespace: t.Optional[str] = 'all',
        label_selector: t.Union[str, t.Dict] = None,
        field_selector: t.Union[str, t.Dict] = None,
        as_object: object = None,
        **kwargs,
    ) -> t.AsyncGenerator['aobjects.PersistentVolumeClaim']:
        ...
    
    
    async def aget(
        self,
        name: str,
        *args,
        namespace: t.Optional[str] = 'all',
        **kwargs,
    ) -> t.AsyncGenerator['aObjectT', 'aObjectListT']:
        """
        Get an object
        """
        await self.ainit()
        async for obj in kr8s.asyncio.get(name, *args, namespace = namespace, api = self.aclient, **kwargs):
            yield obj

