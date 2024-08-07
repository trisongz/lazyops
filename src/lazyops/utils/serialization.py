import uuid
import json
import typing
import codecs
import hashlib
import datetime
import contextlib
import dataclasses
from enum import Enum

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



# try:
#     import ruamel.yaml.scalarstring as yaml
# except ImportError:
#     yaml = None

# Borrowed from httpx
# Null bytes; no need to recreate these on each call to guess_json_utf
_null = b"\x00"
_null2 = _null * 2
_null3 = _null * 3

def guess_json_utf(data: bytes) -> typing.Optional[str]:
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


def parse_list_str(
    line: typing.Optional[typing.Union[typing.List[str], str]],
    default: typing.Optional[typing.List[str]] = None,
    seperators: typing.Optional[typing.List[str]] = None,
) -> typing.Optional[typing.List[str]]:
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
    


def object_serializer(obj: typing.Any) -> typing.Any:
    if isinstance(obj, dict):
        return {k: object_serializer(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [object_serializer(v) for v in obj]    

    if isinstance(obj, bytes):
        return obj.decode('utf-8')
    
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj

    if hasattr(obj, 'dict'): # test for pydantic models
        return obj.dict()
    
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)

    # Custom dict methods
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    
    if hasattr(obj, 'todict'):
        return obj.todict()
    
    if hasattr(obj, 'to_json'):
        return obj.to_json()
    
    if hasattr(obj, 'tojson'):
        return obj.tojson()
    
    if hasattr(obj, 'toJson'):
        return obj.toJson()

    if hasattr(obj, 'json'):
        return obj.json()
    
    if hasattr(obj, 'encode'):
        return obj.encode()

    if hasattr(obj, 'get_secret_value'):
        return obj.get_secret_value()
    
    if hasattr(obj, 'as_posix'):
        return obj.as_posix()
    
    if hasattr(obj, "numpy"):  # Checks for TF tensors without needing the import
        return obj.numpy().tolist()
    
    if hasattr(obj, 'tolist'): # Checks for torch tensors without importing
        return obj.tolist()
    
    # Convert pd datetimes to isoformat
    if isinstance(obj, (datetime.date, datetime.datetime)) or hasattr(obj, 'isoformat'):
        return obj.isoformat()
    
    # Convert UUIDs
    if isinstance(obj, uuid.UUID):
        return str(obj)
    
    if isinstance(obj, Enum): #  hasattr(obj, 'value'):
        return obj.value

    if np is not None:
        # if isinstance(obj, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64)):
        if isinstance(obj, np_int_types):
            return int(obj)
        
        # if isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
        if isinstance(obj, np_float_types):
            return float(obj)

    if isinstance(obj, object):
        with contextlib.suppress(Exception):
            return {k: object_serializer(v) for k, v in obj.__dict__.items()}
    
    
    # Try to convert to a primitive type
    with contextlib.suppress(Exception):
        return int(obj)
    
    with contextlib.suppress(Exception):
        return float(obj)
    
    with contextlib.suppress(Exception):
        return str(obj)


    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def object_deserializer(obj: typing.Dict) -> typing.Dict:
    results = {}

    for key, value in obj.items():
        
        if isinstance(value, bytes):
            encoding = guess_json_utf(value)
            results[key] = value.decode(encoding) if encoding is not None else value
            continue

        if isinstance(value, dict):
            results[key] = object_deserializer(value)
            continue

        for dt_key in {
            'created',
            'updated',
            'modified',
            'timestamp',
            'date',
        }:
            if dt_key in key:
                if isinstance(value, str):
                    with contextlib.suppress(Exception):
                        results[key] = datetime.datetime.strptime(value, '%a, %d %b %Y %H:%M:%S GMT')
                        continue
                    with contextlib.suppress(Exception):
                        results[key] = datetime.datetime.fromisoformat(value)
                        continue
                
                with contextlib.suppress(Exception):
                    results[key] = datetime.datetime.fromtimestamp(value, tz = datetime.timezone.utc)
                    continue


        results[key] = value
    return results


if typing.TYPE_CHECKING:
    from lazyops.types import BaseModel

from .lazy import lazy_import, get_obj_class_name

def object_model_serializer(obj: typing.Union['BaseModel', typing.Any]) -> typing.Any:
    """
    Hooks for the object serializer for BaseModels
    """
    if not hasattr(obj, "Config") and not hasattr(obj, "dict"):
        return object_serializer(obj)
    return {
        "__jsontype__": "model",
        "__model__": get_obj_class_name(obj),
        "__data__": obj.dict(),
    }


def object_model_deserializer(obj: typing.Any) -> typing.Union['BaseModel', typing.Any]:
    """
    Hooks for the object deserializer for BaseModels
    """
    if not isinstance(obj, dict): return obj
    if any(key not in obj for key in ["__jsontype__", "__model__", "__data__"]):
        return object_deserializer(obj)

    
    model = lazy_import(obj["__model__"])
    return model(**obj["__data__"])


class ObjectEncoder(json.JSONEncoder):
    
    def default(self, obj: typing.Any):   # pylint: disable=arguments-differ,method-hidden
        with contextlib.suppress(Exception):
           return object_serializer(obj)
        # try:
        #     return object_serializer(obj)
        # except TypeError:
        #     print(f"Object of type {type(obj)} is not JSON serializable: {obj}")
        return json.JSONEncoder.default(self, obj)

class ObjectDecoder(json.JSONDecoder):
    
    def __init__(self, *args, object_hook: typing.Optional[typing.Callable] = None, **kwargs):
        object_hook = object_hook or object_deserializer
        super().__init__(*args, object_hook = object_hook, **kwargs)

class ObjectModelEncoder(json.JSONEncoder):
    """
    Object Model Encoder
    """
    def default(self, obj: typing.Any):   # pylint: disable=arguments-differ,method-hidden
        with contextlib.suppress(Exception):
            return object_model_serializer(obj)
        return json.JSONEncoder.default(self, obj)
        
class ObjectModelDecoder(json.JSONDecoder):
    """
    Object Model Decoder
    """
    def __init__(self, *args, object_hook: typing.Optional[typing.Callable] = None, **kwargs):
        object_hook = object_hook or object_model_deserializer
        super().__init__(*args, object_hook = object_hook, **kwargs)


class Json:

    @staticmethod
    def dumps(
        obj: typing.Dict[typing.Any, typing.Any], 
        *args, 
        default: typing.Dict[typing.Any, typing.Any] = None, 
        cls: typing.Type[json.JSONEncoder] = ObjectEncoder,
        _fallback_method: typing.Optional[typing.Callable] = None,
        **kwargs
    ) -> str:
        try:
            return json.dumps(obj, *args, default = default, cls = cls, **kwargs)
        except Exception as e:
            if _fallback_method is not None:
                return _fallback_method(obj, *args, default = default, **kwargs)
            raise e

    @staticmethod
    def loads(
        data: typing.Union[str, bytes], 
        *args, 
        _fallback_method: typing.Optional[typing.Callable] = None,
        **kwargs
    ) -> typing.Union[typing.Dict[typing.Any, typing.Any], typing.List[str]]:
        try:
            return json.loads(data, *args, **kwargs)
        except json.JSONDecodeError as e:
            if _fallback_method is not None:
                return _fallback_method(data, *args, **kwargs)
            raise e

class JsonModelSerializer:

    """
    Encoder and Decoder for Pydantic Models
    for optimal performance in deep serialization
    """

    @staticmethod
    def dumps(
        obj: typing.Dict[typing.Any, typing.Any], 
        *args, 
        default: typing.Dict[typing.Any, typing.Any] = None, 
        cls: typing.Type[json.JSONEncoder] = ObjectModelEncoder,
        _fallback_method: typing.Optional[typing.Callable] = None,
        **kwargs
    ) -> str:
        """
        Serializes a dict into a JSON string using the ObjectModelEncoder
        """
        try:
            return json.dumps(obj, *args, default = default, cls = cls, **kwargs)
        except Exception as e:
            if _fallback_method is not None:
                return _fallback_method(obj, *args, default = default, **kwargs)
            raise e

    @staticmethod
    def loads(
        data: typing.Union[str, bytes], 
        *args, 
        cls: typing.Type[json.JSONDecoder] = ObjectModelDecoder,
        _fallback_method: typing.Optional[typing.Callable] = None,
        **kwargs
    ) -> typing.Union[typing.Dict[typing.Any, typing.Any], typing.List[str]]:
        """
        Loads a JSON string into a dict using the ObjectModelDecoder
        """
        try:
            return json.loads(data, *args, cls = cls, **kwargs)
        except json.JSONDecodeError as e:
            if _fallback_method is not None:
                return _fallback_method(data, *args, **kwargs)
            raise e

# Add simdjson support if available
try:
    import simdjson

    _parser = simdjson.Parser()

    class SimdJson:

        """
        JSON Encoder and Decoder using simdjson
        """
        parser = _parser

        @staticmethod
        def dumps(
            obj: typing.Dict[typing.Any, typing.Any], 
            *args, 
            default: typing.Dict[typing.Any, typing.Any] = None, 
            cls: typing.Type[json.JSONEncoder] = None,
            _fallback_method: typing.Optional[typing.Callable] = None,
            **kwargs
        ) -> str:
            """
            Serializes a dict into a JSON string
            """
            try:
                return simdjson.dumps(obj, *args, default = default, cls = cls, **kwargs)
            except Exception as e:
                if _fallback_method is not None:
                    return _fallback_method(obj, *args, default = default, **kwargs)
                raise e

        @staticmethod
        def loads(
            data: typing.Union[str, bytes], 
            *args, 
            object_hook: typing.Optional[typing.Callable] = None,
            recursive: typing.Optional[bool] = True,
            _raw: typing.Optional[bool] = False,
            _fallback_method: typing.Optional[typing.Callable] = None,
            **kwargs
        ) -> typing.Union[typing.Dict[typing.Any, typing.Any], typing.List[str], simdjson.Object, simdjson.Array]:
            """
            Loads a JSON string into a dict using the ObjectModelDecoder
            """
            try:
                value = _parser.parse(data, recursive)
                return value if _raw or not object_hook else object_hook(value)
            
            except Exception as e:
                if _fallback_method is not None:
                    return _fallback_method(data, *args, **kwargs)
                raise e


    class SimdJsonModelSerializer:

        """
        JSON Encoder and Decoder using simdjson
        """

        parser = _parser

        @staticmethod
        def dumps(
            obj: typing.Dict[typing.Any, typing.Any], 
            *args, 
            default: typing.Dict[typing.Any, typing.Any] = None, 
            cls: typing.Type[json.JSONEncoder] = ObjectModelEncoder,
            _fallback_method: typing.Optional[typing.Callable] = None,
            **kwargs
        ) -> str:
            """
            Serializes a dict into a JSON string using the ObjectModelEncoder
            """
            try:
                return simdjson.dumps(obj, *args, default = default, cls = cls, **kwargs)
            except Exception as e:
                if _fallback_method is not None:
                    return _fallback_method(obj, *args, default = default, **kwargs)
                raise e

        @staticmethod
        def loads(
            data: typing.Union[str, bytes], 
            *args, 
            object_hook: typing.Optional[typing.Callable] = object_model_deserializer,
            recursive: typing.Optional[bool] = True,
            _raw: typing.Optional[bool] = False,
            _fallback_method: typing.Optional[typing.Callable] = None,
            **kwargs
        ) -> typing.Union[typing.Dict[typing.Any, typing.Any], typing.List[str], 'BaseModel', simdjson.Object, simdjson.Array]:
            """
            Loads a JSON string into a dict using the ObjectModelDecoder
            """
            try:
                value = _parser.parse(data, recursive)
                return value if _raw or not object_hook else object_hook(value)
            
            except Exception as e:
                if _fallback_method is not None:
                    return _fallback_method(data, *args, **kwargs)
                raise e



except ImportError:
    _parser = None

    SimdJson = Json
    SimdJsonModelSerializer = JsonModelSerializer



"""
Hashing Functions
"""


def create_hash_key(
    args: typing.Optional[tuple] = None, 
    kwargs: typing.Optional[dict] = None, 
    typed: typing.Optional[bool] = False,
    key_base: typing.Optional[tuple] = None,
    exclude: typing.Optional[typing.List[str]] = None,
    hashfunc: typing.Optional[str] = 'md5',
    separator: typing.Optional[str] = ':',
):
    """
    Create hash key out of function arguments.
    :param tuple base: base of key
    :param tuple args: function arguments
    :param dict kwargs: function keyword arguments
    :param bool typed: include types in cache key
    :return: cache key tuple
    """

    hash_key = key_base or ()
    if args: hash_key += args
    if kwargs:
        if exclude: kwargs = {k: v for k, v in kwargs.items() if k not in exclude}
        sorted_items = sorted(kwargs.items())
        for item in sorted_items:
            hash_key += item

    if typed:
        hash_key += tuple(type(arg) for arg in args)
        if kwargs: hash_key += tuple(type(value) for _, value in sorted_items)

    cache_key = f'{separator}'.join(str(k) for k in hash_key)
    func = getattr(hashlib, hashfunc)
    return func(cache_key.encode()).hexdigest()

