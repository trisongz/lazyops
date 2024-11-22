from __future__ import annotations

"""
Temporal Object Registry
"""

import copy
import functools
import typing as t
from lzo.registry.base import MRegistry
from lzl.types import eproperty
from temporalio import workflow
from temporalio import activity

from .utils import logger

if t.TYPE_CHECKING:
    from lzl.io.persistence import TemporaryData
    from .client import TemporalClient
    from .settings import TemporalSettings
    from .mixins import (
        BaseTemporalMixin, TemporalWorkflowMixin, TemporalActivityMixin,
        TemporalMixinT, TemporalWorkflowT, TemporalActivityT, 
        MixinKinds
    )
    from temporalio.types import CallableType, ClassType
    
    # TemporalWorkflowT = t.TypeVar('TemporalWorkflowT', bound = TemporalWorkflowMixin)
    # TemporalActivityT = t.TypeVar('TemporalActivityT', bound = TemporalActivityMixin)

class TemporalRegistry(MRegistry['TemporalMixinT']):
    """
    Temporal Registry
    """
    workflow_index: t.Dict[str, t.Dict[str, t.Dict[str, t.Any]]] = {}
    workflow_names: t.Set[str] = set()
    workflow_search_index: t.Dict[str, str] = {}
    workflow_type_index: t.Dict[str, t.Type['TemporalWorkflowT']] = {}

    activity_index: t.Dict[str, t.Dict[str, t.Dict[str, t.Any]]] = {}
    activity_names: t.Set[str] = set()
    activity_search_index: t.Dict[str, str] = {}
    activity_type_index: t.Dict[str, t.Type['TemporalActivityT']] = {}

    # Consolidate
    # search_index: t.Dict[str, str] = {}
    # type_index: t.Dict[str, 'TemporalActivityT' | 'TemporalWorkflowT'] = {}

    @eproperty
    def client(self) -> t.Optional['TemporalClient']:
        """
        Returns the Temporal Client
        """
        return self._extra.get('client')

    @eproperty
    def config(self) -> 'TemporalSettings':
        """
        Returns the Temporal Settings
        """
        from .settings import get_temporal_settings
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
        if value.mixin_kind == 'workflow': self.workflow_names.add(key)
        elif value.mixin_kind == 'activity': self.activity_names.add(key)
    

    def _register(self, key: str, value: 'TemporalMixinT') -> None:
        """
        Registers a Temporal Object in the registry
        """
        # self._import_wf_configs_()
        super()._register(key, value)
        if value.mixin_kind == 'workflow': self.workflow_names.add(key)
        elif value.mixin_kind == 'activity': self.activity_names.add(key)

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

    """
    Main Mixin Registry Methods
    """

    def create_registry_name(self, obj: 'TemporalMixinT', is_type: t.Optional[bool] = None, return_parts: t.Optional[bool] = None) -> str | t.Tuple[str, str, str, t.Optional[str], str]:
        """
        Creates the registry name
        """
        
        if not is_type:
            cls_name = self.get_classname(obj, is_type = is_type)
            cls_module = obj.__class__.__module__.split('.')[0]
        else:
            cls_name = self.get_classname(obj, is_type = is_type).split('.', 1)[-1]
            cls_module = obj.__module__.split('.')[0]
        namespace = obj.namespace
        name = obj.name if getattr(obj, 'name', None) is not None else cls_name
        registry_name = f'{cls_module}.{namespace}.{name}' if namespace else f'{cls_module}.{name}'
        # logger.info(f'Registry Name: {registry_name}', prefix = 'Temporal')
        if return_parts:
            return registry_name, cls_name, cls_module, namespace, name
        return registry_name

    def register_initialized_workflow(
        self,
        obj: 'TemporalWorkflowT',
        **kwargs,
    ) -> None:
        """
        Registers an initialized workflow
        """
        if hasattr(obj, '_rxtra'):
            return self._register_initialized(obj._rxtra['registry_name'], obj)
        registry_name = self.create_registry_name(obj, is_type = False)
        if registry_name in self.init_registry:
            raise ValueError(f'Workflow {registry_name} is already registered')
        return self._register_initialized(registry_name, obj)


    def register_initialized_activity(
        self,
        obj: 'TemporalActivityT',
        **kwargs,
    ) -> None:
        """
        Registers an initialized activity
        """
        if hasattr(obj, '_rxtra'):
            return self._register_initialized(obj._rxtra['registry_name'], obj)
        registry_name = self.create_registry_name(obj, is_type = False)
        if registry_name in self.init_registry:
            raise ValueError(f'Activity {registry_name} is already registered')
        return self._register_initialized(registry_name, obj)

    def _register_temporal_obj_(
        self, 
        obj: t.Type['TemporalMixinT'],
        cls_module: str,
        cls_name: str,
        namespace: str,
        name: str,
        registry_name: str,
        **kwargs,
    ):  # sourcery skip: class-extract-method
        """
        Registers the temporal object
        """
        if getattr(obj, '__init__').__qualname__ == 'BaseTemporalMixin.__init__':
            from .mixins import BaseTemporalMixin
            setattr(obj, '__init__', copy.deepcopy(BaseTemporalMixin.__init__))
        obj._rxtra['base_name'] = str(obj.__name__)
        obj._rxtra['module_source'] = f'{obj.__module__}.{obj.__qualname__}'
        obj._rxtra['module_prefix'] = obj._rxtra['module_source'].rsplit('.', 1)[0]
        obj._rxtra['module'] = cls_module
        obj._rxtra['cls_name'] = cls_name
        obj._rxtra[f'{obj.mixin_kind}_name'] = name
        obj._rxtra[f'{obj.mixin_kind}_namespace'] = namespace
        obj._rxtra['module_path'] = self.get_module_path(obj)
        obj._rxtra['registered'] = True
        obj._rxtra['registry_name'] = registry_name
        
    
    def _index_temporal_obj_(
        self,
        obj: t.Type['TemporalMixinT'] | 'TemporalMixinT',
        **kwargs,
    ):  # sourcery skip: class-extract-method, extract-duplicate-method
        """
        Indexes the temporal object to the referenced registry_name
        """
        search_index = getattr(self, f'{obj.mixin_kind}_search_index')
        type_index = getattr(self, f'{obj.mixin_kind}_type_index')
        registry_name = obj._rxtra['registry_name']
        search_index[registry_name] = registry_name
        if obj._rxtra['module_source'] not in search_index:
            search_index[obj._rxtra['module_source']] = registry_name
        if obj.display_name not in search_index: search_index[obj.display_name] = registry_name
        
        def _index_(base: str):
            if base and '.' not in base: base = f'{base}.'
            for name in {
                obj.name,
                obj._rxtra['cls_name'],
                obj._rxtra['base_name'],
            }:
                if name and f'{base}{name}' not in search_index: search_index[f'{base}{name}'] = registry_name
        
        # Index First without Module
        base_name = ''
        _index_(base_name)
        
        # Index with Module
        base_name += f'{obj._rxtra["module"]}.'
        _index_(base_name)

        # If there's a namespace, index it
        if obj.namespace: 
            _index_(obj.namespace)
            base_name += f'{obj.namespace}.'
            _index_(base_name)
        type_index[registry_name] = obj

    def _search_for_temporal_obj_(
        self,
        module: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        name: t.Optional[str] = None,
        display_name: t.Optional[str] = None,
        kind: t.Optional['MixinKinds'] = 'workflow',
    ) -> t.Optional[str]:
        """
        Searches for the Temporal Object
        """
        index = getattr(self, f'{kind}_search_index')
        if display_name and display_name in index:
            return index[display_name]

        if module:
            base = f'{module}.'
            if namespace: base += f'{namespace}.'
            if name: base += f'{name}'
            if base in index: return index[base]

        # If there's a namespace, search it
        if namespace:
            base = f'{namespace}.'
            if name: base += f'{name}'
            if base in index: return index[base]

        # If there's a name, search it
        return index[name] if name and name in index else None


    def configure_workflow(
        self,
        obj:  t.Type['TemporalWorkflowT'],
        **kwargs,
    ):
        # sourcery skip: extract-method, inline-immediately-returned-variable, move-assign-in-block
        """
        Configures the workflow
        """
        if obj.enable_init:
            init_func = getattr(obj, '__init__')
            init_func = workflow.init(init_func)
            setattr(obj, '__init__', init_func)
        
        _set_run, _set_signal, _set_query = False, False, False
        obj._configure_display_name_()
        obj._configure_gen_id_()
        # if not obj.display_name and (not obj.config or not obj.config.get('disable_full_name')): 
        #     obj.display_name = obj._rxtra['registry_name']
        
        if obj.config:
            if obj.config.get('run'):
                _set_run = True
                run_func = getattr(obj, obj.config['run'])
                run_func = workflow.run(run_func)
                setattr(obj, obj.config['run'], run_func)
            
            if obj.config.get('signal'):
                _set_signal = True
                _skip_set_signal = False
                sig_config = obj.config['signal']
                if isinstance(sig_config, str):
                    sig_func_name = sig_config
                    sig_func = getattr(obj, sig_config)
                    sig_config = {}
                elif isinstance(sig_config, dict):
                    # Single Function
                    if sig_config.get('func'):
                        sig_func_name = sig_config.pop('func')
                        sig_func = getattr(obj, sig_func_name)
                    
                    # Multiple Functions
                    else:
                        _skip_set_signal = True
                        for sig_func_name, func_config in sig_config.items():
                            sig_func = getattr(obj, sig_func_name)
                            if func_config.get('unfinished_policy') and isinstance(func_config['unfinished_policy'], str):
                                func_config['unfinished_policy'] = workflow.HandlerUnfinishedPolicy[func_config['unfinished_policy']]
                            sig_func = workflow.signal(sig_func, **func_config)
                            setattr(obj, sig_func_name, sig_func)
    
                # Support Tuple and Lists later
                else:
                    logger.warning(f'Unsupported Signal Config Type: {sig_config} ({type(sig_config)})', prefix = 'Temporal', colored = True)
                    _skip_set_signal = True
                
                if not _skip_set_signal:
                    if sig_config.get('unfinished_policy') and isinstance(sig_config['unfinished_policy'], str):
                        sig_config['unfinished_policy'] = workflow.HandlerUnfinishedPolicy[sig_config['unfinished_policy']]
                    sig_func = workflow.signal(sig_func, **sig_config)
                    setattr(obj, sig_func_name, sig_func)

            if obj.config.get('query'):
                _set_query = True
                _skip_set_query = False
                query_config = obj.config['query']
                if isinstance(query_config, str):
                    query_func_name = query_config
                    query_func = getattr(obj, query_config)
                    query_config = {}
                
                elif isinstance(query_config, dict):
                    # Single Function
                    if query_config.get('func'):
                        query_func_name = query_config.pop('func')
                        query_func = getattr(obj, query_func_name)
                    
                    # Multiple Functions
                    else:
                        _skip_set_query = True
                        for query_func_name, func_config in query_config.items():
                            query_func = getattr(obj, query_func_name)
                            query_func = workflow.query(query_func, **func_config)
                            setattr(obj, query_func_name, query_func)
                
                # Support Tuple and Lists later
                else:
                    logger.warning(f'Unsupported Query Config Type: {query_config} ({type(query_config)})', prefix = 'Temporal', colored = True)
                    _skip_set_query = True
                    # query_func_name = query_config.pop('func')
                    # query_func = getattr(obj, query_func_name)
                
                if not _skip_set_query:
                    query_func = workflow.query(query_func, **query_config)
                    setattr(obj, query_func_name, query_func)
        
        if not _set_run and hasattr(obj, 'run'):
            run_func = getattr(obj, 'run')
            # if run_func.__qualname__ != 'BaseTemporalMixin.run':
            run_func = workflow.run(run_func)
            setattr(obj, 'run', run_func)
    
        if not _set_signal and hasattr(obj, 'signal'):
            sig_func = getattr(obj, 'signal')
            sig_func = workflow.signal(sig_func)
            setattr(obj, 'signal', sig_func)
        
        if not _set_query and hasattr(obj, 'query'):
            query_func = getattr(obj, 'query')
            query_func = workflow.query(query_func)
            setattr(obj, 'query', query_func)
        
        obj._on_register_hook_()
        

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
        if obj._rxtra.get('registry_name'):
            registry_name = obj._rxtra['registry_name']
            cls_name = obj._rxtra['cls_name']
            cls_module = obj._rxtra['module']
            namespace = obj.namespace
            name = obj._rxtra['workflow_name']
        else:
            registry_name, cls_name, cls_module, namespace, name = self.create_registry_name(obj, is_type = True, return_parts = True)
        if registry_name in self.mregistry:
            if self.tmpdata.has_logged(f'tmprl:register:workflow:exists:{registry_name}'): return
            logger.warning(f'Workflow {name} already registered with `{registry_name}`', prefix = 'Temporal')
            return
        self._register_temporal_obj_(obj, cls_module, cls_name, namespace, name, registry_name, **kwargs)
        self.configure_workflow(obj, **kwargs)
        self.compile_workflow(obj)
        self._index_temporal_obj_(obj)
        if not defn:
            workflow._Definition._apply_to_class(
                obj,
                workflow_name = None if obj.dynamic else obj.display_name,
                sandboxed = obj.sandboxed,
                failure_exception_types = obj.failure_exception_types or [],
            )

        self[f'workflow.{registry_name}'] = obj
        if not self.tmpdata.has_logged(f'tmprl:register:workflow:success:{registry_name}'):
            extra = f' ({self.client.namespace})' if self.client else ''
            logger.info(f'Registered Workflow: `|g|{registry_name}|e|` from `|g|{obj._rxtra["module_source"]}|e|`{extra}', colored = True, prefix = 'Temporal')

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

        _set_funcs = False
        obj._configure_display_name_()
        obj._configure_gen_id_()

        if obj.config:
            if obj.config.get('func'):
                _set_funcs = True
                func = obj.config['func']
                if isinstance(func, str):
                    func_name = func
                    act_func = getattr(obj, func)
                    act_conf = {}
                else:
                    # It's a dict
                    func_name = list(func.keys())[0]
                    act_func = getattr(obj, func_name)
                    act_conf = dict(func.values())

                act_func = activity_defn(obj, act_func, **act_conf)
                setattr(obj, func_name, act_func)
            
            elif obj.config.get('funcs'):
                _set_funcs = True
                funcs = obj.config['funcs']
                for func_name, func_conf in funcs.items():
                    act_func = getattr(obj, func_name)
                    act_func = activity_defn(obj, act_func, **func_conf)
                    setattr(obj, func_name, act_func)
        
        if not _set_funcs:
            # Detect all functions
            for name in dir(obj):
                if name.startswith('_') or name.endswith('_'): continue
                func = getattr(obj, name)
                if not callable(func): continue
                logger.info(f'{obj.display_name} Detected Activity Function: {name}', prefix = 'Temporal')
                act_func = activity_defn(obj, func)
                setattr(obj, name, act_func)
        
        obj._on_register_hook_()

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
        if obj._rxtra.get('registry_name'):
            registry_name = obj._rxtra['registry_name']
            cls_name = obj._rxtra['cls_name']
            cls_module = obj._rxtra['module']
            namespace = obj.namespace
            name = obj._rxtra['activity_name']
        else:
            registry_name, cls_name, cls_module, namespace, name = self.create_registry_name(obj, is_type = True, return_parts = True)
        if registry_name in self.mregistry:
            if self.tmpdata.has_logged(f'tmprl:register:activity:exists:{registry_name}'): return
            logger.warning(f'Activity {name} already registered with `{registry_name}`', prefix = 'Temporal')
            return
        self._register_temporal_obj_(obj, cls_module, cls_name, namespace, name, registry_name, **kwargs)
        self.configure_activity(obj, **kwargs)
        self.compile_activity(obj)
        self._index_temporal_obj_(obj)
        self[f'activity.{registry_name}'] = obj
        if not self.tmpdata.has_logged(f'tmprl:register:activity:success:{registry_name}'):
            extra = f' ({self.client.namespace})' if self.client else ''
            logger.info(f'Registered Activity: `|g|{registry_name}|e|` from `|g|{obj._rxtra["module_source"]}|e|`{extra}', colored = True, prefix = 'Temporal')

    
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
        else:
            raise ValueError(f'Invalid / Unsupported Mixin Kind: {obj.mixin_kind}')
    
    @t.overload
    def get_workflow(
        self,
        registry_name: t.Optional[str] = ...,
        module: t.Optional[str] = ...,
        namespace: t.Optional[str] = ...,
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
        namespace: t.Optional[str] = ...,
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
        namespace: t.Optional[str] = None,
        name: t.Optional[str] = None,
        display_name: t.Optional[str] = None,
        as_type: t.Optional[bool] = None,
    ) -> t.Type['TemporalWorkflowT'] | 'TemporalWorkflowT':
        """
        Gets a Temporal Workflow
        """
        if not registry_name and not module and not namespace and not name and not display_name:
            raise ValueError('Either `registry_name`, `module`, `namespace`, `name`, or `display_name` must be provided')
        if registry_name and registry_name in self.workflow_search_index:
            registry_name = self.workflow_search_index[registry_name]
            return self.workflow_type_index[registry_name] if as_type else self.get(f'workflow.{registry_name}')
        registry_name = self._search_for_temporal_obj_(
            module = module,
            namespace = namespace,
            name = name or registry_name,
            display_name = display_name,
            kind = 'workflow',
        )
        if not registry_name: return None
        if as_type: return self.workflow_type_index[registry_name]
        return self.get(f'workflow.{registry_name}')

    @t.overload
    def get_activity(
        self,
        registry_name: t.Optional[str] = ...,
        module: t.Optional[str] = ...,
        namespace: t.Optional[str] = ...,
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
        namespace: t.Optional[str] = ...,
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
        namespace: t.Optional[str] = None,
        name: t.Optional[str] = None,
        display_name: t.Optional[str] = None,
        as_type: t.Optional[bool] = None,
    ) -> t.Optional['TemporalActivityT']:
        """
        Gets a Temporal Activity
        """
        if not registry_name and not module and not namespace and not name and not display_name:
            raise ValueError('Either `registry_name`, `module`, `namespace`, `name`, or `display_name` must be provided')
        if registry_name and registry_name in self.activity_search_index:
            registry_name = self.activity_search_index[registry_name]
            return self.activity_type_index[registry_name] if as_type else self.get(f'activity.{registry_name}')
        registry_name = self._search_for_temporal_obj_(
            module = module,
            namespace = namespace,
            name = name or registry_name,
            display_name = display_name,
            kind = 'activity',
        )
        if not registry_name: return None
        if as_type: return self.activity_type_index[registry_name]
        return self.get(f'activity.{registry_name}')

    @t.overload
    def get_ref(
        self,
        registry_name: t.Optional[str] = ...,
        module: t.Optional[str] = ...,
        namespace: t.Optional[str] = ...,
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
        namespace: t.Optional[str] = ...,
        name: t.Optional[str] = ...,
        display_name: t.Optional[str] = ...,
        as_type: t.Optional[bool] = ...,
        kind: t.Literal['activity'] = ...,
    ) -> 'TemporalActivityT' | 'TemporalActivityMixin' | t.Type['TemporalActivityT'] | t.Type['TemporalActivityMixin']:
        """
        Gets a Temporal Activity Class or Object
        """
        ...

    def get_ref(
        self,
        registry_name: t.Optional[str] = None,
        module: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        name: t.Optional[str] = None,
        display_name: t.Optional[str] = None,
        as_type: t.Optional[bool] = None,
        kind: t.Optional['MixinKinds'] = 'workflow',
    ) -> t.Union['TemporalWorkflowT', 'TemporalActivityT']:
        """
        Gets a Temporal Object
        """
        func = self.get_workflow if kind == 'workflow' else self.get_activity
        return func(
            registry_name = registry_name,
            module = module,
            namespace = namespace,
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