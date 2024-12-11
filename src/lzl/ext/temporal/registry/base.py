from __future__ import annotations

"""
Temporal Object Registry: Base
"""

import copy
import inspect
import dataclasses
import typing as t
import pathlib
from lzo.registry.base import combine_parts
from lzl.io.ser import get_object_classname

if t.TYPE_CHECKING:
    from ..mixins import (
        BaseTemporalMixin, TemporalWorkflowMixin, TemporalActivityMixin,
        TemporalMixinT, TemporalWorkflowT, TemporalActivityT, TemporalObjT,
        MixinKinds
    )

@dataclasses.dataclass
class RegistryItem:
    """
    Registry Item
    """
    
    base_name: t.Optional[str] = None
    cls_name: t.Optional[str] = None
    cls_module: t.Optional[str] = None
    cls_submodule: t.Optional[str] = None
    module_source: t.Optional[str] = None
    module_prefix: t.Optional[str] = None
    namespace: t.Optional[str] = None
    workspace: t.Optional[str] = None
    name: t.Optional[str] = None
    mixin_kind: t.Optional['MixinKinds'] = None
    registry_name: t.Optional[str] = None

    @classmethod
    def get_module_path(cls, obj: t.Type['TemporalMixinT']) -> pathlib.Path:
        """
        Gets the module path
        """
        return pathlib.Path(inspect.getfile(obj)).parent

    @classmethod
    def parse_obj(cls, obj: 'TemporalMixinT', is_type: t.Optional[bool] = None) -> 'RegistryItem':
        """
        Parses the Object
        """
        cls_module = getattr(obj, '_rmodule', None)
        cls_submodule = getattr(obj, '_rsubmodule', None)
        if not is_type:
            cls_name = get_object_classname(obj, is_type = is_type)
            base_name = str(obj.__name__)
            if not cls_module: cls_module = obj.__class__.__module__.split('.')[0]
            module_source =f'{obj.__class__.__module__}.{obj.__class__.__qualname__}'
        else:
            cls_name = get_object_classname(obj, is_type = is_type).split('.', 1)[-1]
            base_name = cls_name
            if not cls_module: cls_module = obj.__module__.split('.')[0]
            module_source = f'{obj.__module__}.{obj.__qualname__}'
        module_prefix = module_source.rsplit('.', 1)[0]
        namespace = obj.namespace
        workspace = obj.workspace
        name = obj.name if getattr(obj, 'name', None) is not None else cls_name
        registry_name = combine_parts(cls_module, cls_submodule, namespace, workspace, name)
        if cls_submodule and f'{cls_submodule}.{cls_submodule}' in registry_name:
            registry_name = registry_name.replace(f'{cls_submodule}.{cls_submodule}', cls_submodule)
        return cls(
            base_name = base_name,
            registry_name = registry_name, 
            cls_name = cls_name, 
            cls_module = cls_module, 
            cls_submodule = cls_submodule, 
            module_source = module_source,
            module_prefix = module_prefix,
            namespace = namespace, 
            workspace = workspace, 
            name = name,
            mixin_kind = obj.mixin_kind,
        )

    
    @classmethod
    def from_obj(cls, obj: 'TemporalMixinT', is_type: t.Optional[bool] = None) -> 'RegistryItem':
        """
        Creates the registry item from the object
        """
        if hasattr(obj, '_rxtra') and obj._rxtra.get('registry_name'):
            return cls(
                base_name = obj._rxtra['base_name'],
                registry_name = obj._rxtra['registry_name'],
                cls_name = obj._rxtra['cls_name'],
                cls_module = obj._rxtra['module'],
                cls_submodule = obj._rxtra['submodule'],
                module_source = obj._rxtra['module_source'],
                module_prefix = obj._rxtra['module_prefix'],
                namespace = obj.namespace,
                workspace = obj.workspace,
                name = obj._rxtra['object_name'],
                mixin_kind = obj.mixin_kind,
            )
        return cls.parse_obj(obj, is_type = is_type)

    @classmethod
    def build(cls, obj: 'TemporalMixinT', is_type: t.Optional[bool] = None) -> 'RegistryItem':
        """
        Builds the registry item from the object
        """
        if hasattr(obj, '_rxtra') and obj._rxtra.get('reg_item'):
            return obj._rxtra['reg_item']
        return cls.parse_obj(obj, is_type = is_type)

    
    def register_obj(
        self,
        obj: t.Type['TemporalMixinT'],
        **kwargs,
    ):
        """
        Registers the Temporal Object
        """
        if getattr(obj, '__init__').__qualname__ == 'BaseTemporalMixin.__init__':
            from ..mixins import BaseTemporalMixin
            setattr(obj, '__init__', copy.deepcopy(BaseTemporalMixin.__init__))
        
        obj._rxtra['base_name'] = self.base_name
        obj._rxtra['module_source'] = self.module_source
        obj._rxtra['module_prefix'] = self.module_prefix
        obj._rxtra['module'] = self.cls_module
        obj._rxtra['submodule'] = self.cls_submodule
        obj._rxtra['cls_name'] = self.cls_name
        obj._rxtra['object_name'] = self.name
        obj._rxtra[f'{obj.mixin_kind}_name'] = self.name
        obj._rxtra[f'{obj.mixin_kind}_namespace'] = self.namespace
        obj._rxtra[f'{obj.mixin_kind}_workspace'] = self.workspace
        obj._rxtra['module_path'] = self.get_module_path(obj)
        obj._rxtra['reg_item'] = self
        obj._rxtra['registered'] = True
        obj._rxtra['registry_name'] = self.registry_name

    def __getitem__(self, key: str) -> t.Optional[str]:
        """
        Gets a value
        """
        return getattr(self, key, None)
    
    def get(self, key: str, default: t.Any  = None) -> t.Any:
        """
        Gets an attribute like a dict
        """
        return getattr(self, key, default)


@dataclasses.dataclass
class RegistryIndex:
    """
    The Object Registry Index
    """
    index: t.Dict[str, t.Dict[str, t.Dict[str, t.Any]]] = dataclasses.field(default_factory = dict)
    names: t.Set[str] = dataclasses.field(default_factory = set)
    search_index: t.Dict[str, str] = dataclasses.field(default_factory = dict)
    type_index: t.Dict[str, t.Type['TemporalObjT']] = dataclasses.field(default_factory = dict)

    def index_obj(
        self,
        obj: t.Type['TemporalMixinT'] | 'TemporalMixinT',
        **kwargs,
    ):  # sourcery skip: class-extract-method, extract-duplicate-method
        """
        Indexes the temporal object to the referenced registry_name
        """
        i: RegistryItem = obj._rxtra['reg_item']
        self.search_index[i.registry_name] = i.registry_name
        if i.module_source not in self.search_index:
            self.search_index[i.module_source] = i.registry_name
        if obj.display_name not in self.search_index: self.search_index[obj.display_name] = i.registry_name

        def _do_index_(base: str):
            """
            Main Indexing Function
            """
            if base and '.' not in base: base = f'{base}.'
            for name in {
                obj.name, i.cls_name, i.base_name,
            }:
                if name and f'{base}{name}' not in self.search_index: self.search_index[f'{base}{name}'] = i.registry_name
        
        # Index First without Module
        base_name = ''
        _do_index_(base_name)
        
        # Index with Module
        base_name += f'{i.cls_module}.'
        _do_index_(base_name)

        if i.cls_submodule:
            base_name += f'{i.cls_submodule}.'
            _do_index_(base_name)
        
        # If there's a workspace, index it
        if obj.workspace:
            _do_index_(obj.workspace)

        # If there's a namespace, index it
        if obj.namespace: 
            _do_index_(obj.namespace)
            base_name += f'{obj.namespace}.'
            _do_index_(base_name)
            if obj.workspace: 
                base_name += f'{obj.workspace}.'
                _do_index_(base_name)

        self.type_index[i.registry_name] = obj


    def search_for_obj(
        self,
        module: t.Optional[str] = None,
        submodule: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        workspace: t.Optional[str] = None,
        name: t.Optional[str] = None,
        display_name: t.Optional[str] = None,
        **kwargs,
    ) -> t.Optional[str]:
        """
        Searches for the Temporal Object
        """
        if display_name and display_name in self.search_index:
            return self.search_index[display_name]
        
        if module:
            base = combine_parts(module, submodule, namespace, workspace, name)
            if base in self.search_index: return self.search_index[base]

        # If there's a workspace, search it
        if workspace:
            base = combine_parts(workspace, name)
            if base in self.search_index: return self.search_index[base]

        # If there's a namespace, search it
        if namespace:
            base = combine_parts(namespace, name)
            if base in self.search_index: return self.search_index[base]

        # If there's a name, search it
        return self.search_index[name] if name and name in self.search_index else None