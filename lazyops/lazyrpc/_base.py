# Has all the base dependencies

from lazyops import lazy_init, get_logger

lazy_init('fastapi')
lazy_init('pydantic')
lazy_init('aiojobs')
lazy_init('starlette')

import asyncio
import inspect
import contextvars

from collections import ChainMap
from json import JSONDecodeError
from types import FunctionType, CoroutineType
from typing import List, Union, Any, Callable, Type, Optional, Dict, Sequence, Awaitable, Tuple
from contextlib import AsyncExitStack, AbstractAsyncContextManager, asynccontextmanager, contextmanager

# noinspection PyProtectedMember
from pydantic import DictError
from pydantic import StrictStr, ValidationError
from pydantic import BaseModel as PyBaseModel
from pydantic import BaseConfig
from pydantic.fields import ModelField, Field
from pydantic.main import ModelMetaclass

# noinspection PyProtectedMember
from fastapi.dependencies.models import Dependant
from fastapi.encoders import jsonable_encoder
from fastapi.params import Depends
from fastapi import FastAPI, Body, Header
from fastapi.dependencies.utils import solve_dependencies, get_dependant, get_flat_dependant, get_parameterless_sub_dependant
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.routing import APIRoute, APIRouter, serialize_response

from starlette.background import BackgroundTasks
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response
from starlette.responses import JSONResponse as BaseJSONResponse
from starlette.routing import Match, request_response, compile_path

import aiojobs
import fastapi.params
import simdjson as json

logger = get_logger(name='LazyFastAPI')

_JSON_PARSER = json.Parser()
_JSON_DECODER = json.loads
_JSON_ENCODER = json.dumps

try:
    from functools import cached_property
except ImportError:
    class cached_property:  # noqa
        def __init__(self, func):
            self.__doc__ = getattr(func, "__doc__")
            self.func = func

        def __get__(self, obj, cls):
            if obj is None:
                return self
            value = obj.__dict__[self.func.__name__] = self.func(obj)
            return value

try:
    import sentry_sdk
    from sentry_sdk.utils import transaction_from_function as sentry_transaction_from_function
except ImportError:
    sentry_sdk = None
    sentry_transaction_from_function = None

def sjson_loads(data, *args, **kwargs):
    try:
        return _JSON_PARSER.parse(data, recursive=kwargs.get('recursive', False))
    except Exception as e:
        logger.error(f'Simdjson decoding error: {e}')
        return _JSON_DECODER.loads(data, *args, **kwargs)


def sjson_dumps(v, *, default):
    return json.dumps(v, default=default).decode()

class JSONResponse(BaseJSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(content, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":")).encode("utf-8")

class BaseModel(PyBaseModel):
    class Config:
        json_loads = sjson_loads
        json_dumps = sjson_dumps