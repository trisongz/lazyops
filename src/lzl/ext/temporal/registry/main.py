from __future__ import annotations

"""
Temporal Object Registry: Main
"""

import copy
import typing as t
from lzo.registry.base import MRegistry, combine_parts
from lzl.types import eproperty
from lzl.pool import ThreadPool

from temporalio import workflow
from temporalio import activity
from .base import RegistryItem, RegistryIndex
from .methods import configure_workflow, configure_activity, configure_dispatch
from ..utils import logger

if t.TYPE_CHECKING:
    from lzl.io.persistence import TemporaryData
    from temporalio.types import ClassType, CallableType
    from ..client import TemporalClient
    from ..configs import TemporalSettings
    from ..mixins import (
        BaseTemporalMixin, TemporalWorkflowMixin, TemporalActivityMixin, TemporalDispatchMixin,
        TemporalMixinT, TemporalWorkflowT, TemporalActivityT, TemporalDispatchT,
        MixinKinds
    )
    

    
class TemporalRegistry(MRegistry['TemporalMixinT']):
    """
    Temporal Registry
    """
    workflow: RegistryIndex = RegistryIndex()
    activity: RegistryIndex = RegistryIndex()
    dispatch: RegistryIndex = RegistryIndex()


    # Consolidate
    # search_index: t.Dict[str, str] = {}
    # type_index: t.Dict[str, 'TemporalActivityT' | 'TemporalWorkflowT'] = {}
    clients: t.Dict[str, 'TemporalClient'] = {}
    client_get_hooks: t.List[t.Callable[[], t.Awaitable['TemporalClient']]] = []
    client_init_hooks: t.List[t.Callable[[], 'TemporalClient']] = []

    @eproperty
    def client(self) -> t.Optional['TemporalClient']:
        """
        Returns the Temporal Client
        """
        return self._extra.get('client')

    def add_client_hook(
        self, 
        func: t.Callable[[], 'TemporalClient' |  t.Awaitable['TemporalClient']], 
        mode: t.Optional[t.Literal['get', 'init']] = None,
    ):
        """
        Adds a client hook
        """
        # logger.info(f'Adding Client Hook: {func}')
        if mode is None:  mode = 'get' if ThreadPool.is_coro(func) else 'init'
        if mode == 'get': self.client_get_hooks.append(func)
        elif mode == 'init': self.client_init_hooks.append(func)
    
    def run_client_init_hooks(self, client: 'TemporalClient'):
        """
        [Init] Runs the client hooks
        """
        for n, hook in enumerate(self.client_init_hooks):
            if isinstance(hook, str):
                from lzl.load import lazy_import
                hook = lazy_import(hook)
                self.client_init_hooks[n] = hook
            if ThreadPool.is_coro(hook):
                ThreadPool.create_background_task(hook, client)
            else:
                hook(client)
    
    async def run_client_get_hooks(self, client: 'TemporalClient'):
        """
        [Get] Runs the client hooks
        """
        for n, hook in enumerate(self.client_get_hooks):
            if isinstance(hook, str):
                from lzl.load import lazy_import
                hook = lazy_import(hook)
                self.client_get_hooks[n] = hook
            if not ThreadPool.is_coro(hook):
                hook(client)
            else:
                await hook(client)
        
    def register_client(self, client: 'TemporalClient'):
        """
        Registers the Temporal Client
        """
        self.clients[client.namespace] = client
        if not self.client: self.client = client
        self.run_client_init_hooks(client)

    async def get_client(
        self,
        host: t.Optional[str] = None,
        api_key: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        converter: t.Optional[str] = None,
        **kwargs,
    ) -> 'TemporalClient':  # sourcery skip: inline-immediately-returned-variable
        """
        Returns the Temporal Client
        """
        # if namespace and namespace in self.clients: return self.clients[namespace]
        # we'll register null ones too
        if namespace in self.clients: return self.clients[namespace]
        new = await self.config.get_client(
            host = host,
            api_key = api_key,
            namespace = namespace,
            converter = converter,
            **kwargs,
        )
        # do set all the extra stuff
        # ..
        await self.run_client_get_hooks(new)
        return new

    
    @eproperty
    def config(self) -> 'TemporalSettings':
        """
        Returns the Temporal Settings
        """
        from ..configs import get_temporal_settings
        return get_temporal_settings()

    @property
    def tmpdata(self) -> 'TemporaryData':
        """
        Returns the temporary data
        """
        return self.config.tmpdata

    def _register_initialized(self, key: str, value: 'TemporalMixinT') -> None:
        """
        Registers an initialized Temporal Object in the registry
        """
        self.init_registry[key] = value
        if value.mixin_kind == 'workflow': self.workflow.names.add(key)
        elif value.mixin_kind == 'activity': self.activity.names.add(key)
        elif value.mixin_kind == 'dispatch': self.dispatch.names.add(key)
        if value.namespace and value.namespace in self.clients:
            value.client = self.clients[value.namespace]
    

    def _register(self, key: str, value: 'TemporalMixinT') -> None:
        """
        Registers a Temporal Object in the registry
        """
        # self._import_wf_configs_()
        super()._register(key, value)
        if value.mixin_kind == 'workflow': self.workflow.names.add(key)
        elif value.mixin_kind == 'activity': self.activity.names.add(key)
        elif value.mixin_kind == 'dispatch': self.dispatch.names.add(key)

    def register_activity_step(self, func: t.Callable[..., t.Any], **kwargs) -> None:
        """
        Registers an activity step
        """
        pass

    def compile_activity(self, obj: 'TemporalActivityT') -> None:
        """
        Compiles the Temporal Activity
        """
        pass

    def register_workflow_step(self, func: t.Callable[..., t.Any], **kwargs) -> None:
        """
        Registers a workflow step
        """
        pass

    def compile_workflow(self, obj: 'TemporalWorkflowT') -> None:
        """
        Compiles the Temporal Workflow
        """
        pass

    def compile_dispatch(self, obj: 'TemporalDispatchT') -> None:
        """
        Compiles the Temporal Dispatch
        """
        pass

    """
    Main Mixin Registry Methods
    """

    def get_registry_item(self, obj: 'TemporalMixinT', is_type: t.Optional[bool] = None) -> RegistryItem:
        """
        Creates the registry item
        """
        return RegistryItem.build(obj, is_type = is_type)

    """
    Workflow Methods
    """

    def configure_workflow(
        self,
        obj:  t.Type['TemporalWorkflowT'],
        **kwargs,
    ):
        # sourcery skip: extract-method, inline-immediately-returned-variable, move-assign-in-block
        """
        Configures the workflow
        """
        configure_workflow(obj, **kwargs)


    def register_initialized_workflow(
        self,
        obj: 'TemporalWorkflowT',
        **kwargs,
    ) -> None:  # sourcery skip: class-extract-method
        """
        Registers an initialized workflow
        """
        obj._on_init_hook_()
        if hasattr(obj, '_rxtra'):
            return self._register_initialized(obj._rxtra['registry_name'], obj)
        i = self.get_registry_item(obj, is_type = False)
        if i.registry_name in self.init_registry:
            raise ValueError(f'Workflow {i.registry_name} is already registered')
        return self._register_initialized(i.registry_name, obj)
    
    def register_workflow(
        self,
        obj: t.Union[t.Type['TemporalWorkflowT'], 'TemporalWorkflowT'],
        defn: t.Optional[bool] = None,
        **kwargs,
    ) -> None:
        # sourcery skip: extract-method, inline-immediately-returned-variable, move-assign-in-block
        """
        Registers the workflow with the registry
        """
        if not isinstance(obj, type): return self.register_initialized_workflow(obj, **kwargs)
        i = self.get_registry_item(obj, is_type = True)
        if i.registry_name in self.mregistry:
            if self.tmpdata.has_logged(f'tmprl:register:workflow:exists:{i.registry_name}'): return
            logger.warning(f'Workflow {i.registry_name} already registered with `{i.registry_name}`', prefix = 'Temporal')
            return
        i.register_obj(obj)
        self.configure_workflow(obj, **kwargs)
        self.compile_workflow(obj)
        self.workflow.index_obj(obj)
        if not defn:
            workflow._Definition._apply_to_class(
                obj,
                workflow_name = None if obj.dynamic else obj.display_name,
                sandboxed = obj.sandboxed,
                failure_exception_types = obj.failure_exception_types or [],
            )
        self[f'workflow.{[i.registry_name]}'] = obj
        if not self.tmpdata.has_logged(f'tmprl:register:workflow:success:{i.registry_name}'):
            extra = f' ({self.client.namespace})' if self.client else ''
            logger.info(f'Registered Workflow: `|g|{i.registry_name}|e|` from `|g|{i.module_source}|e|`{extra}', colored = True, prefix = 'Temporal')

    """
    Activity Methods
    """

    def configure_activity(
        self,
        obj:  t.Type['TemporalActivityT'],
        **kwargs,
    ):
        # sourcery skip: extract-method, inline-immediately-returned-variable, move-assign-in-block
        """
        Configures the activity
        """
        # init doesnt matter here
        configure_activity(obj, **kwargs)
    
    def register_initialized_activity(
        self,
        obj: 'TemporalActivityT',
        **kwargs,
    ) -> None:
        """
        Registers an initialized activity
        """
        obj._on_init_hook_()
        if hasattr(obj, '_rxtra'):
            return self._register_initialized(obj._rxtra['registry_name'], obj)
        i = self.get_registry_item(obj, is_type = False)
        if i.registry_name in self.init_registry:
            raise ValueError(f'Activity {i.registry_name} is already registered')
        return self._register_initialized(i.registry_name, obj)
    
    def register_activity(
        self,
        obj: t.Union[t.Type['TemporalActivityT'], 'TemporalActivityT'],
        **kwargs,
    ) -> None:
        # sourcery skip: extract-method, inline-immediately-returned-variable, move-assign-in-block
        """
        Registers the activity with the registry
        """
        if not isinstance(obj, type): return self.register_initialized_activity(obj, **kwargs)
        i = self.get_registry_item(obj, is_type = True)
        if i.registry_name in self.mregistry:
            if self.tmpdata.has_logged(f'tmprl:register:activity:exists:{i.registry_name}'): return
            logger.warning(f'Activity {i.registry_name} already registered with `{i.registry_name}`', prefix = 'Temporal')
            return
        i.register_obj(obj)
        self.configure_activity(obj, **kwargs)
        self.compile_activity(obj)
        self.activity.index_obj(obj)
        self[f'activity.{i.registry_name}'] = obj
        if not self.tmpdata.has_logged(f'tmprl:register:activity:success:{i.registry_name}'):
            extra = f' ({self.client.namespace})' if self.client else ''
            logger.info(f'Registered Activity: `|g|{i.registry_name}|e|` from `|g|{i.module_source}|e|`{extra}', colored = True, prefix = 'Temporal')

    """
    Dispatch Methods
    """

    def configure_dispatch(
        self,
        obj: t.Type['TemporalDispatchT'],
        **kwargs,
    ):
        # sourcery skip: extract-method, inline-immediately-returned-variable, move-assign-in-block
        """
        Configures the dispatch
        """
        configure_dispatch(obj, **kwargs)

    
    def register_initialized_dispatch(
        self,
        obj: 'TemporalDispatchT',
        **kwargs,
    ) -> None:
        """
        Registers an initialized Dispatch
        """
        obj._on_init_hook_()
        if hasattr(obj, '_rxtra'):
            return self._register_initialized(obj._rxtra['registry_name'], obj)
        i = self.get_registry_item(obj, is_type = False)
        if i.registry_name in self.init_registry:
            raise ValueError(f'Dispatch {i.registry_name} is already registered')
        return self._register_initialized(i.registry_name, obj)
    
    def register_dispatch(
        self,
        obj: t.Union[t.Type['TemporalDispatchT'], 'TemporalDispatchT'],
        **kwargs,
    ) -> None:
        # sourcery skip: extract-method, inline-immediately-returned-variable, move-assign-in-block
        """
        Registers the dispatch with the registry
        """
        if not isinstance(obj, type): return self.register_initialized_dispatch(obj, **kwargs)
        i = self.get_registry_item(obj, is_type = True)
        if i.registry_name in self.mregistry:
            if self.tmpdata.has_logged(f'tmprl:register:dispatch:exists:{i.registry_name}'): return
            logger.warning(f'Dispatch {i.registry_name} already registered with `{i.registry_name}`', prefix = 'Temporal')
            return
        i.register_obj(obj)
        self.configure_dispatch(obj, **kwargs)
        self.compile_dispatch(obj)
        self.dispatch.index_obj(obj)
        self[f'dispatch.{i.registry_name}'] = obj
        if not self.tmpdata.has_logged(f'tmprl:register:dispatch:success:{i.registry_name}'):
            extra = f' ({self.client.namespace})' if self.client else ''
            logger.info(f'Registered Dispatch: `|g|{i.registry_name}|e|` from `|g|{i.module_source}|e|`{extra}', colored = True, prefix = 'Temporal')

    def _get_index_(self, kind: t.Literal['workflow', 'activity', 'dispatch']) -> RegistryIndex:
        """
        Returns the index
        """
        return getattr(self, kind)

    def search_for_obj(
        self,
        module: t.Optional[str] = None,
        submodule: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        workspace: t.Optional[str] = None,
        name: t.Optional[str] = None,
        display_name: t.Optional[str] = None,
        kind: t.Optional['MixinKinds'] = 'workflow',
        **kwargs,
    ) -> t.Optional[str]:
        """
        Searches for the Temporal Object
        """
        idx = self._get_index_(kind)
        return idx.search_for_obj(module = module, submodule = submodule, namespace = namespace, workspace = workspace, name = name, display_name = display_name, **kwargs)
    
    def register_mixin(
        self,
        obj: t.Union[t.Type['TemporalMixinT'], 'TemporalMixinT'],
        **kwargs,
    ) -> None:
        # sourcery skip: extract-method, inline-immediately-returned-variable, move-assign-in-block
        """
        Registers the Temporal Object with the Registry
        """
        if obj.mixin_kind == 'workflow':
            self.register_workflow(obj, **kwargs)
        elif obj.mixin_kind == 'activity':
            self.register_activity(obj, **kwargs)
        elif obj.mixin_kind == 'dispatch':
            self.register_dispatch(obj, **kwargs)
        
        # else:
        # 
        #     raise ValueError(f'Invalid / Unsupported Mixin Kind: {obj.mixin_kind}')
    
    @t.overload
    def get_workflow(
        self,
        registry_name: t.Optional[str] = ...,
        module: t.Optional[str] = ...,
        submodule: t.Optional[str] = ...,
        namespace: t.Optional[str] = ...,
        workspace: t.Optional[str] = ...,
        name: t.Optional[str] = ...,
        display_name: t.Optional[str] = ...,
        as_type: t.Literal[True] = ...,
    ) -> t.Type['TemporalWorkflowT'] | t.Type['TemporalWorkflowMixin']:
        """
        Gets a Temporal Workflow Class
        """
        ...
    
    @t.overload
    def get_workflow(
        self,
        registry_name: t.Optional[str] = ...,
        module: t.Optional[str] = ...,
        submodule: t.Optional[str] = ...,
        namespace: t.Optional[str] = ...,
        workspace: t.Optional[str] = ...,
        name: t.Optional[str] = ...,
        display_name: t.Optional[str] = ...,
        as_type: t.Literal[False] = ...,
    ) -> 'TemporalWorkflowT' | 'TemporalWorkflowMixin':
        """
        Gets a Temporal Workflow Object
        """
        ...

    def get_workflow(
        self,
        registry_name: t.Optional[str] = None,
        module: t.Optional[str] = None,
        submodule: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        workspace: t.Optional[str] = None,
        name: t.Optional[str] = None,
        display_name: t.Optional[str] = None,
        as_type: t.Optional[bool] = None,
    ) -> t.Type['TemporalWorkflowT'] | 'TemporalWorkflowT':
        """
        Gets a Temporal Workflow
        """
        if not registry_name and not module and not namespace and not name and not display_name:
            raise ValueError('Either `registry_name`, `module`, `namespace`, `name`, or `display_name` must be provided')
        if registry_name and registry_name in self.workflow.search_index:
            registry_name = self.workflow.search_index[registry_name]
            return self.workflow.type_index[registry_name] if as_type else self.get(f'workflow.{registry_name}')
        registry_name = self.search_for_obj(
            module = module,
            submodule = submodule,
            namespace = namespace,
            workspace = workspace,
            name = name or registry_name,
            display_name = display_name,
            kind = 'workflow',
        )
        if not registry_name: return None
        if as_type: return self.workflow.type_index[registry_name]
        return self.get(f'workflow.{registry_name}')

    @t.overload
    def get_activity(
        self,
        registry_name: t.Optional[str] = ...,
        module: t.Optional[str] = ...,
        submodule: t.Optional[str] = ...,
        namespace: t.Optional[str] = ...,
        workspace: t.Optional[str] = ...,
        name: t.Optional[str] = ...,
        display_name: t.Optional[str] = ...,
        as_type: t.Literal[True] = ...,
    ) -> t.Type['TemporalActivityT'] | t.Type['TemporalActivityMixin']:
        """
        Gets a Temporal Activity Class
        """
        ...
    
    @t.overload
    def get_activity(
        self,
        registry_name: t.Optional[str] = ...,
        module: t.Optional[str] = ...,
        submodule: t.Optional[str] = ...,
        namespace: t.Optional[str] = ...,
        workspace: t.Optional[str] = ...,
        name: t.Optional[str] = ...,
        display_name: t.Optional[str] = ...,
        as_type: t.Literal[False] = ...,
    ) -> 'TemporalActivityT' | 'TemporalActivityMixin':
        """
        Gets a Temporal Activity Object
        """
        ...

    def get_activity(
        self,
        registry_name: t.Optional[str] = None,
        module: t.Optional[str] = None,
        submodule: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        workspace: t.Optional[str] = None,
        name: t.Optional[str] = None,
        display_name: t.Optional[str] = None,
        as_type: t.Optional[bool] = None,
    ) -> t.Optional['TemporalActivityT']:
        """
        Gets a Temporal Activity
        """
        if not registry_name and not module and not workspace and not namespace and not name and not display_name:
            raise ValueError('Either `registry_name`, `module`, `workspace`, `namespace`, `name`, or `display_name` must be provided')
        if registry_name and registry_name in self.activity.search_index:
            registry_name = self.activity.search_index[registry_name]
            return self.activity.type_index[registry_name] if as_type else self.get(f'activity.{registry_name}')
        registry_name = self.search_for_obj(
            module = module,
            submodule = submodule,
            namespace = namespace,
            workspace = workspace,
            name = name or registry_name,
            display_name = display_name,
            kind = 'activity',
        )
        if not registry_name: return None
        if as_type: return self.activity.type_index[registry_name]
        return self.get(f'activity.{registry_name}')

    @t.overload
    def get_dispatch(
        self,
        registry_name: t.Optional[str] = ...,
        module: t.Optional[str] = ...,
        submodule: t.Optional[str] = ...,
        namespace: t.Optional[str] = ...,
        workspace: t.Optional[str] = ...,
        name: t.Optional[str] = ...,
        display_name: t.Optional[str] = ...,
        as_type: t.Literal[True] = ...,
    ) -> t.Type['TemporalDispatchT'] | t.Type['TemporalDispatchMixin']:
        """
        Gets a Temporal Dispatch Class
        """
        ...
    
    @t.overload
    def get_dispatch(
        self,
        registry_name: t.Optional[str] = ...,
        module: t.Optional[str] = ...,
        submodule: t.Optional[str] = ...,
        namespace: t.Optional[str] = ...,
        workspace: t.Optional[str] = ...,
        name: t.Optional[str] = ...,
        display_name: t.Optional[str] = ...,
        as_type: t.Literal[False] = ...,
    ) -> 'TemporalDispatchT' | 'TemporalDispatchMixin':
        """
        Gets a Temporal Dispatch Object
        """
        ...

    def get_dispatch(
        self,
        registry_name: t.Optional[str] = None,
        module: t.Optional[str] = None,
        submodule: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        workspace: t.Optional[str] = None,
        name: t.Optional[str] = None,
        display_name: t.Optional[str] = None,
        as_type: t.Optional[bool] = None,
    ) -> t.Optional['TemporalDispatchT']:
        """
        Gets a Temporal Dispatch
        """
        if not registry_name and not module and not workspace and not namespace and not name and not display_name:
            raise ValueError('Either `registry_name`, `module`, `workspace`, `namespace`, `name`, or `display_name` must be provided')
        if registry_name and registry_name in self.dispatch.search_index:
            registry_name = self.dispatch.search_index[registry_name]
            return self.dispatch.type_index[registry_name] if as_type else self.get(f'dispatch.{registry_name}')
        registry_name = self.search_for_obj(
            module = module,
            submodule = submodule,
            namespace = namespace,
            workspace = workspace,
            name = name or registry_name,
            display_name = display_name,
            kind = 'dispatch',
        )
        if not registry_name: return None
        if as_type: return self.dispatch.type_index[registry_name]
        return self.get(f'dispatch.{registry_name}')

    @t.overload
    def get_ref(
        self,
        registry_name: t.Optional[str] = ...,
        module: t.Optional[str] = ...,
        submodule: t.Optional[str] = ...,
        namespace: t.Optional[str] = ...,
        workspace: t.Optional[str] = ...,
        name: t.Optional[str] = ...,
        display_name: t.Optional[str] = ...,
        as_type: t.Optional[bool] = ...,
        kind: t.Literal['workflow'] = ...,
    ) -> 'TemporalWorkflowT' | 'TemporalWorkflowMixin' | t.Type['TemporalWorkflowT'] | t.Type['TemporalWorkflowMixin']:
        """
        Gets a Temporal Workflow Class or Object
        """
        ...

    @t.overload
    def get_ref(
        self,
        registry_name: t.Optional[str] = ...,
        module: t.Optional[str] = ...,
        submodule: t.Optional[str] = ...,
        namespace: t.Optional[str] = ...,
        workspace: t.Optional[str] = ...,
        name: t.Optional[str] = ...,
        display_name: t.Optional[str] = ...,
        as_type: t.Optional[bool] = ...,
        kind: t.Literal['activity'] = ...,
    ) -> 'TemporalActivityT' | 'TemporalActivityMixin' | t.Type['TemporalActivityT'] | t.Type['TemporalActivityMixin']:
        """
        Gets a Temporal Activity Class or Object
        """
        ...

    
    @t.overload
    def get_ref(
        self,
        registry_name: t.Optional[str] = ...,
        module: t.Optional[str] = ...,
        submodule: t.Optional[str] = ...,
        namespace: t.Optional[str] = ...,
        workspace: t.Optional[str] = ...,
        name: t.Optional[str] = ...,
        display_name: t.Optional[str] = ...,
        as_type: t.Optional[bool] = ...,
        kind: t.Literal['dispatch'] = ...,
    ) -> 'TemporalDispatchT' | 'TemporalDispatchMixin' | t.Type['TemporalDispatchT'] | t.Type['TemporalDispatchMixin']:
        """
        Gets a Temporal Dispatch Class or Object
        """
        ...

    def get_ref(
        self,
        registry_name: t.Optional[str] = None,
        module: t.Optional[str] = None,
        submodule: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        workspace: t.Optional[str] = None,
        name: t.Optional[str] = None,
        display_name: t.Optional[str] = None,
        as_type: t.Optional[bool] = None,
        kind: t.Optional['MixinKinds'] = 'workflow',
    ) -> t.Union['TemporalWorkflowT', 'TemporalActivityT']:
        """
        Gets a Temporal Object
        """
        if kind == 'workflow':
            func = self.get_workflow
        elif kind == 'activity':
            func = self.get_activity
        elif kind == 'dispatch':
            func = self.get_dispatch
        else:
            raise ValueError(f'Invalid Kind: {kind}')
        # func = self.get_workflow if kind == 'workflow' else self.get_activity
        return func(
            registry_name = registry_name,
            module = module,
            submodule = submodule,
            namespace = namespace,
            workspace = workspace,
            name = name,
            display_name = display_name,
            as_type = as_type,
        )

    
registry: TemporalRegistry = TemporalRegistry('temporal')

@t.overload
def workflow_defn(
    cls: 'TemporalWorkflowT',
    *,
    name: t.Optional[str] = ...,
    sandboxed: t.Optional[bool] = ...,
    dynamic: t.Optional[bool] = ...,
    failure_exception_types: t.Sequence[t.Type[BaseException]] = ...,
) -> 'TemporalWorkflowT':
    """Decorator for workflow classes.

    This must be set on any registered workflow class (it is ignored if on a
    base class).

    Args:
        cls: The class to decorate.
        name: Name to use for the workflow. Defaults to class ``__name__``. This
            cannot be set if dynamic is set.
        sandboxed: Whether the workflow should run in a sandbox. Default is
            true.
        dynamic: If true, this activity will be dynamic. Dynamic workflows have
            to accept a single 'Sequence[RawValue]' parameter. This cannot be
            set to true if name is present.
        failure_exception_types: The types of exceptions that, if a
            workflow-thrown exception extends, will cause the workflow/update to
            fail instead of suspending the workflow via task failure. These are
            applied in addition to ones set on the worker constructor. If
            ``Exception`` is set, it effectively will fail a workflow/update in
            all user exception cases. WARNING: This setting is experimental.
    """
    ...

def workflow_defn(
    cls: t.Optional['ClassType'] = None,
    *,
    name: t.Optional[str] = None,
    sandboxed: t.Optional[bool] = True,
    dynamic: t.Optional[bool] = False,
    failure_exception_types: t.Sequence[t.Type[BaseException]] = [],
) -> t.Callable[['ClassType'], 'ClassType']:
    """Decorator for workflow classes.

    This must be set on any registered workflow class (it is ignored if on a
    base class).

    Args:
        cls: The class to decorate.
        name: Name to use for the workflow. Defaults to class ``__name__``. This
            cannot be set if dynamic is set.
        sandboxed: Whether the workflow should run in a sandbox. Default is
            true.
        dynamic: If true, this activity will be dynamic. Dynamic workflows have
            to accept a single 'Sequence[RawValue]' parameter. This cannot be
            set to true if name is present.
        failure_exception_types: The types of exceptions that, if a
            workflow-thrown exception extends, will cause the workflow/update to
            fail instead of suspending the workflow via task failure. These are
            applied in addition to ones set on the worker constructor. If
            ``Exception`` is set, it effectively will fail a workflow/update in
            all user exception cases. WARNING: This setting is experimental.
    """
    if cls and workflow._Definition.from_class(cls): return cls
    def decorator(cls: 'ClassType' | t.Type['TemporalWorkflowT']) -> 'ClassType':
        nonlocal name, sandboxed, dynamic, failure_exception_types
        registry.register_workflow(cls, defn = True)
        if cls.failure_exception_types: failure_exception_types = cls.failure_exception_types
        if cls.sandboxed is not None: sandboxed = cls.sandboxed
        if cls.dynamic is not None: dynamic = cls.dynamic
        # name = None if dynamic else cls._rxtra['workflow_name']
        name = None if dynamic else cls.display_name
        # This performs validation
        workflow._Definition._apply_to_class(
            cls,
            workflow_name = name,
            sandboxed = sandboxed,
            failure_exception_types = failure_exception_types,
        )
        return cls
    return decorator(cls) if cls is not None else decorator


def activity_defn(
    cls: 'ClassType' | 'TemporalActivityT',
    fn: 'CallableType',
    *,
    name: t.Optional[str] = None,
    no_thread_cancel_exception: bool = False,
    dynamic: bool = False,
):
    """Decorator for activity functions.

    Activities can be async or non-async.

    Args:
        fn: The function to decorate.
        name: Name to use for the activity. Defaults to function ``__name__``.
            This cannot be set if dynamic is set.
        no_thread_cancel_exception: If set to true, an exception will not be
            raised in synchronous, threaded activities upon cancellation.
        dynamic: If true, this activity will be dynamic. Dynamic activities have
            to accept a single 'Sequence[RawValue]' parameter. This cannot be
            set to true if name is present.
    """
    if cls.no_thread_cancel_exception is not None: no_thread_cancel_exception = cls.no_thread_cancel_exception
    if cls.dynamic is not None: dynamic = cls.dynamic
    def decorator(fn: 'CallableType') -> 'CallableType':
        # This performs validation
        activity._Definition._apply_to_callable(
            fn,
            activity_name = None if dynamic else name or fn.__name__,
            no_thread_cancel_exception = no_thread_cancel_exception,
        )
        return fn
    return decorator(fn)



workflow.defn = workflow_defn