import json
import typing
import datetime
import contextlib
from enum import Enum
from sqlalchemy import inspect
from lazyops.utils.serialization import object_serializer, Json
from sqlalchemy.ext.declarative import DeclarativeMeta
from pydantic import create_model, BaseModel, Field
from typing import Optional, Dict, Any, List, Union, Type, cast


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
_json_encoders = {
    datetime.datetime: lambda v: v.isoformat(),
    Enum: lambda v: v.value
}
with contextlib.suppress(ImportError):
    import numpy as np
    _json_encoders[np.ndarray] = lambda v: v.tolist()
    _json_encoders[np.int64] = lambda v: int(v)
    _json_encoders[np.float64] = lambda v: float(v)


class BasePydanticConfig:
    orm_mode = True
    arbitrary_types_allowed = True
    json_encoders = _json_encoders
    json_loads = Json.loads
    json_dumps = Json.dumps
    extra = 'allow'

# from lazyops.utils import logger

def cast_to_optional(t: Type[Any]) -> Optional[Type[Any]]:
    """
    Cast a type to an optional type
    """
    # logger.warning(f'Cast to optional: {t}')
    # if isinstance(t, None):
    if t == type(None):
        # Turn it into Any
        # logger.warning(f'Cast to optional from none: {t}')
        return Optional[Any]
    if isinstance(t, type):
        return Optional[t]
    return Optional[t[0]] if isinstance(t, list) else Optional[t.__args__[0]]

def get_sqlmodel_dict(obj: DeclarativeMeta) -> Dict[str, Any]:
    """
    Return a dictionary representation of a sqlalchemy model
    """
    return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}

def get_model_fields(obj: DeclarativeMeta) -> Dict[str, Any]:
    """
    Return a dictionary representation of a sqlalchemy model
    """
    fields = {}
    for c in inspect(obj).mapper.column_attrs:
        # logger.warning(f'Cast to optional: {c.key}')
        fields[c.key] = (cast_to_optional(type(getattr(obj, c.key))), Field(None))
    # map relationships
    # for r in inspect(obj).mapper.relationships:
    # for r in obj.__mapper__.relationships:
    #     if r.mapper.class_ == obj.__class__: continue
    #     # determine if the relationship is a parent
    #     # if it is, then we don't need to create a model for it
    #     if r.direction.name == 'MANYTOONE':
    #         logger.warning(f'Skip Cast to optional: {r.key}: {r.uselist} {r.mapper.class_} {r.direction.name}')
    #         # fields[r.key] = (cast_to_optional(type(getattr(obj, r.key))), Field(None))
    #         continue
    #     logger.warning(f'Cast to optional: {r.key}: {r.uselist} {r.mapper.class_} {r.direction.name} {r}')
    #     base_type = build_pydantic_model(r.mapper.class_)
    #     if r.uselist:
    #         fields[r.key] = (cast_to_optional(List[base_type]), Field(None))
    #     else:
    #         fields[r.key] = (cast_to_optional(base_type), Field(None))
        # fields[r.key] = (cast_to_optional(List[get_pydantic_model(r.mapper.class_)]), Field(None))
    return fields

def build_pydantic_model(obj: DeclarativeMeta) -> Type[BaseModel]:
    """
    Create a pydantic model from a sqlalchemy model
    """
    global _pydantic_models
    
    obj_class_name = f'{obj.__class__.__module__}.{obj.__class__.__name__}Model'
    if obj_class_name not in _pydantic_models:
        # fields = {
        #     c.key: (cast_to_optional(type(getattr(obj, c.key))), Field(None))
        #     for c in inspect(obj).mapper.column_attrs
        # }
        fields = get_model_fields(obj)
        # logger.info(f'Creating pydantic model for {obj_class_name}: {fields}')
        _pydantic_models[obj_class_name] = create_model(
            f'{obj.__class__.__name__}Model',
            __config__ = BasePydanticConfig,
            __module__=obj.__class__.__module__,
            **fields,
        )
    return _pydantic_models[obj_class_name]


def get_pydantic_model(obj: object) -> Type[BaseModel]:
    """
    Create a pydantic model from a sqlalchemy model
    """
    # obj_class_name = f'{obj.__class__.__module__}.{obj.__class__.__name__}Model'
    return build_pydantic_model(obj).from_orm(obj)

    # global _pydantic_models
    
    # obj_class_name = f'{obj.__class__.__module__}.{obj.__class__.__name__}Model'
    # if obj_class_name not in _pydantic_models:
    #     # fields = {
    #     #     c.key: (cast_to_optional(type(getattr(obj, c.key))), Field(None))
    #     #     for c in inspect(obj).mapper.column_attrs
    #     # }
    #     fields = get_model_fields(obj)
    #     # logger.info(f'Creating pydantic model for {obj_class_name}: {fields}')
    #     _pydantic_models[obj_class_name] = create_model(
    #         f'{obj.__class__.__name__}Model',
    #         __config__ = BasePydanticConfig,
    #         __module__=obj.__class__.__module__,
    #         **fields,
    #     )
    #     # logger.info(f'Created pydantic model for {obj_class_name}: {_pydantic_models[obj_class_name]}: {fields}')
    # # return _pydantic_models[obj_class_name](**obj.dict())
    # # print(_pydantic_models[obj_class_name].__fields__)
    # return _pydantic_models[obj_class_name].from_orm(obj)


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