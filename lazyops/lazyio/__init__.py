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
    'json'
]

