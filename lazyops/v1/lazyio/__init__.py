from .models import (
    LazyFile,
    LazyJson,
    LazyPickler,
    LazyIOBase,
    LazyIOText,
    LazyIOJson,
    LazyIOJsonLines,
    LazyIOPickle,
    LazyIOType,
    LazyHFModel,
    gfile,
    File,
    json,
    PathIO,
    PathIOLike,
)
from .async_ops import (
    async_open,
    aio_stat,
    aio_remove,
    aio_rename,
    aio_mkdir,
    stat_results
)

lazypickler = LazyPickler
lazypkler = LazyPickler
lazyjson = LazyJson

#lazyfile = LazyIOBase
lazyfile = LazyFile
lazyiojson = LazyIOJson
lazyjsonlines = LazyIOJsonLines
lazyjlines = LazyIOJsonLines
lazyjl = LazyIOJsonLines
lazypickle = LazyIOPickle
lazypkl = LazyIOPickle


__all__ = [
    'LazyFile',
    'LazyJson',
    'LazyPickler',
    'LazyIOBase',
    'LazyIOText',
    'LazyIOJson',
    'LazyIOJsonLines',
    'LazyIOPickle',
    'LazyIOType',
    'LazyHFModel',
    'lazypickler',
    'lazypkler',
    'lazyjson',
    'lazyfile',
    'lazyiojson',
    'lazyjsonlines',
    'lazyjlines',
    'lazyjl',
    'lazypickle',
    'lazypkl',
    'File',
    'gfile',
    'json',
    'PathIO',
    'PathIOLike',
    'async_open',
    'aio_stat',
    'aio_remove',
    'aio_rename',
    'aio_mkdir',
    'stat_results'
]

