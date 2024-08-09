"""
Serialization Utilities
"""

import abc
import json
import codecs
import datetime
import dataclasses
import contextlib
from uuid import UUID
from enum import Enum
from lzl.logging import logger
from lzl.load import lazy_import
from lzl.types import BaseModel
from typing import Optional, Union, Any, Dict, List, Tuple, Callable, Type, Mapping, TypeVar, Literal, TYPE_CHECKING

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

import pickle
try:
    import cloudpickle
    _cloudpicke_available = True
except ImportError:
    _cloudpicke_available = False

try:
    import dill
    _dill_available = True
except ImportError:
    _dill_available = False

if _cloudpicke_available:
    default_pickle = cloudpickle
elif _dill_available:
    default_pickle = dill
else:
    default_pickle = pickle

SerMode = Literal['auto', 'raw']
SerializableObject = TypeVar('SerializableObject')
serialization_class_registry: Dict[str, Type[SerializableObject]] = {}

_alias_schema_mapping: Dict[str, str] = {}
_null = b"\x00"
_null2 = _null * 2
_null3 = _null * 3

def guess_json_utf(data: bytes) -> Optional[str]:
    # JSON always starts with two ASCII characters, so detection is as
    # easy as counting the nulls and from their location and count
    # determine the encoding. Also detect a BOM, if present.
    sample = data[:4]
    if sample in (codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE):
        return "utf-32"  # BOM included
    if sample[:3] == codecs.BOM_UTF8:
        return "utf-8-sig"  # BOM included, MS style (discouraged)
    if sample[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
        return "utf-16"  # BOM included
    nullcount = sample.count(_null)
    if nullcount == 0:
        return "utf-8"
    if nullcount == 2:
        if sample[::2] == _null2:  # 1st and 3rd are null
            return "utf-16-be"
        if sample[1::2] == _null2:  # 2nd and 4th are null
            return "utf-16-le"
    elif nullcount == 3:
        if sample[:3] == _null3:
            return "utf-32-be"
        if sample[1:] == _null3:
            return "utf-32-le"
    return None


def is_primitive(value, exclude_bytes: Optional[bool] = False) -> bool:
    """
    Check if a value is a primitive type
    """
    if exclude_bytes and isinstance(value, bytes): return False
    return isinstance(value, (int, float, bool, str, bytes, type(None)))


def get_object_classname(obj: SerializableObject) -> str:
    """
    Get the classname of an object
    """
    return f"{obj.__class__.__module__}.{obj.__class__.__name__}"

def get_object_class(name: str) -> Type[SerializableObject]:
    """
    Get the class of an object
    """
    global serialization_class_registry
    if name not in serialization_class_registry:
        serialization_class_registry[name] = lazy_import(name)
    return serialization_class_registry[name]

def register_object_class(obj: SerializableObject) -> str:
    """
    Register the object class
    """
    global serialization_class_registry
    obj_class_name = get_object_classname(obj)
    if obj_class_name not in serialization_class_registry:
        serialization_class_registry[obj_class_name] = obj.__class__
    return obj_class_name

def register_schema_mapping(schemas: Dict[str, str]):
    """
    Register the schema mapping
    """
    global _alias_schema_mapping
    _alias_schema_mapping.update(schemas)


def parse_list_str(
    line: Optional[Union[List[str], str]],
    default: Optional[List[str]] = None,
    seperators: Optional[List[str]] = None,
) -> Optional[List[str]]:
    """
    Try to parse a string as a list of strings

    Args:
        line (typing.Optional[typing.Union[typing.List[str], str]]): [description]
        default (typing.Optional[typing.List[str]], optional): [description]. Defaults to None.
        seperators (typing.Optional[typing.List[str]], optional): [description]. Defaults to None.
    
    """
    if line is None: return default
    if seperators is None: seperators = [',', '|', ';']
    if isinstance(line, list): return line
    if isinstance(line, str):
        if '[' in line and ']' in line:
            if '"' in line or "'" in line:
                try:
                    line = json.loads(line)
                    return line
                except Exception: line = line.replace("'", '').replace('"', '')
            line = line.replace('[', '').replace(']', '')
        for seperator in seperators:
            if seperator in line:
                return line.split(seperator)
        line = [line]
    return line
    

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
        {
            "__type__": ...,
            "value": ...,
        }
    """
    if obj is None: return None

    if isinstance(obj, BaseModel) or hasattr(obj, 'model_dump'):
        obj_class_name = register_object_class(obj)
        obj_value = obj.model_dump(mode = 'json', round_trip = True, **kwargs)
        if mode == 'raw': return obj_value
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
        
        obj_type = obj["__type__"]
        obj_value = obj["value"]
        if '__class__' in obj:
            if schema_map is not None and obj['__class__'] in schema_map:
                obj['__class__'] = schema_map[obj['__class__']]
            elif obj['__class__'] in _alias_schema_mapping:
                obj['__class__'] = _alias_schema_mapping[obj['__class__']]
            
        if obj_type == "pydantic":
            obj_class_type = obj["__class__"]
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
        
        if obj_type == "numpy" and np is not None:
            dtype = obj.get("__class__")
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
            obj_class_type = obj["__class__"]
            # if schema_map is not None and obj_class_type in schema_map:
            #     obj_class_type = schema_map[obj_class_type]
            
            obj_class = get_object_class(obj_class_type)
            return obj_class(**obj_value)
        
        if obj_type == "path":
            obj_class = get_object_class(obj["__class__"])
            return obj_class(obj_value)
        
        if obj_type == "enum":
            obj_class = get_object_class(obj["__class__"])
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



