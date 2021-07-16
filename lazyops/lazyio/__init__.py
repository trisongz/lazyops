from .models import (
    LazyJson,
    LazyPickler,
    LazyIOBase,
    LazyIOText,
    LazyIOJson,
    LazyIOJsonLines,
    LazyIOPickle,
    LazyIOType,
)


lazypickler = LazyPickler
lazypkler = LazyPickler
lazyjson = LazyJson

lazyfile = LazyIOBase
lazyiojson = LazyIOJson
lazyjsonlines = LazyIOJsonLines
lazyjlines = LazyIOJsonLines
lazyjl = LazyIOJsonLines
lazypickle = LazyIOPickle
lazypkl = LazyIOPickle


__all__ = [
    'LazyJson',
    'LazyPickler',
    'LazyIOBase',
    'LazyIOText',
    'LazyIOJson',
    'LazyIOJsonLines',
    'LazyIOPickle',
    'LazyIOType',
    'lazypickler',
    'lazypkler',
    'lazyjson',
    'lazyfile',
    'lazyiojson',
    'lazyjsonlines',
    'lazyjlines',
    'lazyjl',
    'lazypickle',
    'lazypkl'
]

