from __future__ import annotations

import random
import asyncio
import logging
import contextlib
from enum import Enum
from lazyops.libs.kops.base import *
from lazyops.libs.kops.config import KOpsSettings
from lazyops.libs.kops.utils import cached, DillSerializer, SignalHandler
from lazyops.libs.kops._kopf import kopf
from lazyops.types import lazyproperty
from lazyops.utils import logger


from typing import List, Dict, Union, Any, Optional, Callable, TYPE_CHECKING

import lazyops.libs.kops.types as t
import lazyops.libs.kops.atypes as at

if TYPE_CHECKING:
    with contextlib.suppress(ImportError):
        import requests
        import aiohttpx


class EventType(str, Enum):
    startup = 'startup'
    shutdown = 'shutdown'


class KOpsContext:
    def __init__(
        self,
        settings: KOpsSettings,
        ctx: Optional[str] = None,
        name: Optional[str] = None,
        config_file: Optional[str] = None,

    ):
        self.settings = settings
        self.ctx = ctx
        self.name = name
        self.config_file = config_file
        self.ainitialized: bool = False
        self.initialized: bool = False

    async def aset_k8_config(self):
        if self.ainitialized: return
        if self.settings.in_k8s:
            logger.info('Loading in-cluster config')
            AsyncConfig.load_incluster_config()
        else:
            config = self.settings.get_kconfig_path(self.ctx or self.name)
            if config: config = config.as_posix()
            logger.info(f'Loading kubeconfig from {config}')
            await AsyncConfig.load_kube_config(config_file = config, context = self.ctx or self.name or self.settings.kubeconfig_context)
        logger.info('Initialized K8s Client')
        self.ainitialized = True
    
    def set_k8_config(self):
        if self.initialized: return
        if self.settings.in_k8s:
            logger.info('Loading in-cluster config')
            SyncConfig.load_incluster_config()
        else:
            config = self.settings.get_kconfig_path(self.ctx or self.name)
            if config: config = config.as_posix()
            logger.info(f'Loading kubeconfig from {config}')
            SyncConfig.load_kube_config(config_file = config, context = self.ctx or self.name or self.settings.kubeconfig_context)
        logger.info('Initialized K8s Client')
        self.initialized = True

    @lazyproperty
    def client(self) -> 'SyncClient.ApiClient':
        """
        Primary Sync Client
        """
        return SyncClient.ApiClient(pool_threads=4)

    @lazyproperty
    def aclient(self) -> 'AsyncClient.ApiClient':
        """
        Primary Async Client
        """
        return AsyncClient.ApiClient(pool_threads=4)
    
    @lazyproperty
    def wsclient(self) -> 'SyncStream.WSClient':
        """
        Primary Websocket Client
        """
        return SyncStream.WSClient(pool_threads=4)
    
    @lazyproperty
    def awsclient(self) -> 'AsyncStream.WsApiClient':
        """
        Primary Async Websocket Client
        """
        return AsyncStream.WsApiClient()
    
    @lazyproperty
    def core_v1(self) -> 'SyncClient.CoreV1Api':
        """
        - StatefulSets
        - Deployments
        - DaemonSets
        - ReplicaSets
        - Secrets
        - Pods
        - Nodes
        """
        return SyncClient.CoreV1Api(self.client)
    
    @lazyproperty
    def core_v1_ws(self) -> 'SyncClient.CoreV1Api':
        """
        Websocket Client

        - StatefulSets
        - Deployments
        - DaemonSets
        - ReplicaSets
        - Secrets
        - Pods
        - Nodes
        """
        return SyncClient.CoreV1Api(self.wsclient)
    

    @lazyproperty
    def apps_v1(self) -> 'SyncClient.AppsV1Api':
        """
        - StatefulSets
        - Deployments
        - DaemonSets
        - ReplicaSets
        """
        return SyncClient.AppsV1Api(self.client)

    @lazyproperty
    def networking_v1(self) -> 'SyncClient.NetworkingV1Api':
        """
        - Ingress
        """
        return SyncClient.NetworkingV1Api(self.client)
    

    @lazyproperty
    def crds(self) -> 'SyncClient.ApiextensionsV1Api':
        return SyncClient.ApiextensionsV1Api(self.client)

    
    @lazyproperty
    def customobjs(self) -> 'SyncClient.CustomObjectsApi':
        return SyncClient.CustomObjectsApi(self.client)

    """
    Async Properties
    """

    @lazyproperty
    def acore_v1(self) -> 'AsyncClient.CoreV1Api':
        """
        - StatefulSets
        - Deployments
        - DaemonSets
        - ReplicaSets
        - Secrets
        - Pods
        - Nodes
        """
        return AsyncClient.CoreV1Api(self.aclient)
    

    @lazyproperty
    def acore_v1_ws(self) -> 'AsyncClient.CoreV1Api':
        """
        Websocket Client

        - StatefulSets
        - Deployments
        - DaemonSets
        - ReplicaSets
        - Secrets
        - Pods
        - Nodes
        """
        return AsyncClient.CoreV1Api(self.awsclient)
    

    @lazyproperty
    def aapps_v1(self) -> 'AsyncClient.AppsV1Api':
        """
        - StatefulSets
        - Deployments
        - DaemonSets
        - ReplicaSets
        """
        return AsyncClient.AppsV1Api(self.aclient)

    @lazyproperty
    def anetworking_v1(self) -> 'AsyncClient.NetworkingV1Api':
        """
        - Ingress
        """
        return AsyncClient.NetworkingV1Api(self.aclient)
    

    @lazyproperty
    def acrds(self) -> 'AsyncClient.ApiextensionsV1Api':
        return AsyncClient.ApiextensionsV1Api(self.aclient)

    
    @lazyproperty
    def acustomobjs(self) -> 'AsyncClient.CustomObjectsApi':
        return AsyncClient.CustomObjectsApi(self.aclient)
    


    """
    Sync Resource Level
    """
    @lazyproperty
    def config_maps(self) -> 'SyncClient.CoreV1Api':
        return self.core_v1
    
    @lazyproperty
    def secrets(self) -> 'SyncClient.CoreV1Api':
        return self.core_v1
    
    @lazyproperty
    def pods(self) -> 'SyncClient.CoreV1Api':
        return self.core_v1
    
    @lazyproperty
    def nodes(self) -> 'SyncClient.CoreV1Api':
        return self.core_v1
    
    @lazyproperty
    def services(self) -> 'SyncClient.CoreV1Api':
        return self.core_v1
    
    @lazyproperty
    def ingresses(self) -> 'SyncClient.NetworkingV1Api':
        return self.networking_v1
    
    @lazyproperty
    def stateful_sets(self) -> 'SyncClient.AppsV1Api':
        return self.apps_v1
    
    @lazyproperty
    def deployments(self) -> 'SyncClient.AppsV1Api':
        return self.apps_v1
    
    @lazyproperty
    def daemon_sets(self) -> 'SyncClient.AppsV1Api':
        return self.apps_v1
    
    @lazyproperty
    def replica_sets(self) -> 'SyncClient.AppsV1Api':
        return self.apps_v1
    
    @lazyproperty
    def customresourcedefinitions(self) -> 'SyncClient.ApiextensionsV1Api':
        return self.crds
    
    @lazyproperty
    def customobjects(self) -> 'SyncClient.CustomObjectsApi':
        return self.customobjs
    
    @lazyproperty
    def persistent_volumes(self) -> 'SyncClient.CoreV1Api':
        return self.core_v1
    
    @lazyproperty
    def persistent_volume_claims(self) -> 'SyncClient.CoreV1Api':
        return self.core_v1
    
    """
    Async Resource Level
    """

    @lazyproperty
    def aconfig_maps(self) -> 'AsyncClient.CoreV1Api':
        return self.acore_v1
    
    @lazyproperty
    def asecrets(self) -> 'AsyncClient.CoreV1Api':
        return self.acore_v1
    
    @lazyproperty
    def apods(self) -> 'AsyncClient.CoreV1Api':
        return self.acore_v1
    
    @lazyproperty
    def anodes(self) -> 'AsyncClient.CoreV1Api':
        return self.acore_v1
    
    @lazyproperty
    def aservices(self) -> 'AsyncClient.CoreV1Api':
        return self.acore_v1
    
    @lazyproperty
    def aingresses(self) -> 'AsyncClient.NetworkingV1Api':
        return self.anetworking_v1
    
    @lazyproperty
    def astateful_sets(self) -> 'AsyncClient.AppsV1Api':
        return self.aapps_v1
    
    @lazyproperty
    def adeployments(self) -> 'AsyncClient.AppsV1Api':
        return self.aapps_v1
    
    @lazyproperty
    def adaemon_sets(self) -> 'AsyncClient.AppsV1Api':
        return self.aapps_v1
    
    @lazyproperty
    def areplica_sets(self) -> 'AsyncClient.AppsV1Api':
        return self.aapps_v1
    
    @lazyproperty
    def acustomresourcedefinitions(self) -> 'AsyncClient.ApiextensionsV1Api':
        return self.acrds
    
    @lazyproperty
    def acustomobjects(self) -> 'AsyncClient.CustomObjectsApi':
        return self.acustomobjs
    
    @lazyproperty
    def apersistent_volumes(self) -> 'AsyncClient.CoreV1Api':
        return self.acore_v1
    
    @lazyproperty
    def apersistent_volume_claims(self) -> 'AsyncClient.CoreV1Api':
        return self.acore_v1
    
    @property
    def auth_headers(self) -> Dict[str, str]:
        if not self.initialized and not self.ainitialized: return None
        auth = self.aclient.configuration.auth_settings() if self.ainitialized \
            else self.client.configuration.auth_settings()
        return {auth['BearerToken']['key']: auth['BearerToken']['value']}

    @property
    def request_headers(self) -> Dict[str, str]:
        if not self.initialized and not self.ainitialized: return None
        headers = self.aclient.default_headers if self.ainitialized \
            else self.client.default_headers
        # logger.info(f"Request Headers: {headers}")
        return {
            'Accept': 'application/json;as=Table;v=v1;g=meta.k8s.io,application/json;as=Table;v=v1beta1;g=meta.k8s.io,application/json',
            'Connection': 'keep-alive',
            # 'Keep-alive': 'max=10, timeout=1200',
            **self.auth_headers,
            **headers
        }
    
    @property
    def cluster_url(self) -> str:
        if self.initialized or self.ainitialized:
            return self.aclient.configuration.host if self.ainitialized \
                    else self.client.configuration.host
        else: return None

    @property
    def ssl_ca_cert(self) -> str:
        if self.initialized or self.ainitialized:
            return self.aclient.configuration.ssl_ca_cert if self.ainitialized \
                    else self.client.configuration.ssl_ca_cert
        else: return None

    @lazyproperty
    def http_client(self) -> Union['aiohttpx.Client', 'requests.Session']:
        """
        Returns the http client
        """
        with contextlib.suppress(ImportError):
            import aiohttpx
            return aiohttpx.Client(
                base_url = self.cluster_url,
                headers = self.request_headers, 
                verify = self.ssl_ca_cert,
            )
        with contextlib.suppress(ImportError):
            import requests
            sess = requests.Session()
            sess.headers.update(self.request_headers)
            sess.verify = self.ssl_ca_cert
            return sess
        raise ImportError('No http client found. Please install aiohttpx or requests')


    @staticmethod
    def to_singular(resource: str) -> str:
        if resource.endswith('es'):
            return resource[:-2]
        elif resource.endswith('s'):
            return resource[:-1]
        return resource


    """
    API Methods
    """


    def get(self, resource: str, name: str, namespace: str = None, **kwargs) -> 'SyncClient.V1ObjectMeta':
        api = getattr(self, resource)
        singular = self.to_singular(resource)
        return getattr(api, f'read_namespaced_{singular}')(name, namespace = namespace, **kwargs)
    
    def list(self, resource: str, namespace: str = None, **kwargs) -> 'SyncClient.V1ObjectMeta':
        api = getattr(self, resource)
        singular = self.to_singular(resource)
        if namespace:
            return getattr(api, f'list_namespaced_{singular}')(namespace = namespace, **kwargs)
        return getattr(api, f'list_{singular}_for_all_namespaces')(**kwargs)
    
    def create(self, resource: str, namespace: str = None, **kwargs) -> 'SyncClient.V1ObjectMeta':
        api = getattr(self, resource)
        singular = self.to_singular(resource)
        return getattr(api, f'create_namespaced_{singular}')(namespace = namespace, **kwargs)
    
    def update(self, resource: str, name: str, namespace: str = None, **kwargs) -> 'SyncClient.V1ObjectMeta':
        api = getattr(self, resource)
        singular = self.to_singular(resource)
        return getattr(api, f'patch_namespaced_{singular}')(name, namespace = namespace, **kwargs)
    
    def delete(self, resource: str, name: str, namespace: str = None, **kwargs) -> 'SyncClient.V1ObjectMeta':
        api = getattr(self, resource)
        singular = self.to_singular(resource)
        return getattr(api, f'delete_namespaced_{singular}')(name, namespace = namespace, **kwargs)
    
    def patch(self, resource: str, name: str, namespace: str = None, **kwargs) -> 'SyncClient.V1ObjectMeta':
        api = getattr(self, resource)
        singular = self.to_singular(resource)
        return getattr(api, f'patch_namespaced_{singular}')(name, namespace = namespace, **kwargs)


    async def aget(self, resource: str, name: str, namespace: str = None, **kwargs) -> 'AsyncClient.V1ObjectMeta':
        aresource = resource if resource.startswith('a') else f'a{resource}'
        api = getattr(self, aresource)
        singular = self.to_singular(resource)
        return await getattr(api, f'read_namespaced_{singular}')(name, namespace = namespace, **kwargs)
    
    async def alist(self, resource: str, namespace: str = None, **kwargs) -> 'AsyncClient.V1ObjectMeta':
        aresource = resource if resource.startswith('a') else f'a{resource}'
        api = getattr(self, aresource)
        singular = self.to_singular(resource)
        if namespace:
            return await getattr(api, f'list_namespaced_{singular}')(namespace = namespace, **kwargs)
        return await getattr(api, f'list_{singular}_for_all_namespaces')(**kwargs)
    
    async def acreate(self, resource: str, namespace: str = None, **kwargs) -> 'AsyncClient.V1ObjectMeta':
        aresource = resource if resource.startswith('a') else f'a{resource}'
        api = getattr(self, aresource)
        singular = self.to_singular(resource)
        return await getattr(api, f'create_namespaced_{singular}')(namespace = namespace, **kwargs)
    
    async def aupdate(self, resource: str, name: str, namespace: str = None, **kwargs) -> 'AsyncClient.V1ObjectMeta':
        aresource = resource if resource.startswith('a') else f'a{resource}'
        api = getattr(self, aresource)
        singular = self.to_singular(resource)
        return await getattr(api, f'patch_namespaced_{singular}')(name, namespace = namespace, **kwargs)
    
    async def adelete(self, resource: str, name: str, namespace: str = None, **kwargs) -> 'AsyncClient.V1ObjectMeta':
        aresource = resource if resource.startswith('a') else f'a{resource}'
        api = getattr(self, aresource)
        singular = self.to_singular(resource)
        return await getattr(api, f'delete_namespaced_{singular}')(name, namespace = namespace, **kwargs)
    
    async def apatch(self, resource: str, name: str, namespace: str = None, **kwargs) -> 'AsyncClient.V1ObjectMeta':
        aresource = resource if resource.startswith('a') else f'a{resource}'
        api = getattr(self, aresource)
        singular = self.to_singular(resource)
        return await getattr(api, f'patch_namespaced_{singular}')(name, namespace = namespace, **kwargs)




class KOpsClientMeta(type):
    """
    This is the metaclass for the KOpsClient class.
    """

    ctx: Optional[str] = None
    _settings: Optional[KOpsSettings] = None
    _session: Optional[KOpsContext] = None
    _sessions: Dict[str, KOpsContext] = {}
    _startup_functions: List[Callable] = []
    _shutdown_functions: List[Callable] = []

    @property
    def settings(cls) -> KOpsSettings:
        if not cls._settings:
            cls._settings = KOpsSettings()
        return cls._settings
    
    def add_session(
        cls,
        name: Optional[str] = None, 
        config_file: Optional[str] = None, 
        ctx: Optional[Any] = None, 
        set_as_current: Optional[bool] = True, 
        **kwargs
    ):
        """
        Adds a session to the client.
        """
        name = name or 'default'
        if name not in cls._sessions:
            cls._sessions[name] = KOpsContext(
                settings = cls.settings,
                config_file = config_file,
                ctx = ctx,
                **kwargs
            )
            logger.info(f'Session created: {name}')
        if set_as_current:
            cls.ctx = name
            cls._session = cls._sessions[name]
            logger.info(f'Session set: {name}')
    
    def set_session(
        cls,
        name: Optional[str] = None,
    ):
        """
        Sets the current session.
        """
        name = name or 'default'
        if name in cls._sessions:
            cls.ctx = name
            cls._session = cls._sessions[name]
            logger.info(f'Session set: {name}')

    @property
    def session(cls) -> KOpsContext:
        if not cls._session:
            cls._session = KOpsContext(
                settings = cls.settings,
                ctx = cls.ctx
            )
            if cls.ctx is None: cls.ctx = 'default'
            cls._sessions[cls.ctx] = cls._session
            logger.info(f'Session set: {cls.ctx}')
        return cls._session

    @property
    def client(cls) -> 'SyncClient.ApiClient':
        """
        Returns the kubernetes client.
        """
        return cls.session.client

    @property
    def aclient(cls) -> 'AsyncClient.ApiClient':
        """
        Returns the async kubernetes client.
        """
        return cls.session.aclient
    
    """
    HTTP Client Properties
    """

    @property
    def auth_headers(cls) -> Dict[str, str]:
        """
        Returns the authentication headers.
        """
        return cls.session.auth_headers
    
    @property
    def request_headers(cls) -> Dict[str, str]:
        """
        Returns the request headers.
        """
        return cls.session.request_headers
    
    @property
    def cluster_url(cls) -> str:
        """
        Returns the cluster url.
        """
        return cls.session.cluster_url
    
    @property
    def ssl_ca_cert(cls) -> str:
        """
        Returns the ssl ca cert.
        """
        return cls.session.ssl_ca_cert
    
    @property
    def http_client(cls) -> Union['aiohttpx.Client', 'requests.Session']:
        """
        Returns the http client.
        """
        return cls.session.http_client

    @property
    def wsclient(cls) -> 'SyncStream.WSClient':
        """
        Returns the websocket kubernetes client.
        """
        return cls.session.wsclient
    
    @property
    def awsclient(cls) -> 'AsyncStream.WsApiClient':
        """
        Returns the async websocket kubernetes client.
        """
        return cls.session.awsclient
    
    
    @property
    def apps_v1(cls) -> 'SyncClient.AppsV1Api':
        """
        Returns the apps_v1 api.
        """
        return cls.session.apps_v1

    @property
    def core_v1(cls) -> 'SyncClient.CoreV1Api':
        """
        Returns the core_v1 api.
        """
        return cls.session.core_v1
    
    @property
    def core_v1_ws(cls) -> 'SyncClient.CoreV1Api':
        """
        Websocket Client:
        - StatefulSets
        - Deployments
        - DaemonSets
        - ReplicaSets
        - Secrets
        - Pods
        - Nodes
        """
        return cls.session.core_v1_ws
    
    @property
    def crds(cls) -> 'SyncClient.CustomObjectsApi':
        """
        Returns the crds_v1 api.
        """
        return cls.session.crds

    
    @property
    def customobjs(cls) -> 'SyncClient.CustomObjectsApi':
        return cls.session.customobjs
    

    """
    Async Properties
    """

    @property
    def acore_v1(cls) -> 'AsyncClient.CoreV1Api':
        """
        - StatefulSets
        - Deployments
        - DaemonSets
        - ReplicaSets
        - Secrets
        - Pods
        - Nodes
        """
        return cls.session.acore_v1
    
    @property
    def acore_v1_ws(cls) -> 'AsyncClient.CoreV1Api':
        """
        Websocket Client:
        - StatefulSets
        - Deployments
        - DaemonSets
        - ReplicaSets
        - Secrets
        - Pods
        - Nodes
        """
        return cls.session.acore_v1_ws
    

    @property
    def aapps_v1(cls) -> 'AsyncClient.AppsV1Api':
        """
        - StatefulSets
        - Deployments
        - DaemonSets
        - ReplicaSets
        """
        return cls.session.aapps_v1

    @property
    def anetworking_v1(cls) -> 'AsyncClient.NetworkingV1Api':
        """
        - Ingress
        """
        return cls.session.anetworking_v1
    

    @property
    def acrds(cls) -> 'AsyncClient.ApiextensionsV1Api':
        return cls.session.acrds

    
    @property
    def acustomobjs(cls) -> 'AsyncClient.CustomObjectsApi':
        return cls.session.acustomobjs
    


    """
    Sync Resource Level
    """
    @property
    def config_maps(cls) -> 'SyncClient.CoreV1Api':
        return cls.session.config_maps
    
    @property
    def secrets(cls) -> 'SyncClient.CoreV1Api':
        return cls.session.secrets
    
    @property
    def pods(cls) -> 'SyncClient.CoreV1Api':
        return cls.session.pods
    
    @property
    def nodes(cls) -> 'SyncClient.CoreV1Api':
        return cls.session.nodes
    
    @property
    def services(cls) -> 'SyncClient.CoreV1Api':
        return cls.session.services
    
    @property
    def ingresses(cls) -> 'SyncClient.NetworkingV1Api':
        return cls.session.ingresses
    
    @property
    def stateful_sets(cls) -> 'SyncClient.AppsV1Api':
        return  cls.session.stateful_sets
    
    @property
    def deployments(cls) -> 'SyncClient.AppsV1Api':
        return cls.session.deployments
    
    @property
    def daemon_sets(cls) -> 'SyncClient.AppsV1Api':
        return cls.session.daemon_sets
    
    @property
    def replica_sets(cls) -> 'SyncClient.AppsV1Api':
        return cls.session.replica_sets
    
    @property
    def customresourcedefinitions(cls) -> 'SyncClient.ApiextensionsV1Api':
        return cls.session.customresourcedefinitions
    
    @property
    def customobjects(cls) -> 'SyncClient.CustomObjectsApi':
        return cls.session.customobjects
    
    @property
    def persistent_volumes(cls) -> 'SyncClient.CoreV1Api':
        return cls.session.persistent_volumes
    
    @property
    def persistent_volume_claims(cls) -> 'SyncClient.CoreV1Api':
        return cls.session.persistent_volume_claims
    
    """
    Async Resource Level
    """

    @property
    def aconfig_maps(cls) -> 'AsyncClient.CoreV1Api':
        return cls.session.aconfig_maps
    
    @property
    def asecrets(cls) -> 'AsyncClient.CoreV1Api':
        return cls.session.asecrets
    
    @property
    def apods(cls) -> 'AsyncClient.CoreV1Api':
        return cls.session.apods
    
    @property
    def anodes(cls) -> 'AsyncClient.CoreV1Api':
        return cls.session.anodes
    
    @property
    def aservices(cls) -> 'AsyncClient.CoreV1Api':
        return cls.session.aservices
    
    @property
    def aingresses(cls) -> 'AsyncClient.NetworkingV1Api':
        return cls.session.aingresses
    
    @property
    def astateful_sets(cls) -> 'AsyncClient.AppsV1Api':
        return cls.session.astateful_sets
    
    @property
    def adeployments(cls) -> 'AsyncClient.AppsV1Api':
        return cls.session.adeployments
    
    @property
    def adaemon_sets(cls) -> 'AsyncClient.AppsV1Api':
        return cls.session.adaemon_sets
    
    @property
    def areplica_sets(cls) -> 'AsyncClient.AppsV1Api':
        return cls.session.areplica_sets
    
    @property
    def acustomresourcedefinitions(cls) -> 'AsyncClient.ApiextensionsV1Api':
        return cls.session.acustomresourcedefinitions
    
    @property
    def acustomobjects(cls) -> 'AsyncClient.CustomObjectsApi':
        return cls.session.acustomobjects
    
    @property
    def apersistent_volumes(cls) -> 'AsyncClient.CoreV1Api':
        return cls.session.apersistent_volumes
    
    @property
    def apersistent_volume_claims(cls) -> 'AsyncClient.CoreV1Api':
        return cls.session.apersistent_volume_claims

    async def aconfigure(cls):
        """
        Sets the kubernetes config for the current context.
        """
        await cls.session.aset_k8_config()

    async def aset_k8_config(cls):
        """
        Sets the kubernetes config for the current context.
        """
        await cls.session.aset_k8_config()
    
    def configure(cls):
        """
        Sets the kubernetes config for the current context.
        """
        cls.session.set_k8_config()

    def set_k8_config(cls):
        """
        Sets the kubernetes config for the current context.
        """
        cls.session.set_k8_config()

    
    def get(cls, resource: str, name: str, namespace: str = None, **kwargs) -> 'SyncClient.V1ObjectMeta':
        """
        Gets a resource.
        """
        return cls.session.get(resource, name, namespace, **kwargs)
    
    
    def list(cls, resource: str, namespace: str = None, **kwargs) -> 'SyncClient.V1ObjectMeta':
        """
        Lists a resource.
        """
        return cls.session.list(resource, namespace, **kwargs)
    
    def create(cls, resource: str, namespace: str = None, **kwargs) -> 'SyncClient.V1ObjectMeta':
        """
        Creates a resource.
        """
        return cls.session.create(resource, namespace, **kwargs)
        
    def update(cls, resource: str, name: str, namespace: str = None, **kwargs) -> 'SyncClient.V1ObjectMeta':
        """
        Updates a resource.
        """
        return cls.session.update(resource, name, namespace, **kwargs)
    
    def delete(cls, resource: str, name: str, namespace: str = None, **kwargs) -> 'SyncClient.V1ObjectMeta':
        """
        Deletes a resource.
        """
        return cls.session.delete(resource, name, namespace, **kwargs)
    
    def patch(cls, resource: str, name: str, namespace: str = None, **kwargs) -> 'SyncClient.V1ObjectMeta':
        """
        Patches a resource.
        """
        return cls.session.patch(resource, name, namespace, **kwargs)


    async def aget(cls, resource: str, name: str, namespace: str = None, **kwargs) -> 'AsyncClient.V1ObjectMeta':
        """
        Gets a resource.
        """
        return await cls.session.aget(resource, name, namespace, **kwargs)

    
    async def alist(cls, resource: str, namespace: str = None, **kwargs) -> 'AsyncClient.V1ObjectMeta':
        """
        Lists a resource.
        """
        return await cls.session.alist(resource, namespace, **kwargs)
    
    async def acreate(cls, resource: str, namespace: str = None, **kwargs) -> 'AsyncClient.V1ObjectMeta':
        """
        Creates a resource.
        """
        return await cls.session.acreate(resource, namespace, **kwargs)
    
    async def aupdate(cls, resource: str, name: str, namespace: str = None, **kwargs) -> 'AsyncClient.V1ObjectMeta':
        """
        Updates a resource.
        """
        return await cls.session.aupdate(resource, name, namespace, **kwargs)
    
    async def adelete(cls, resource: str, name: str, namespace: str = None, **kwargs) -> 'AsyncClient.V1ObjectMeta':
        """
        Deletes a resource.
        """
        return await cls.session.adelete(resource, name, namespace, **kwargs)
    
    async def apatch(cls, resource: str, name: str, namespace: str = None, **kwargs) -> 'AsyncClient.V1ObjectMeta':
        """
        Patches a resource.
        """
        return await cls.session.apatch(resource, name, namespace, **kwargs)

    """
    KOpf Methods
    """

    def add_function(cls, function: Callable, event: EventType = EventType.startup):
        if event == EventType.startup:
            cls._startup_functions.append(function)
        elif event == EventType.shutdown:
            cls._shutdown_functions.append(function)
    
    async def run_startup_functions(cls, **kwargs):
        # Start Signal Watcher
        asyncio.create_task(SignalHandler.monitor(cls._shutdown_functions))

        if not cls._startup_functions: return
        for func in cls._startup_functions:
            await func(**kwargs)

    async def run_shutdown_functions(cls, **kwargs):
        if not cls._shutdown_functions: return
        for func in cls._shutdown_functions:
            await func(**kwargs)
    

    # Register Startup Functions
    def configure_kopf(
        cls, 
        _logger: logging.Logger = None,
        _settings: Optional[kopf.OperatorSettings] = None,
        enable_event_logging: Optional[bool] = None,
        event_logging_level: Optional[str] = None,
        finalizer: Optional[str] = None,
        storage_prefix: Optional[str] = None,
        persistent_key: Optional[str] = None,
        error_delays: Optional[List[int]] = None,
        startup_functions: Optional[List[Callable]] = None,
        shutdown_functions: Optional[List[Callable]] = None,
        kopf_name: Optional[str] = None,
        app_name: Optional[str] = None,
        multi_pods: Optional[bool] = True,
        **kwargs
    ):
        """
        Registers the startup function for configuring kopf.

        Parameters
        """ 
        enable_event_logging = enable_event_logging if enable_event_logging is not None \
            else cls.settings.kopf_enable_event_logging
        event_logging_level = event_logging_level if event_logging_level is not None \
            else cls.settings.kopf_event_logging_level
        finalizer = finalizer if finalizer is not None \
            else cls.settings.kops_finalizer
        
        if finalizer != cls.settings.kops_finalizer:
            cls.settings.kops_finalizer = finalizer
        
        storage_prefix = storage_prefix if storage_prefix is not None \
            else cls.settings.kops_prefix
        persistent_key = persistent_key if persistent_key is not None \
            else cls.settings.kops_persistent_key
        
        if persistent_key != cls.settings.kops_persistent_key:
            cls.settings.kops_persistent_key = persistent_key
        
        error_delays = error_delays if error_delays is not None \
            else [10, 20, 30]
        kopf_name = kopf_name if kopf_name is not None \
            else cls.settings.kopf_name
        app_name = app_name if app_name is not None \
            else cls.settings.app_name
        
        _logger = _logger if _logger is not None \
            else logger
        
        if startup_functions is not None:
            for func in startup_functions:
                cls.add_function(func, EventType.startup)
        
        if shutdown_functions is not None:
            for func in shutdown_functions:
                cls.add_function(func, EventType.shutdown)

        
        # @kopf.on.startup()
        # async def configure(settings: kopf.OperatorSettings, logger: logging.Logger, **kwargs):
        
        @kopf.on.startup()
        async def configure(settings: kopf.OperatorSettings, **kwargs):
            if _settings is not None:
                settings = _settings
            if enable_event_logging is False:
                settings.posting.enabled = enable_event_logging
                _logger.info(f'Kopf Events Enabled: {enable_event_logging}')
            if event_logging_level is not None:
                # elif enable_event_logging is True:
                settings.posting.level = logging.getLevelName(event_logging_level.upper())
                _logger.info(f'Kopf Events Logging Level: {event_logging_level}')

            settings.persistence.finalizer = finalizer
            settings.persistence.progress_storage = kopf.SmartProgressStorage(prefix = storage_prefix)
            settings.persistence.diffbase_storage = kopf.AnnotationsDiffBaseStorage(
                prefix = storage_prefix,
                key = persistent_key,
            )
            settings.batching.error_delays = error_delays
            if multi_pods:
                settings.peering.priority = random.randint(0, 32767)
                settings.peering.stealth = True
                if kwargs.get('peering_name'):
                    settings.peering.name = kwargs.get('peering_name')

            # if cls.settings.kopf_enable_event_logging is False:
            #     settings.posting.enabled = cls.settings.kopf_enable_event_logging
            #     logger.info(f'Kopf Events Enabled: {cls.settings.kopf_enable_event_logging}')
            # elif cls.settings.kopf_enable_event_logging is True:
            #     settings.posting.level = logging.getLevelName(cls.settings.kopf_event_logging_level.upper())
            #     logger.info(f'Kopf Events Logging Level: {cls.settings.kopf_enable_event_logging}')

            # settings.persistence.finalizer = cls.settings.kops_finalizer
            # settings.persistence.progress_storage = kopf.SmartProgressStorage(prefix = cls.settings.kops_prefix)
            # settings.persistence.diffbase_storage = kopf.AnnotationsDiffBaseStorage(
            #     prefix = cls.settings.kops_prefix,
            #     key = cls.settings.kops_persistent_key,
            # )
            # settings.batching.error_delays = [10, 20, 30]

            _logger.info(f'Starting Kopf: {kopf_name} {app_name} @ {cls.settings.build_id}')
            await cls.aset_k8_config()
            if cls._startup_functions:
                _logger.info('Running Startup Functions')
                await cls.run_startup_functions()
            _logger.info('Completed Kopf Startup')

        @kopf.on.login()
        async def login_fn(**kwargs):
            return (
                kopf.login_with_service_account(**kwargs)
                or kopf.login_with_kubeconfig(**kwargs)
                if cls.settings.in_k8s
                else kopf.login_via_client(**kwargs)
            )
        

class BaseKOpsClient(metaclass = KOpsClientMeta):
    """
    Provides a base client for interacting with Kubernetes.
    """
    pass


"""
Cached Methods for Efficient Retrieval
"""

def get_namespaces(**kwargs) -> List[t.V1Namespace]:
    namespaces: t.V1NamespaceList = BaseKOpsClient.core_v1.list_namespace(**kwargs)
    return list(namespaces.items)

@cached(ttl = 5, serializer = DillSerializer)
async def aget_namespaces(**kwargs) -> List[at.V1Namespace]:
    namespaces: at.V1NamespaceList = await BaseKOpsClient.acore_v1.list_namespace(**kwargs)
    return list(namespaces.items)


"""
Nodes
"""

# @cached(ttl = 60, serializer = DillSerializer)
def get_node_name(name: Optional[str] = None, host_ip: Optional[str] = None, **kwargs) -> str:
    # not sure how this would work with diff clusters
    assert name or host_ip, 'Must provide either name or host_ip'
    if host_ip: name = 'ip-' + host_ip.replace('.', '-') + '.ec2.internal'
    return name

def get_nodes(**kwargs) -> List[t.V1Node]:
    nodes: t.V1NodeList = BaseKOpsClient.core_v1.list_node(**kwargs)
    return list(nodes.items)

@cached(ttl = 5, serializer = DillSerializer)
async def aget_nodes(**kwargs) -> List[at.V1Node]:
    nodes: at.V1NodeList = await BaseKOpsClient.acore_v1.list_node(**kwargs)
    return list(nodes.items)


def get_node(name: Optional[str] = None, host_ip: Optional[str] = None, **kwargs) -> t.V1Node:
    name = get_node_name(name = name, host_ip = host_ip)
    return BaseKOpsClient.core_v1.read_node(name = name, **kwargs)

@cached(ttl = 5, serializer = DillSerializer)
async def aget_node(name: Optional[str] = None, host_ip: Optional[str] = None, **kwargs) -> at.V1Node:
    name = get_node_name(name = name, host_ip = host_ip)
    return await BaseKOpsClient.acore_v1.read_node(name = name, **kwargs)


"""
Pods
"""
def get_pods(namespace: Optional[str] = None, **kwargs) -> List[t.V1Pod]:
    pods: t.V1PodList = BaseKOpsClient.core_v1.list_pod_for_all_namespaces(**kwargs)
    pods = list(pods.items)
    if namespace: pods = [pod for pod in pods if pod.metadata.namespace == namespace]
    return pods

@cached(ttl = 5, serializer = DillSerializer)
async def aget_pods(namespace: Optional[str] = None, **kwargs) -> List[at.V1Pod]:
    pods: at.V1PodList = await BaseKOpsClient.acore_v1.list_pod_for_all_namespaces(**kwargs)
    pods = list(pods.items)
    if namespace: pods = [pod for pod in pods if pod.metadata.namespace == namespace]
    return pods


def get_pod(name: str, namespace: Optional[str] = None, **kwargs) -> t.V1Pod:
    if name and namespace:
        return BaseKOpsClient.core_v1.read_namespaced_pod(name = name, namespace = namespace, **kwargs)
    pods = get_pods(namespace = namespace, **kwargs)
    for pod in pods:
        if pod.metadata.name == name:
            return pod
    raise ValueError(f'Pod {name} not found')

@cached(ttl = 5, serializer = DillSerializer)
async def aget_pod(name: str, namespace: Optional[str] = None, **kwargs) -> at.V1Pod:
    if name and namespace:
        return await BaseKOpsClient.acore_v1.read_namespaced_pod(name = name, namespace = namespace, **kwargs)
    pods = await aget_pods(namespace = namespace, **kwargs)
    for pod in pods:
        if pod.metadata.name == name:
            return pod
    raise ValueError(f'Pod {name} not found')


@cached(ttl = 5, serializer = DillSerializer)
async def aget_pods_on_node(name: str, host_ip: Optional[str] = None, namespace: Optional[str] = None, **kwargs) -> List[at.V1Pod]:
    pods = await aget_pods(namespace = namespace, **kwargs)
    host_ip = get_node_name(name = name, host_ip = host_ip)
    return [pod for pod in pods if pod.status.host_ip and pod.status.host_ip == host_ip]

@cached(ttl = 5, serializer = DillSerializer)
async def aget_claimnames_from_pods_on_node(name: str, host_ip: Optional[str] = None, namespace: Optional[str] = None, **kwargs) -> List[str]:
    """
    Returns a list of PVC names from pods on a node
    """
    pods = await aget_pods_on_node(name = name, host_ip = host_ip, namespace = namespace, **kwargs)
    claim_names = []
    for pod in pods:
        claim_names.extend(
            volume.persistent_volume_claim.claim_name
            for volume in pod.spec.volumes
            if volume.persistent_volume_claim
        )
    return claim_names


def run_pod_command(
    name: str, 
    namespace: str,
    command: Union[str, List[str]],
    container: Optional[str] = None,
    stderr: Optional[bool] = True,
    stdin: Optional[bool] = True,
    stdout: Optional[bool] = True,
    tty: Optional[bool] = False,
    ignore_error: bool = True, 
    **kwargs
) -> str:
    """
    Runs a command in the pod and returns the command
    name = 'name_example' # str | name of the PodExecOptions
    namespace = 'namespace_example' # str | object name and auth scope, such as for teams and projects
    command = 'command_example' # str | Command is the remote command to execute. argv array. Not executed within a shell. (optional)
    container = 'container_example' # str | Container in which to execute the command. Defaults to only container if there is only one container in the pod. (optional)
    stderr = True # bool | Redirect the standard error stream of the pod for this call. (optional)
    stdin = True # bool | Redirect the standard input stream of the pod for this call. Defaults to false. (optional)
    stdout = True # bool | Redirect the standard output stream of the pod for this call. (optional)
    tty = True # bool | TTY if true indicates that a tty will be allocated for the exec call. Defaults to false. (optional)

    """
    if isinstance(command, str):
        command = command.split(' ')
    try:
        return BaseKOpsClient.core_v1_ws.connect_post_namespaced_pod_exec(
            name = name, 
            namespace = namespace, 
            command = command,
            container = container,
            stderr = stderr,
            stdin = stdin,
            stdout = stdout,
            tty = tty
        )
    except Exception as e:
        if not ignore_error:
            logger.warning(f'[{namespace}/{name}] Exec Status Failed: {e}')
        return None

async def arun_pod_command(
    name: str, 
    namespace: str,
    command: Union[str, List[str]],
    container: Optional[str] = None,
    stderr: Optional[bool] = True,
    stdin: Optional[bool] = True,
    stdout: Optional[bool] = True,
    tty: Optional[bool] = False,
    ignore_error: bool = True, 
    **kwargs
) -> str:
    """
    Runs a command in the pod and returns the command
    name = 'name_example' # str | name of the PodExecOptions
    namespace = 'namespace_example' # str | object name and auth scope, such as for teams and projects
    command = 'command_example' # str | Command is the remote command to execute. argv array. Not executed within a shell. (optional)
    container = 'container_example' # str | Container in which to execute the command. Defaults to only container if there is only one container in the pod. (optional)
    stderr = True # bool | Redirect the standard error stream of the pod for this call. (optional)
    stdin = True # bool | Redirect the standard input stream of the pod for this call. Defaults to false. (optional)
    stdout = True # bool | Redirect the standard output stream of the pod for this call. (optional)
    tty = True # bool | TTY if true indicates that a tty will be allocated for the exec call. Defaults to false. (optional)

    """
    if isinstance(command, str):
        command = command.split(' ')
    
    try:
        return await BaseKOpsClient.acore_v1_ws.connect_post_namespaced_pod_exec(
            name = name, 
            namespace = namespace, 
            command = command,
            container = container,
            stderr = stderr,
            stdin = stdin,
            stdout = stdout,
            tty = tty
        )
    except Exception as e:
        if not ignore_error:
            logger.warning(f'[{namespace}/{name}] Exec Status Failed: {e}')
        return None

"""
PVCs
"""

@cached(ttl = 5, serializer = DillSerializer)
async def aget_pvcs(namespace: Optional[str] = None, **kwargs) -> List[at.V1PersistentVolumeClaim]:
    pvcs: at.V1PersistentVolumeClaimList = await BaseKOpsClient.acore_v1.list_persistent_volume_claim_for_all_namespaces(**kwargs)
    pvcs = list(pvcs.items)
    if namespace: pvcs = [pvc for pvc in pvcs if pvc.metadata.namespace == namespace]
    return pvcs


@cached(ttl = 5, serializer = DillSerializer)
async def aget_pvcs_from_claim_names(claim_names: List[str], namespace: Optional[str] = None, **kwargs) -> List[at.V1PersistentVolumeClaim]:
    """
    Used to filter down PVCs that are attached to a list of pods
    """
    pvcs = await aget_pvcs(namespace = namespace, **kwargs)
    return [pvc for pvc in pvcs if pvc.metadata.name in claim_names]


@cached(ttl = 5, serializer = DillSerializer)
async def aget_pvcs_with_storageclass(storageclass: str, namespace: Optional[str] = None, name: Optional[str] = None,  **kwargs) -> Union[List[at.V1PersistentVolumeClaim], at.V1PersistentVolumeClaim]:
    pvcs = await aget_pvcs(namespace = namespace, **kwargs)
    pvcs = [pvc for pvc in pvcs if pvc.spec.storage_class_name == storageclass]
    if name:
        for pvc in pvcs:
            if pvc.metadata.name == name:
                return pvc
        raise ValueError(f'PVC {name} not found')
    return pvcs

@cached(ttl = 5, serializer = DillSerializer)
async def aget_pvcs_with_storageclasses(storageclasses: List[str], namespace: Optional[str] = None, **kwargs) -> List[at.V1PersistentVolumeClaim]:
    pvcs = await aget_pvcs(namespace = namespace, **kwargs)
    return [pvc for pvc in pvcs if pvc.spec.storage_class_name in storageclasses]

@cached(ttl = 5, serializer = DillSerializer)
async def aget_pvc(name: str, namespace: Optional[str] = None, storageclass: Optional[str] = None, **kwargs) -> at.V1PersistentVolumeClaim:
    if storageclass:
        return await aget_pvcs_with_storageclass(storageclass = storageclass, name = name, namespace = namespace, **kwargs)
    if name and namespace:
        return await BaseKOpsClient.acore_v1.read_namespaced_persistent_volume_claim(name = name, namespace = namespace, **kwargs)
    pvcs = await aget_pvcs(namespace = namespace, **kwargs)
    for pvc in pvcs:
        if pvc.metadata.name == name:
            return pvc
    raise ValueError(f'PVC {name} not found')


"""
Combination Methods
"""

@cached(ttl = 5, serializer = DillSerializer)
async def aget_pods_with_pvc(namespace: Optional[str] = None, **kwargs) -> List[at.V1Pod]:
    """
    Returns all pods that have a PVC
    """
    pods = await aget_pods(namespace = namespace, **kwargs)
    return [
        pod
        for pod in pods
        if pod.spec.volumes
        and any(v.persistent_volume_claim for v in pod.spec.volumes)
    ]

@cached(ttl = 5, serializer = DillSerializer)
async def aget_pvcs_on_node(name: Optional[str] = None, host_ip: Optional[str] = None, namespace: Optional[str] = None, **kwargs) -> List[at.V1PersistentVolumeClaim]:
    """
    Returns all PVCs that are on a given node
    """
    claim_names = await aget_claimnames_from_pods_on_node(name = name, host_ip = host_ip, namespace = namespace, **kwargs)
    return await aget_pvcs_from_claim_names(claim_names = claim_names, namespace = namespace, **kwargs)

@cached(ttl = 5, serializer = DillSerializer)
async def get_pvcs_on_node_with_storageclasses(storageclasses: List[str], name: Optional[str] = None, host_ip: Optional[str] = None, namespace: Optional[str] = None, **kwargs) -> List[at.V1PersistentVolumeClaim]:
    """
    Returns all PVCs that are on a given node that have a given storageclass
    """
    pvcs = await aget_pvcs_on_node(name = name, host_ip = host_ip, namespace = namespace, **kwargs)
    return [pvc for pvc in pvcs if pvc.spec.storage_class_name in storageclasses]


class KOpsClient(BaseKOpsClient):

    @classmethod
    def get_namespaces(cls, **kwargs) -> List[str]:
        return get_namespaces(**kwargs)
    
    @classmethod
    async def aget_namespaces(cls, **kwargs) -> List[str]:
        return await aget_namespaces(**kwargs)
    
    @classmethod
    def get_nodes(cls, **kwargs) -> List[t.V1Node]:
        return get_nodes(**kwargs)

    @classmethod
    async def aget_nodes(cls, **kwargs) -> List[at.V1Node]:
        return await aget_nodes(**kwargs)
    
    @classmethod
    def get_pods(cls, namespace: Optional[str] = None, **kwargs) -> List[t.V1Pod]:
        return get_pods(namespace = namespace, **kwargs)
    
    @classmethod
    async def aget_pods(cls, namespace: Optional[str] = None, **kwargs) -> List[at.V1Pod]:
        return await aget_pods(namespace = namespace, **kwargs)
    
    @classmethod
    def run_command(
        cls,
        name: str, 
        namespace: str,
        command: Union[str, List[str]],
        container: Optional[str] = None,
        stderr: Optional[bool] = True,
        stdin: Optional[bool] = True,
        stdout: Optional[bool] = True,
        tty: Optional[bool] = False,
        ignore_error: bool = True, 
        **kwargs
    ) -> str:
        return run_pod_command(
            name = name, 
            namespace = namespace,
            command = command,
            container = container,
            stderr = stderr,
            stdin = stdin,
            stdout = stdout,
            tty = tty,
            ignore_error = ignore_error, 
            **kwargs
        )
    
    @classmethod
    async def arun_command(
        cls,
        name: str, 
        namespace: str,
        command: Union[str, List[str]],
        container: Optional[str] = None,
        stderr: Optional[bool] = True,
        stdin: Optional[bool] = True,
        stdout: Optional[bool] = True,
        tty: Optional[bool] = False,
        ignore_error: bool = True, 
        **kwargs
    ) -> str:
        return await arun_pod_command(
            name = name, 
            namespace = namespace,
            command = command,
            container = container,
            stderr = stderr,
            stdin = stdin,
            stdout = stdout,
            tty = tty,
            ignore_error = ignore_error, 
            **kwargs
        )