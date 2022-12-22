import uuid
import json
import typing
import codecs
import datetime
import contextlib
import dataclasses

try:
    import numpy as np
except ImportError:
    np = None

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


def object_serializer(obj: typing.Any) -> typing.Any:
    if isinstance(obj, dict):
        return {k: object_serializer(v) for k, v in obj.items()}

    if isinstance(obj, bytes):
        return obj.decode('utf-8')

    if isinstance(obj, (str, list, dict, int, float, bool, type(None))):
        return obj

    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)

    if hasattr(obj, 'dict'): # test for pydantic models
        return obj.dict()
    
    # Custom dict methods
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    
    if hasattr(obj, 'todict'):
        return obj.todict()
    
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

    if np is not None:
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64)):
            return int(obj)
        
        if isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        
    else:
        # Try to convert to a primitive type
        with contextlib.suppress(Exception):
            return int(obj)
        with contextlib.suppress(Exception):
            return float(obj)

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


class ObjectEncoder(json.JSONEncoder):
    
    def default(self, obj: typing.Any):   # pylint: disable=arguments-differ,method-hidden
        with contextlib.suppress(Exception):
            return object_serializer(obj)
        return json.JSONEncoder.default(self, obj)

class ObjectDecoder(json.JSONDecoder):
    
    def __init__(self, *args, object_hook: typing.Optional[typing.Callable] = None, **kwargs):
        object_hook = object_hook or object_deserializer
        super().__init__(*args, object_hook = object_hook, **kwargs)


class Json:

    @staticmethod
    def dumps(obj: typing.Dict[typing.Any, typing.Any], *args, default: typing.Dict[typing.Any, typing.Any] = None, cls: typing.Type[json.JSONEncoder] = ObjectEncoder, **kwargs) -> str:
        return json.dumps(obj, *args, default = default, cls = cls, **kwargs)

    @staticmethod
    def loads(data: typing.Union[str, bytes], *args, **kwargs) -> typing.Union[typing.Dict[typing.Any, typing.Any], typing.List[str]]:
        return json.loads(data, *args, **kwargs)

