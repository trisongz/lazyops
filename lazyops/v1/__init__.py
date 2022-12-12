import os
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
warnings.filterwarnings('ignore', message='RequestsDependencyWarning')


lazyops_root = os.path.abspath(os.path.dirname(__file__))
from .lazyclasses import lazyclass
from dataclasses import dataclass
import typing as types

from .envs import LazyEnv, get_logger, lazywatcher, lazywatch
from .models import LazyData, LazyTime, LazyDate, LazyFormatter, LazyTimer, LazyObject
from .common import lazylibs, lazy_init, run_cmd, clone_repo, File, PathIO, PathIOLike, get_pathlike
from .common import autojson, read_json, read_jsonlines

from .utils import find_binary_in_path, timed_cache, latest_tf_ckpt, require_module
from .utils import build_chunks, retryable, list_to_dict, create_uuid
from .mp import lazy_parallelize, lazyproc, lazymultiproc, LazyProcs, LazyProc, async_to_sync
from .apis import LazyAPI, LazyAPIConfig


lazyenv = LazyEnv
lazyitem = LazyData
timer = LazyTime
timers = LazyTimer
formatter = LazyFormatter
tstamp = LazyDate.dtime
dtime = LazyDate
ddate = LazyDate.date
fio = File
lazyapi = LazyAPI
lazyapiconfig = LazyAPIConfig
lazy_async = async_to_sync

from .lazyio import LazyHFModel
from . import lazyconfig

from .serializers import async_cache

__all__ = [
    'types',
    'dataclass',
    'lazyclass',
    'LazyEnv',
    'get_logger',
    'LazyData',
    'LazyTime',
    'LazyDate',
    'LazyFormatter',
    'LazyTimer',
    'LazyObject',
    'LazyHFModel',
    'lazylibs',
    'lazy_init',
    'run_cmd',
    'clone_repo',
    'File',
    'lazyenv',
    'lazyitem',
    'timer',
    'timers',
    'formatter',
    'dtime',
    'tstamp',
    'ddate',
    'fio',
    'lazyapi',
    'lazyapiconfig',
    'lazywatch',
    'lazywatcher',
    'lazy_parallelize',
    'lazyproc',
    'lazymultiproc',
    'LazyProcs',
    'LazyProc',
    'lazy_async',
    'async_to_sync',
    'async_cache',
    'PathIO',
    'PathIOLike', 
    'get_pathlike'
    'lazyconfig'
]
#from . import lazyrpc