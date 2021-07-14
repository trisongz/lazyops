from lazyops import lazy_init
lazy_init('pydantic')

import abc
import threading
import time
from dataclasses import dataclass
from pydantic.typing import NoneType
from pydantic import create_model, ValidationError, validator
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

import fileio
from lazyops.lazyclasses import lazyclass
from lazyops.lazyrpc import BaseModel, Field, sjson_dumps, sjson_loads, jsonable_encoder
from lazyops import LazyDate, fio, get_logger, timer, tstamp, LazyEnv

_lazydb_default_cache_path = fio.userdir('.lazydb', mkdirs=True)
_lazydb_logger = get_logger('LazyDB')
_lazydb_picker = fileio.src._pickler
