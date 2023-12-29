import io
import pickle
from typing import Union, Any
from pydantic import BaseModel
from pydantic.types import ByteSize

class Constant(tuple):
    """Pretty display of immutable constant."""

    def __new__(cls, name):
        return tuple.__new__(cls, (name,))

    def __repr__(self):
        return f'{self[0]}'


DBNAME = 'sqlcache.db'
ENOVAL = Constant('ENOVAL')
UNKNOWN = Constant('UNKNOWN')

MODE_NONE = 0
MODE_RAW = 1
MODE_BINARY = 2
MODE_TEXT = 3
MODE_PICKLE = 4

KeyT = Union[str, int, float, bytes, None]
ValueT = Union[str, int, float, bytes, None, io.BytesIO, Any]

class SizeModel(BaseModel):
    size: ByteSize



DEFAULT_SETTINGS = {
    'statistics': 0,  # False
    'tag_index': 0,  # False
    'eviction_policy': 'least-recently-stored',
    'size_limit': 2**30,  # 1gb
    'cull_limit': 10,
    'sqlite_auto_vacuum': 1,  # FULL
    'sqlite_cache_size': 2**13,  # 8,192 pages
    'sqlite_journal_mode': 'wal',
    'sqlite_mmap_size': 2**26,  # 64mb
    'sqlite_synchronous': 1,  # NORMAL
    'disk_min_file_size': 2**15,  # 32kb
    'disk_pickle_protocol': pickle.HIGHEST_PROTOCOL,
}

OPTIMIZED_SETTINGS = {
    'fast': {
        'min_file_size': SizeModel(size = '32KiB').size,
        'size_limit': SizeModel(size = '4GiB').size,
        'mmap_size': SizeModel(size = '512MiB').size,
        'eviction_policy': 'least-recently-stored',
        'cache_size': 8192,
        'compression_level': 0,
    },
    'standard': {
        'min_file_size': SizeModel(size = '64KiB').size,
        'size_limit': SizeModel(size = '8GiB').size,
        'mmap_size': SizeModel(size = '1024MiB').size,
        'eviction_policy': 'least-recently-stored',
        'cache_size': 8192,
        'compression_level': 5,
    },
    'optimized': {
        'min_file_size': SizeModel(size = '128KiB').size,
        'size_limit': SizeModel(size = '16GiB').size,
        'mmap_size': SizeModel(size = '2048MiB').size,
        'eviction_policy': 'least-recently-stored',
        'sqlite_cache_size': 8192,
        'compression_level': 2,
    },
    'cache': {
        'min_file_size': SizeModel(size = '256KiB').size,
        'size_limit': SizeModel(size = '32GiB').size,
        'mmap_size': SizeModel(size = '4GiB').size,
        'eviction_policy': 'least-recently-used',
        'cache_size': 8192 * 2,
        'compression_level': 8,
    },
    'cache_large': {
        'min_file_size': SizeModel(size = '512KiB').size,
        'size_limit': SizeModel(size = '64GiB').size,
        'mmap_size': SizeModel(size = '8GiB').size,
        'eviction_policy': 'least-recently-used',
        'cache_size': 8192 * 4,
        'compression_level': 10,
    },
}

METADATA = {
    'count': 0,
    'size': 0,
    'hits': 0,
    'misses': 0,
}

EVICTION_POLICY = {
    'none': {
        'init': None,
        'get': None,
        'cull': None,
    },
    'least-recently-stored': {
        'init': (
            'CREATE INDEX IF NOT EXISTS Cache_store_time ON'
            ' Cache (store_time)'
        ),
        'get': None,
        'cull': 'SELECT {fields} FROM Cache ORDER BY store_time LIMIT ?',
    },
    'least-recently-used': {
        'init': (
            'CREATE INDEX IF NOT EXISTS Cache_access_time ON'
            ' Cache (access_time)'
        ),
        'get': 'access_time = {now}',
        'cull': 'SELECT {fields} FROM Cache ORDER BY access_time LIMIT ?',
    },
    'least-frequently-used': {
        'init': (
            'CREATE INDEX IF NOT EXISTS Cache_access_count ON'
            ' Cache (access_count)'
        ),
        'get': 'access_count = access_count + 1',
        'cull': 'SELECT {fields} FROM Cache ORDER BY access_count LIMIT ?',
    },
}

_EVICTION_POLICY = {
    'none': {
        'init': None,
        'get': None,
        'cull': None,
    },
    'least-recently-stored': {
        'init': (
            'CREATE INDEX IF NOT EXISTS Cache_store_time ON'
            ' Cache (store_time)'
        ),
        'get': None,
        'cull': 'SELECT {fields} FROM Cache ORDER BY store_time LIMIT ?',
    },
    'least-recently-used': {
        'init': (
            'CREATE INDEX IF NOT EXISTS Cache_access_time ON'
            ' Cache (access_time)'
        ),
        'get': 'access_time = {now}',
        'cull': 'SELECT {fields} FROM Cache ORDER BY access_time LIMIT ?',
    },
    'least-frequently-used': {
        'init': (
            'CREATE INDEX IF NOT EXISTS Cache_access_count ON'
            ' Cache (access_count)'
        ),
        'get': 'access_count = access_count + 1',
        'cull': 'SELECT {fields} FROM Cache ORDER BY access_count LIMIT ?',
    },
}



try: 
    class WindowsExceptionError(WindowsError):
        pass
except:
    class WindowsExceptionError(Exception):
        "Windows error place-holder on platforms without support."
