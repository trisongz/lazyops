"""
Serialization Utilities
"""

import abc
import datetime
import dataclasses
import contextlib
from uuid import UUID
from enum import Enum
from lzl.logging import logger
from lzl.load import lazy_import
from lzl.types import BaseModel, Literal
from .defaults import default_pickle
from typing import Optional, Union, Any, Dict, List, Tuple, Callable, Type, Mapping, TypeVar, TYPE_CHECKING

try:
    import numpy as np
    np_version = np.__version__
    if np_version.startswith("2."):
        np_float_types = (np.float16, np.float32, np.float64)
    else:
        np_float_types = (np.float_, np.float16, np.float32, np.float64)
    np_int_types = (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64)
    
except ImportError:
    np = None


SerMode = Literal['auto', 'raw']

SerializableObject = TypeVar('SerializableObject')
serialization_class_registry: Dict[str, Type[SerializableObject]] = {}

_alias_schema_mapping: Dict[str, str] = {}

def is_primitive(value, exclude_bytes: Optional[bool] = False) -> bool:
    """
    Check if a value is a primitive type
    """
    if exclude_bytes and isinstance(value, bytes): return False
    return isinstance(value, (int, float, bool, str, bytes, type(None)))


def get_object_classname(obj: SerializableObject, is_type: Optional[bool] = False) -> str:
    """
    Get the classname of an object
    """
    if is_type: return f'{obj.__module__}.{obj.__name__}'
    return f"{obj.__class__.__module__}.{obj.__class__.__name__}"

def get_object_class(name: str) -> Type[SerializableObject]:
    """
    Get the class of an object
    """
    global serialization_class_registry
    if name not in serialization_class_registry:
        serialization_class_registry[name] = lazy_import(name)
    return serialization_class_registry[name]

def register_object_class(obj: SerializableObject, is_type: Optional[bool] = False) -> str:
    """
    Register the object class
    """
    global serialization_class_registry
    obj_class_name = get_object_classname(obj, is_type = is_type)
    if obj_class_name not in serialization_class_registry:
        serialization_class_registry[obj_class_name] = obj if is_type else obj.__class__
    return obj_class_name

def register_schema_mapping(schemas: Dict[str, str]):
    """
    Register the schema mapping
    """
    global _alias_schema_mapping
    _alias_schema_mapping.update(schemas)


def serialize_object(
    obj: SerializableObject,
    mode: Optional[SerMode] = 'auto',
    **kwargs
) -> Union[Dict[str, Any], List[Dict[str, Any]], Any]:
    # sourcery skip: extract-duplicate-method
    """
    Helper to serialize an object

    Args:
        obj: the object to serialize

    Returns:
        the serialized object in dict
        
        if not disable_nested_values:
        {
            "__type__": ...,
            "value": ...,
        }

        otherwise for JSON Objects:

        {
            "__type__": ...,
            ...,
        }

    """
    if obj is None: return None
    disable_nested_values: Optional[bool] = kwargs.get('disable_nested_values')

    if isinstance(obj, BaseModel) or hasattr(obj, 'model_dump'):
        obj_class_name = register_object_class(obj)
        obj_value = obj.model_dump(mode = 'json', round_trip = True, **kwargs)
        if mode == 'raw': return obj_value
        if disable_nested_values:
            return {
                "__type__": "pydantic",
                "__class__": obj_class_name,
                **obj_value,
            }
        return {
            "__type__": "pydantic",
            "__class__": obj_class_name,
            "value": obj_value,
        }

    # Move this to the top before primitives
    if np is not None:
        # if isinstance(obj, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64)):
        if isinstance(obj, np_int_types):
            if mode == 'raw': return int(obj)
            obj_class_name = register_object_class(obj)
            return {
                "__type__": "numpy",
                "__class__": obj_class_name,
                "value": int(obj),
            }


        # if isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
        if isinstance(obj, np_float_types):
            if mode == 'raw': return float(obj)
            obj_class_name = register_object_class(obj)
            return {
                "__type__": "numpy",
                "__class__": obj_class_name,
                "value": float(obj),
            }


    if is_primitive(obj, exclude_bytes = True):
        return obj
    
    if isinstance(obj, type):
        obj_class_name = register_object_class(obj, is_type = True)
        if mode == 'raw': return obj_class_name
        return {
            "__type__": "type",
            "__class__": obj_class_name,
            "value": obj_class_name,
        }

    if isinstance(obj, (list, tuple)):
        return [serialize_object(item, mode = mode, **kwargs) for item in obj]

    if isinstance(obj, dict):
        if "__type__" in obj: 
            return obj['value'] if mode == 'raw' and obj.get('value') else obj
        return {key: serialize_object(value, mode = mode, **kwargs) for key, value in obj.items()}

    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        if mode == 'raw': return obj.isoformat()
        return {
            "__type__": "datetime",
            "value": obj.isoformat(),
        }

    if isinstance(obj, datetime.timedelta):
        if mode == 'raw': return obj.total_seconds()
        return {
            "__type__": "timedelta",
            "value": obj.total_seconds(),
        }

    if isinstance(obj, dataclasses.InitVar) or dataclasses.is_dataclass(obj):
        if mode == 'raw': return dataclasses.asdict(obj)
        obj_class_name = register_object_class(obj)
        if disable_nested_values:
            return {
                "__type__": "dataclass",
                "__class__": obj_class_name,
                **dataclasses.asdict(obj),
            }
        return {
            "__type__": "dataclass",
            "__class__": obj_class_name,
            "value": dataclasses.asdict(obj),
        }

    if hasattr(obj, 'as_posix'):
        if mode == 'raw': return obj.as_posix()
        obj_class_name = register_object_class(obj)
        return {
            "__type__": "path",
            "__class__": obj_class_name,
            "value": obj.as_posix(),
        }

    if isinstance(obj, (bytes, bytearray)):
        if mode == 'raw': return obj
        return {
            "__type__": "bytes",
            "value": obj.hex(),
        }

    if isinstance(obj, (set, frozenset)):
        if mode == 'raw': return list(obj)
        return {
            "__type__": "set",
            "value": list(obj),
        }

    if isinstance(obj, Enum):
        if mode == 'raw': return obj.value
        obj_class_name = register_object_class(obj)
        return {
            "__type__": "enum",
            "__class__": obj_class_name,
            "value": obj.value,
        }

    if isinstance(obj, UUID):
        if mode == 'raw': return str(obj)
        return {
            "__type__": "uuid",
            "value": str(obj),
        }

    if hasattr(obj, 'serialize'):
        if mode == 'raw': return obj.serialize()
        obj_class_name = register_object_class(obj)
        return {
            "__type__": "serializable",
            "__class__": obj_class_name,
            "value": obj.serialize(),
        }

    if isinstance(obj, abc.ABC):
        logger.info(f'Pickle Serializing ABC Object: |r|({type(obj)}) {str(obj)[:1000]}', colored = True)
        # if mode == 'raw': raise TypeError(f"Cannot serialize object of type in raw mode {type(obj)}")
        obj_bytes = default_pickle.dumps(obj)
        if mode == 'raw': return obj_bytes
        return {
            "__type__": "pickle",
            "value": obj_bytes.hex(),
        }


    if hasattr(obj, "numpy"):  # Checks for TF tensors without needing the import
        if mode == 'raw': return obj.numpy().tolist()
        return {
            "__type__": "tensor",
            "value": obj.numpy().tolist(),
        }

    if hasattr(obj, 'tolist'): # Checks for torch tensors without importing
        if mode == 'raw': return obj.tolist()
        return {
            "__type__": "tensor",
            "value": obj.tolist(),
        }

    # Try one shot encoding objects
    # with contextlib.suppress(Exception):

    try:
        logger.info(f'Pickle Serializing Object: |r|({type(obj)}) {str(obj)[:1000]}', colored = True)
        obj_bytes = default_pickle.dumps(obj)
        if mode == 'raw': return obj_bytes
        return {
            "__type__": "pickle",
            "value": obj_bytes.hex(),
        }
    except Exception as e:

        logger.info(f'Error Serializing Object: |r|({type(obj)}) {e}|e| {str(obj)[:1000]}', colored = True)

    raise TypeError(f"Cannot serialize object of type {type(obj)}")


def deserialize_object(
    obj: Union[Dict[str, Any], List[Dict[str, Any]], Any], 
    schema_map: Optional[Dict[str, str]] = None, 
    allow_failed_import: Optional[bool] = False
) -> SerializableObject:
    # sourcery skip: extract-duplicate-method, low-code-quality
    """
    Deserialize an object

    Args:
        obj: the object to deserialize
    """
    if obj is None: return None
    if isinstance(obj, (list, tuple)):
        return [deserialize_object(item, schema_map = schema_map, allow_failed_import = allow_failed_import) for item in obj]

    if isinstance(obj, dict):
        if "__type__" not in obj:
            return {key: deserialize_object(value, schema_map = schema_map, allow_failed_import = allow_failed_import) for key, value in obj.items()}

        # obj_type = obj["__type__"]
        obj_type = obj.pop("__type__")
        if '__class__' in obj:
            if schema_map is not None and obj['__class__'] in schema_map:
                obj['__class__'] = schema_map[obj['__class__']]
            elif obj['__class__'] in _alias_schema_mapping:
                obj['__class__'] = _alias_schema_mapping[obj['__class__']]
        
        obj_class_type = obj.pop('__class__', None)
        if obj_type == "type":
            return get_object_class(obj_class_type)
        
        obj_value = obj["value"] if len(obj) == 1 and "value" in obj else obj
        if obj_type == "pydantic":
            try:
                obj_class = get_object_class(obj_class_type)
                # for k,v in obj_value.items():
                #     if not is_primitive(v):
                #         obj_value[k] = deserialize_object(v)
                return obj_class(**obj_value)
            except ImportError as e:
                if allow_failed_import:
                    return deserialize_object(obj_value, schema_map = schema_map, allow_failed_import = allow_failed_import)
                raise e

        if obj_type == "serializable":
            try:
                obj_class = get_object_class(obj_class_type)
                return obj_class(**obj_value)
            except ImportError as e:
                if allow_failed_import:
                    return deserialize_object(obj_value, schema_map = schema_map, allow_failed_import = allow_failed_import)
                raise e

        if obj_type == "numpy" and np is not None:
            # dtype = obj.get("__class__")
            dtype = obj_class_type
            if dtype: dtype = dtype.replace("numpy.", "")
            return np.array(obj_value, dtype = dtype)

        if obj_type == "pickle":
            try:
                obj_value = bytes.fromhex(obj_value)
                return default_pickle.loads(obj_value)
            except Exception as e:
                raise TypeError(f"Cannot deserialize object of type {obj_type}: {e}") from e

        if obj_type == "datetime":
            return datetime.datetime.fromisoformat(obj_value)

        if obj_type == "timedelta":
            return datetime.timedelta(seconds=obj_value)

        if obj_type == "dataclass":
            # obj_class_type = obj["__class__"]
            # if schema_map is not None and obj_class_type in schema_map:
            #     obj_class_type = schema_map[obj_class_type]

            obj_class = get_object_class(obj_class_type)
            return obj_class(**obj_value)

        if obj_type == "path":
            obj_class = get_object_class(obj_class_type)
            return obj_class(obj_value)

        if obj_type == "enum":
            obj_class = get_object_class(obj_class_type)
            return obj_class(obj_value)

        if obj_type == "uuid":
            return UUID(obj_value)

        if obj_type == "bytes":
            return bytes.fromhex(obj_value)

        if obj_type == "set":
            return set(obj_value)

        raise TypeError(f"Cannot deserialize object of type {obj_type}")

    if isinstance(obj, bytes):
        # Try to deserialize with pickle
        with contextlib.suppress(Exception):
            return default_pickle.loads(obj)

    return obj



