import json
import typing
import datetime
from enum import Enum
from sqlalchemy import inspect
from lazyops.utils.serialization import object_serializer, Json
from sqlalchemy.ext.declarative import DeclarativeMeta
from pydantic import create_model, BaseModel, Field
from typing import Optional, Dict, Any, List, Union, Type


# https://stackoverflow.com/questions/5022066/how-to-serialize-sqlalchemy-result-to-json

class AlchemyEncoder(json.JSONEncoder):

    def default(self, obj):
        if not isinstance(obj.__class__, DeclarativeMeta):
            return json.JSONEncoder.default(self, obj)
        # an SQLAlchemy class
        fields = {}
        for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata']:
            data = obj.__getattribute__(field)
            try:
                json.dumps(data) # this will fail on non-encodable values, like other classes
                fields[field] = data
            except TypeError:
                fields[field] = None
        # a json-encodable dict
        return fields

class SQLJson(Json):

    @staticmethod
    def dumps(
        obj: typing.Dict[typing.Any, typing.Any], 
        *args, 
        default: typing.Dict[typing.Any, typing.Any] = None, 
        cls: typing.Type[json.JSONEncoder] = AlchemyEncoder,
        _fallback_method: typing.Optional[typing.Callable] = None,
        **kwargs
    ) -> str:
        try:
            return json.dumps(obj, *args, default = default, cls = cls, **kwargs)
        except Exception as e:
            if _fallback_method is not None:
                return _fallback_method(obj, *args, default = default, **kwargs)
            raise e


_pydantic_models: Dict[str, Type[BaseModel]] = {}


class BasePydanticConfig:
    orm_mode = True
    json_encoders = {
        datetime.datetime: lambda v: v.isoformat(),
        Enum: lambda v: v.value,
    }
    json_loads = Json.loads
    json_dumps = Json.dumps


def get_pydantic_model(obj: object) -> Type[BaseModel]:
    """
    Create a pydantic model from a sqlalchemy model
    """
    global _pydantic_models
    obj_class_name = f'{obj.__class__.__module__}.{obj.__class__.__name__}Model'
    if obj_class_name not in _pydantic_models:
        fields = {
            c.key: (type(getattr(obj, c.key)), Field(None))
            for c in inspect(obj).mapper.column_attrs
        }
        _pydantic_models[obj_class_name] = create_model(
            f'{obj.__class__.__name__}Model',
            __config__ = BasePydanticConfig,
            __module__=obj.__class__.__module__,
            **fields,
        )
        # logger.info(f'Created pydantic model for {obj_class_name}: {_pydantic_models[obj_class_name]}: {fields}')
    # return _pydantic_models[obj_class_name](**obj.dict())
    return _pydantic_models[obj_class_name].from_orm(obj)


def dict_diff(dict_a: Union[Dict[str, Any], Type[BaseModel]], dict_b: Union[Dict[str, Any], Type[BaseModel]], show_value_diff: bool = True):
    
    """
    Compare two dictionaries and return the difference between them
    """
    if not isinstance(dict_a, dict) and hasattr(dict_a, 'dict'):
        dict_a = dict_a.dict()
    if not isinstance(dict_b, dict) and hasattr(dict_b, 'dict'):
        dict_b = dict_b.dict()
    result = {
        'added': {k: dict_b[k] for k in set(dict_b) - set(dict_a)},
        'removed': {k: dict_a[k] for k in set(dict_a) - set(dict_b)},
    }
    if show_value_diff:
        common_keys =  set(dict_a) & set(dict_b)
        result['value_diffs'] = {
            k:(dict_a[k], dict_b[k])
            for k in common_keys
            if dict_a[k] != dict_b[k]
        }
    return result