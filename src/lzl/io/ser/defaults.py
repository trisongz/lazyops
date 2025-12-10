from __future__ import annotations

import json
from typing import TypeVar

# try:
#     import orjson
#     _orjson_available = True
# except ImportError:
#     _orjson_available = False

try:
    import simdjson
    from .bindings import _simdjson
    _simdjson_available = True
except ImportError:
    _simdjson_available = False

try:
    import cysimdjson
    from .bindings import _cysimdjson
    _cysimdjson_available = True
except ImportError:
    _cysimdjson_available = False

try:
    import ujson
    _ujson_available = True
except ImportError:
    _ujson_available = False


if _simdjson_available:
    # default_json = simdjson
    default_json = _simdjson

elif _cysimdjson_available:
    default_json = _cysimdjson

# elif _orjson_available:
#     default_json = orjson

elif _ujson_available:
    default_json = ujson

else:
    default_json = json

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

try:
    import msgpack
    _msgpack_available = True
    default_msgpack = msgpack
except ImportError:
    _msgpack_available = False
    default_msgpack = None



JsonLibT = TypeVar("JsonLibT")
PickleLibT = TypeVar("PickleLibT")
MsgPackLibT = TypeVar("MsgPackLibT")
