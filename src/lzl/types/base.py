from __future__ import annotations

"""
Pydantic v1/v2 Compatibility Layer and Helper Utilities.

This module provides a consistent interface for Pydantic features across
both v1 and v2, handling import differences and providing utility functions
for common Pydantic operations.
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
        """Wraps `pydantic.model_validator` for v1 compatibility.

        Provides a decorator that behaves like Pydantic v1's `root_validator`,
        mapping the `pre` argument to the `mode` argument in v2's
        `model_validator`.

        Args:
            *args: Positional arguments passed to `model_validator`.
            **kwargs: Keyword arguments passed to `model_validator`. 'pre' is
                mapped to `mode` ('before' if True, 'after' if False).

        Returns:
            Callable: A decorator for root validation methods.
        """
        def decorator(func):
            _pre_kw = kwargs.pop('pre', None)
            kwargs['mode'] = 'before' if _pre_kw is True else ('after' if _pre_kw is False else kwargs.get('mode', 'wrap'))
            return model_validator(*args, **kwargs)(func)
        return decorator

    def pre_root_validator(*args, **kwargs):
        """Wraps `pydantic.model_validator(mode='before')` for v1 compatibility.

        Provides a decorator that behaves like Pydantic v1's `root_validator`
        with `pre=True`.

        Args:
            *args: Positional arguments passed to `model_validator`.
            **kwargs: Keyword arguments passed to `model_validator`.

        Returns:
            Callable: A decorator for pre-validation methods.
        """
        def decorator(func):
            return model_validator(*args, mode='before', **kwargs)(func)
        return decorator
    
    def validator(*args, **kwargs):
        """Wraps `pydantic.validator` for v1 compatibility.

        Ensures the decorated function is treated as a class method.

        Args:
            *args: Positional arguments passed to `pydantic.validator`.
            **kwargs: Keyword arguments passed to `pydantic.validator`.

        Returns:
            Callable: A decorator for validation methods.
        """
        def decorator(func):
            return _validator(*args, **kwargs)(classmethod(func))
        return decorator

except ImportError:
    from pydantic import root_validator, validator

    ConfigDict = typing.Dict[str, typing.Any]

    PYDANTIC_VERSION = 1

    def pre_root_validator(*args, **kwargs):
        """Wraps `pydantic.root_validator(pre=True)` for v2 compatibility.

        Args:
            *args: Positional arguments passed to `root_validator`.
            **kwargs: Keyword arguments passed to `root_validator`.

        Returns:
            Callable: A decorator for pre-validation methods.
        """
        def decorator(func):
            return root_validator(*args, pre=True, **kwargs)(func)
        return decorator

    def field_validator(*args, **kwargs):
        """Wraps `pydantic.validator` for v2 compatibility.

        Behaves like Pydantic v2's `field_validator`.

        Args:
            *args: Positional arguments passed to `validator`.
            **kwargs: Keyword arguments passed to `validator`.

        Returns:
            Callable: A decorator for field validation methods.
        """
        def decorator(func):
            return validator(*args, **kwargs)(func)
        return decorator
    
    def model_validator(*args, **kwargs):
        """Wraps `pydantic.root_validator` for v2 compatibility.

        Behaves like Pydantic v2's `model_validator`.

        Args:
            *args: Positional arguments passed to `root_validator`.
            **kwargs: Keyword arguments passed to `root_validator`.

        Returns:
            Callable: A decorator for model validation methods.
        """
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
    """Gets a dictionary representation of a Pydantic model.

    Handles compatibility between Pydantic v1 (`dict()`) and v2 (`model_dump()`).

    Args:
        model: The Pydantic model instance.
        **kwargs: Keyword arguments passed to `dict()` or `model_dump()`.
            Only non-None values are passed.

    Returns:
        Dict[str, Any]: The dictionary representation of the model.
    """
    if kwargs: kwargs = {k:v for k,v in kwargs.items() if v is not None}
    if hasattr(model, 'model_dump'):
        return model.model_dump(**kwargs)
    return model.dict(**kwargs)

def get_pydantic_fields_dict(model: typing.Type[typing.Union[BaseModel, BaseSettings]]) -> typing.Dict[str, FieldInfo]:
    """Gets a dictionary of fields from a Pydantic model class.

    Handles compatibility between Pydantic v1 (`__fields__`) and v2 (`model_fields`).

    Args:
        model: The Pydantic model class.

    Returns:
        Dict[str, FieldInfo]: A dictionary mapping field names to FieldInfo objects.
    """
    if hasattr(model, 'model_fields'):
        return model.model_fields
    return model.__fields__

def get_pydantic_field_names(model: typing.Type[typing.Union[BaseModel, BaseSettings]]) -> typing.List[str]:
    """Gets a list of field names from a Pydantic model class.

    Args:
        model: The Pydantic model class.

    Returns:
        List[str]: A list of field names.
    """
    return list(get_pydantic_fields_dict(model).keys())

def get_pydantic_fields(model: typing.Type[typing.Union[BaseModel, BaseSettings]]) -> typing.List[FieldInfo]:
    """Gets a list of FieldInfo objects from a Pydantic model class.

    Args:
        model: The Pydantic model class.

    Returns:
        List[FieldInfo]: A list of FieldInfo objects.
    """
    return list(get_pydantic_fields_dict(model).values())

def pydantic_parse_obj(model: typing.Type[typing.Union[BaseModel, BaseSettings]], obj: typing.Any, **kwargs) -> typing.Union[BaseModel, BaseSettings]:
    """Parses an object (e.g., dict) into a Pydantic model instance.

    Handles compatibility between Pydantic v1 (`parse_obj()`) and v2 (`model_validate()`).

    Args:
        model: The Pydantic model class to parse into.
        obj: The object to parse (e.g., a dictionary).
        **kwargs: Additional keyword arguments passed to the parsing method.

    Returns:
        Union[BaseModel, BaseSettings]: An instance of the Pydantic model.
    """
    if hasattr(model, 'model_validate'):
        return model.model_validate(obj, **kwargs)
    return model.parse_obj(obj)

def get_pydantic_schema(model: typing.Type[typing.Union[BaseModel, BaseSettings]], **kwargs) -> typing.Dict[str, typing.Any]:
    """Gets the JSON schema for a Pydantic model class.

    Handles compatibility between Pydantic v1 (`schema()`) and v2 (`model_json_schema()`).

    Args:
        model: The Pydantic model class.
        **kwargs: Keyword arguments passed to the schema generation method.

    Returns:
        Dict[str, Any]: The JSON schema dictionary.
    """
    if hasattr(model, 'model_json_schema'):
        return model.model_json_schema(**kwargs)
    return model.schema(**kwargs)


def get_schema_extra(schema: typing.Dict[str, typing.Any], _):
    """Helper function to filter schema properties.
    
    Removes properties marked as "hidden" or starting with an underscore.
    Note: The second argument `_` seems unused in the original implementation.

    Args:
        schema (Dict[str, Any]): The schema dictionary to process.
        _: Unused argument (present in original signature).

    Returns:
        None: Modifies the schema dictionary in-place.
    """
    props = {
        k: v
        for k, v in schema.get('properties', {}).items()
        if not v.get("hidden", False) and not k.startswith('_')
    }
    schema["properties"] = props
