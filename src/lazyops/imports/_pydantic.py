"""
Resolver for Pydantic v1/v2 imports with additional helpers
"""


import typing
from lazyops.utils.imports import resolve_missing


# Handle v1/v2 of pydantic
try:
    from pydantic import validator as _validator
    from pydantic import model_validator as base_root_validator
    from pydantic import ConfigDict

    PYD_VERSION = 2

    def root_validator(*args, **kwargs):
        """
        v1 Compatible root validator
        """
        def decorator(func):
            _pre_kw = kwargs.pop('pre', None)
            kwargs['mode'] = 'before' if _pre_kw is True else ('after' if _pre_kw is False else kwargs.get('mode', 'wrap'))
            return base_root_validator(*args, **kwargs)(func)
        return decorator

    def pre_root_validator(*args, **kwargs):
        def decorator(func):
            return base_root_validator(*args, mode='before', **kwargs)(func)
        return decorator
    
    def validator(*args, **kwargs):
        def decorator(func):
            return _validator(*args, **kwargs)(classmethod(func))
        return decorator

except ImportError:
    from pydantic import root_validator, validator

    ConfigDict = typing.Dict[str, typing.Any]

    PYD_VERSION = 1

    def pre_root_validator(*args, **kwargs):
        def decorator(func):
            return root_validator(*args, pre=True, **kwargs)(func)
        return decorator



try:
    from pydantic_settings import BaseSettings

except ImportError:
    if PYD_VERSION == 2:
        resolve_missing('pydantic-settings', required = True)
        from pydantic_settings import BaseSettings
    else:
        from pydantic import BaseSettings

import inspect
import pkg_resources
from pathlib import Path

# _AppModulePaths: typing.Dict[str, Path] = {}

class BaseAppSettings(BaseSettings):
    """
    BaseSettings with additional helpers
    """

    @property
    def module_path(self) -> Path:
        """
        Gets the module root path

        https://stackoverflow.com/questions/25389095/python-get-path-of-root-project-structure
        """
        # For some reason, whenever it gets recomputed, it returns the wrong path
        # global _AppModulePaths
        # if self.module_name not in _AppModulePaths:
        p = Path(pkg_resources.get_distribution(self.module_name).location)
        # print(p, self.module_name, self.__class__.__qualname__)
        if 'src' in p.name and p.joinpath(self.module_name).exists():
            p = p.joinpath(self.module_name)
        elif p.joinpath('src').exists() and p.joinpath('src', self.module_name).exists():
            p = p.joinpath('src', self.module_name)
        # print(p, self.module_name, self.__class__.__qualname__)
        return p
        #     _AppModulePaths[self.module_name] = p
        # return _AppModulePaths[self.module_name]

    @property
    def module_config_path(self) -> Path:
        """
        Returns the config module path
        """
        return Path(inspect.getfile(self.__class__)).parent

    @property
    def module_name(self) -> str:
        """
        Returns the module name
        """
        return self.__class__.__module__.split(".")[0]
    
    @property
    def module_version(self) -> str:
        """
        Returns the module version
        """
        return pkg_resources.get_distribution(self.module_name).version
    
    @property
    def module_pkg_name(self) -> str:
        """
        Returns the module pkg name
        
        {pkg}/src   -> src
        {pkg}/{pkg} -> {pkg}
        """
        config_path = self.module_config_path.as_posix()
        module_path = self.module_path.as_posix()
        return config_path.replace(module_path, "").strip().split("/", 2)[1]

    @property
    def in_k8s(self) -> bool:
        """
        Returns whether the app is running in kubernetes
        """
        from lazyops.utils.system import is_in_kubernetes
        return is_in_kubernetes()
    
    @property
    def host_name(self) -> str:
        """
        Returns the hostname
        """
        from lazyops.utils.system import get_host_name
        return get_host_name()




from pydantic import BaseModel
from pydantic.fields import FieldInfo


def get_pyd_dict(model: typing.Union[BaseModel, BaseSettings], **kwargs) -> typing.Dict[str, typing.Any]:
    """
    Get a dict from a pydantic model
    """
    if kwargs: kwargs = {k:v for k,v in kwargs.items() if v is not None}
    return model.model_dump(**kwargs) if PYD_VERSION == 2 else model.dict(**kwargs)

def get_pyd_fields_dict(model: typing.Type[typing.Union[BaseModel, BaseSettings]]) -> typing.Dict[str, FieldInfo]:
    """
    Get a dict of fields from a pydantic model
    """
    return model.model_fields if PYD_VERSION == 2 else model.__fields__

def get_pyd_field_names(model: typing.Type[typing.Union[BaseModel, BaseSettings]]) -> typing.List[str]:
    """
    Get a list of field names from a pydantic model
    """
    return list(get_pyd_fields_dict(model).keys())

def get_pyd_fields(model: typing.Type[typing.Union[BaseModel, BaseSettings]]) -> typing.List[FieldInfo]:
    """
    Get a list of fields from a pydantic model
    """
    return list(get_pyd_fields_dict(model).values())

def pyd_parse_obj(model: typing.Type[typing.Union[BaseModel, BaseSettings]], obj: typing.Any, **kwargs) -> typing.Union[BaseModel, BaseSettings]:
    """
    Parse an object into a pydantic model
    """
    return model.model_validate(obj, **kwargs) if PYD_VERSION == 2 else model.parse_obj(obj)

def get_pyd_schema(model: typing.Type[typing.Union[BaseModel, BaseSettings]], **kwargs) -> typing.Dict[str, typing.Any]:
    """
    Get a pydantic schema
    """
    return model.schema(**kwargs) if PYD_VERSION == 2 else model.model_json_schema(**kwargs)


# https://github.com/pydantic/pydantic/issues/6763
# Patch until `pydantic-core` gets updated

# if PYD_VERSION == 2:
#     import pkg_resources


#     # If the module is < 2.10.1, then we need to patch it
#     pyd_core_version = pkg_resources.get_distribution('pydantic-core').version.split('.')
#     pyd_core_version_major = int(pyd_core_version[0])
#     pyd_core_version_minor = int(pyd_core_version[1])
#     pyd_core_version_patch = int(pyd_core_version[2])

#     if pyd_core_version_minor < 10 or pyd_core_version_patch < 2:

#         import weakref
#         import pydantic
#         # from pydantic.type_adapter import SchemaSerializer
#         from pydantic._internal._model_construction import SchemaSerializer
#         # from pydantic.schema import SchemaSerializer

#         class PickleableSchemaSerializer:
#             def __init__(self, schema, core_config):
#                 self._schema = schema
#                 self._core_config = core_config
#                 self._schema_serializer = SchemaSerializer(self._schema, self._core_config)

#             def __reduce__(self):
#                 return PickleableSchemaSerializer, (self._schema, self._core_config)

#             def __getattr__(self, attr: str):
#                 return getattr(self._schema_serializer, attr)

#         # class PickleableSchemaSerializer(SchemaSerializer):
#         #     def __init__(self, schema, core_config):
#         #         self._schema = schema
#         #         self._core_config = core_config
#         #         # No need for `super().__init__()` because `SchemaSerializer` initialization happens in `__new__`.

#         #     def __reduce__(self):
#         #         return PickleableSchemaSerializer, (self._schema, self._core_config)


#         class WeakRefWrapper:
#             def __init__(self, obj: typing.Any):
#                 self._wr = None if obj is None else weakref.ref(obj)

#             def __reduce__(self):
#                 return WeakRefWrapper, (self(),)

#             def __call__(self) -> typing.Any:
#                 return None if self._wr is None else self._wr()
        
#         pydantic._internal._model_construction.SchemaSerializer = PickleableSchemaSerializer
#         pydantic._internal._dataclasses.SchemaSerializer = PickleableSchemaSerializer
#         pydantic.type_adapter.SchemaSerializer = PickleableSchemaSerializer

#         # Override all usages of `_PydanticWeakRef` (obviously not needed if we upstream the above wrapper):
#         pydantic._internal._model_construction._PydanticWeakRef = WeakRefWrapper

    
