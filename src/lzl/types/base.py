from __future__ import annotations

"""
Resolver for Pydantic v1/v2 imports with additional helpers
"""
import typing
import functools
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo
from pydantic.types import ByteSize
from lzl.require import resolve_missing

# Handle v1/v2 of pydantic
try:
    from pydantic import field_validator
    from pydantic import model_validator
    from pydantic import validator as _validator
    from pydantic import ConfigDict
    from pydantic import PrivateAttr

    PYDANTIC_VERSION = 2

    def root_validator(*args, **kwargs):
        """
        v1 Compatible root validator
        """
        def decorator(func):
            _pre_kw = kwargs.pop('pre', None)
            kwargs['mode'] = 'before' if _pre_kw is True else ('after' if _pre_kw is False else kwargs.get('mode', 'wrap'))
            return model_validator(*args, **kwargs)(func)
        return decorator

    def pre_root_validator(*args, **kwargs):
        def decorator(func):
            return model_validator(*args, mode='before', **kwargs)(func)
        return decorator
    
    def validator(*args, **kwargs):
        def decorator(func):
            return _validator(*args, **kwargs)(classmethod(func))
        return decorator

except ImportError:
    from pydantic import root_validator, validator

    ConfigDict = typing.Dict[str, typing.Any]

    PYDANTIC_VERSION = 1

    def pre_root_validator(*args, **kwargs):
        def decorator(func):
            return root_validator(*args, pre=True, **kwargs)(func)
        return decorator

    def field_validator(*args, **kwargs):
        def decorator(func):
            return validator(*args, **kwargs)(func)
        return decorator
    
    def model_validator(*args, **kwargs):
        def decorator(func):
            return root_validator(*args, **kwargs)(func)
        return decorator
    
    PrivateAttr = functools.partial(Field, exclude = True)

try:
    from pydantic_settings import BaseSettings

except ImportError:
    if PYDANTIC_VERSION == 2:
        resolve_missing('pydantic-settings', required = True)
        from pydantic_settings import BaseSettings
    else:
        from pydantic import BaseSettings



def get_pydantic_dict(model: typing.Union[BaseModel, BaseSettings], **kwargs) -> typing.Dict[str, typing.Any]:
    """
    Get a dict from a pydantic model
    """
    if kwargs: kwargs = {k:v for k,v in kwargs.items() if v is not None}
    if hasattr(model, 'model_dump'):
        return model.model_dump(**kwargs)
    return model.dict(**kwargs)

def get_pydantic_fields_dict(model: typing.Type[typing.Union[BaseModel, BaseSettings]]) -> typing.Dict[str, FieldInfo]:
    """
    Get a dict of fields from a pydantic model
    """
    if hasattr(model, 'model_fields'):
        return model.model_fields
    return model.__fields__

def get_pydantic_field_names(model: typing.Type[typing.Union[BaseModel, BaseSettings]]) -> typing.List[str]:
    """
    Get a list of field names from a pydantic model
    """
    return list(get_pydantic_fields_dict(model).keys())

def get_pydantic_fields(model: typing.Type[typing.Union[BaseModel, BaseSettings]]) -> typing.List[FieldInfo]:
    """
    Get a list of fields from a pydantic model
    """
    return list(get_pydantic_fields_dict(model).values())

def pydantic_parse_obj(model: typing.Type[typing.Union[BaseModel, BaseSettings]], obj: typing.Any, **kwargs) -> typing.Union[BaseModel, BaseSettings]:
    """
    Parse an object into a pydantic model
    """
    if hasattr(model, 'model_validate'):
        return model.model_validate(obj, **kwargs)
    return model.parse_obj(obj)

def get_pydantic_schema(model: typing.Type[typing.Union[BaseModel, BaseSettings]], **kwargs) -> typing.Dict[str, typing.Any]:
    """
    Get a pydantic schema
    """
    if hasattr(model, 'model_json_schema'):
        return model.model_json_schema(**kwargs)
    return model.schema(**kwargs)


def get_schema_extra(schema: typing.Dict[str, typing.Any], _):
    """
    Helper to get the extra schema
    """
    props = {
        k: v
        for k, v in schema.get('properties', {}).items()
        if not v.get("hidden", False) and not k.startswith('_')
    }
    schema["properties"] = props
