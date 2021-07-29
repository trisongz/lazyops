from lazyops import lazy_init, get_logger, timed_cache, tstamp
lazy_init('dill')

import dill as pickler
import simdjson as json
import os

from enum import Enum
from abc import ABCMeta
from typing import Union, List, Any, TypeVar, Optional, Dict
from fileio import File, gfile

logger = get_logger(name='LazyIO')