import random
import asyncio
import pathlib

from pydantic import BaseModel
from lazyops.libs.persistence import PersistentDict
from lazyops.libs.persistence.main import _DEBUG_ENABLED

_DEBUG_ENABLED = True

class X(BaseModel):
    n: int


def test_json(backend: str = 'local', compression_level: int = None, **kwargs):
    """
    Test JSON - The object is serialized to a dict, and upon retrieval, the type is lost
    """
    
    n = random.randint(0, 1000)
    d = PersistentDict(
        name = 'test',
        serializer = 'json',
        backend_type = backend,
        base_key = 'test.json',
        serializer_kwargs= {
            'compression_level': compression_level,
            'disable_object_serialization': True,
        },
        **kwargs,
    )

    d['x'] = X(n=n)
    print(f'[{backend} - {compression_level} - {kwargs} - {d.base_key}] test json: {n}', d['x'], ' type: ', type(d['x']))
    assert d['x']['n'] == n, f'[{backend} - {compression_level} - {kwargs}] test json: {n} {d["x"]} {type(d["x"])}'

    del d['x']
    assert 'x' not in d


def test_json_obj(backend: str = 'local', compression_level: int = None, **kwargs):
    """
    Test JSON Object - The object is serialized to a dict, however upon retrieval, the object gets re-instantiated
    due to the serialization_obj parameter
    """
    
    n = random.randint(0, 1000)
    d = PersistentDict(
        name = 'test',
        serializer = 'json',
        backend_type = backend,
        base_key = 'test.json.obj',
        serializer_kwargs = {
            'serialization_obj': X,
            'compression_level': compression_level,
        },
        **kwargs,
    )

    d['x'] = X(n=n)

    print(f'[{backend} - {compression_level} - {kwargs} - {d.base_key}] test json obj: {n} ', d['x'], ' type: ', type(d['x']))
    assert d['x'].n == n

    del d['x']
    assert 'x' not in d


def test_msgpack(backend: str = 'local', compression_level: int = None, **kwargs):
    """
    Test MsgPack Object - The object is serialized to a dict, however upon retrieval, the object gets re-instantiated
    due to the serialization_obj parameter
    """
    
    n = random.randint(0, 1000)
    d = PersistentDict(
        name = 'test',
        serializer = 'msgpack',
        backend_type = backend,
        base_key = 'test.msgpack',
        serializer_kwargs = {
            'serialization_obj': X,
            'compression_level': compression_level,
        },
        **kwargs,
    )

    d['x'] = X(n=n)
    print(f'[{backend} - {compression_level} - {kwargs} - {d.base_key}] test msgpack obj: {n} ', d['x'], ' type: ', type(d['x']))
    assert d['x'].n == n

    del d['x']
    assert 'x' not in d

def test_pickle(backend: str = 'local', compression_level: int = None, **kwargs):
    """
    Pickle Test - The object is pickled and thus the type is perserved
    """
    n = random.randint(0, 1000)
    d = PersistentDict(
        name = 'test',
        serializer = 'pickle',
        backend_type = backend,
        base_key = 'test.pickle',
        serializer_kwargs= {
            'compression_level': compression_level,
        },
        **kwargs,

    )

    d['x'] = X(n=n)
    print(f'[{backend} - {compression_level} - {kwargs} - {d.base_key}] test pickle: {n} ', d['x'], ' type: ', type(d['x']))
    assert d['x'].n == n
    del d['x']
    assert 'x' not in d


def test_basic_local(compression_level: int = None, **kwargs):
    """
    Test Basic Functionality
    """

    test_json(backend='local', compression_level=compression_level, **kwargs)
    test_json_obj(backend='local', compression_level=compression_level, **kwargs)
    test_msgpack(backend='local', compression_level=compression_level, **kwargs)
    test_pickle(backend='local', compression_level=compression_level, **kwargs)


def test_basic(compression_level: int = None, **kwargs):
    """
    Test Basic Functionality
    """

    test_json(backend='redis', compression_level=compression_level, **kwargs)
    test_json_obj(backend='redis', compression_level=compression_level, **kwargs)
    test_msgpack(backend='redis', compression_level=compression_level, **kwargs)
    test_pickle(backend='redis', compression_level=compression_level, **kwargs)

    test_json(backend='auto', compression_level=compression_level, **kwargs)
    test_pickle(backend='auto', compression_level=compression_level, **kwargs)

async def atest_json(backend: str = 'local', compression_level: int = None, **kwargs):
    n = random.randint(0, 1000)
    d = PersistentDict(
        name = 'test',
        serializer = 'json',
        backend_type = backend,
        base_key = 'test.json',
        serializer_kwargs= {
            'compression_level': compression_level,
            'disable_object_serialization': True,
        },
        **kwargs,
    )
    await d.aset('x', X(n=n))
    v = await d.aget('x')

    print(f'[{backend} - {compression_level} - {kwargs} - {d.base_key}] async test json: {n} ', v, ' type: ', type(v))
    assert v['n'] == n
    await d.adelete('x')
    assert 'x' not in d


async def atest_json_obj(backend: str = 'local', compression_level: int = None, **kwargs):
    n = random.randint(0, 1000)
    d = PersistentDict(
        name = 'test',
        serializer = 'json',
        backend_type = backend,
        base_key = 'test.json.obj',
        serializer_kwargs = {
            'serialization_obj': X,
            'compression_level': compression_level,
            
        }, 
        **kwargs
    )

    await d.aset('x', X(n=n))

    v = await d.aget('x')
    print(f'[{backend} - {compression_level} - {kwargs} - {d.base_key}] async test json obj: {n} ', v, ' type: ', type(v))
    assert v.n == n

    await d.adelete('x')
    assert 'x' not in d

async def atest_pickle(backend: str = 'local', compression_level: int = None, **kwargs):

    n = random.randint(0, 1000)
    d = PersistentDict(
        name = 'test',
        serializer = 'pickle',
        backend_type = backend,
        base_key = 'test.pickle',
        serializer_kwargs= {
            'compression_level': compression_level,
        },
        **kwargs,
    )

    await d.aset('x', X(n=n))
    v = await d.aget('x')
    print(f'[{backend} - {compression_level} - {kwargs} - {d.base_key}] async test pickle: {n} ', v, ' type: ', type(v))
    assert v.n == n
    await d.adelete('x')
    assert 'x' not in d

async def atest_basic_local(compression_level: int = None, **kwargs):
    """
    Test Basic Functionality
    """

    await atest_json(backend='local', compression_level=compression_level, **kwargs)
    await atest_json_obj(backend='local', compression_level=compression_level, **kwargs)
    await atest_pickle(backend='local', compression_level=compression_level, **kwargs)

async def atest_basic(compression_level: int = None, **kwargs):
    """
    Test Basic Functionality
    """

    await atest_json(backend='redis', compression_level=compression_level, **kwargs)
    await atest_json_obj(backend='redis', compression_level=compression_level, **kwargs)

    await atest_pickle(backend='redis', compression_level=compression_level, **kwargs)

    await atest_json(backend='auto', compression_level=compression_level, **kwargs)
    await atest_pickle(backend='auto', compression_level=compression_level, **kwargs)


async def run_basic_tests():

    fp = pathlib.Path(__file__).parent
    test_basic()
    await atest_basic()

    test_basic_local(file_path = fp)
    await atest_basic_local(file_path = fp)

    test_basic(compression_level=1)
    await atest_basic(compression_level=1)

    test_basic(compression_level=9)
    await atest_basic(compression_level=9)

    test_basic(compression_level=1, hset_disabled=True)
    await atest_basic(compression_level=1, hset_disabled=True)

"""
Advanced Tests
"""


def test_json_advanced(backend: str = 'local', compression: str = None, compression_level: int = None, is_obj: bool = False, **kwargs):
    """
    Handling more advanced dict types
    """
    d = PersistentDict(
        name='test',
        serializer='json',
        backend_type=backend,
        base_key='test.json',
        serializer_kwargs={
            'compression': compression,
            'compression_level': compression_level,
            'disable_object_serialization': not is_obj,
            'serialization_obj': X if is_obj else None,
        },
        **kwargs
    )
    y = {}
    for i in range(10):
        i_int = random.randint(0, 1000)
        y[f'x{i}'] = i_int
        d[f'x{i}'] = X(n = i_int)
    
    d.setdefault('xy', {})
    d['xy'].update({
        'x': 1,
        'y': 2,
    })
    
    print(f'[{backend} - {compression}:{d.compression_level} - {kwargs} - {d.base_key}] test json advanced: ', y, '=', list(d.keys()))
    for k,v in d.items():
        if k == 'xy':
            print(f'[{backend} - {compression}:{d.compression_level} - {kwargs} - {d.base_key}] test json advanced: {k} {v} {type(v)}')
            continue
        assert y[k] == v.n if is_obj else v['n'], f'[{backend} - {compression}:{d.compression_level} - {kwargs}] test json advanced: {k} {y[k]} {v} {type(v)}'
    d.clear()
    assert len(d) == 0


def test_msgpack_advanced(backend: str = 'local', compression: str = None, compression_level: int = None, **kwargs):
    """
    Test MsgPack Object - The object is serialized to a dict, however upon retrieval, the object gets re-instantiated
    due to the serialization_obj parameter
    """
    d = PersistentDict(
        name='test',
        serializer='msgpack',
        backend_type=backend,
        base_key='test.msgpack',
        serializer_kwargs={
            'serialization_obj': X,
            'compression': compression,
            'compression_level': compression_level,
        },
        **kwargs
    )
    y = {}
    for i in range(10):
        i_int = random.randint(0, 1000)
        y[f'x{i}'] = i_int
        d[f'x{i}'] = X(n = i_int)
    

    d.setdefault('xy', {})
    d['xy'].update({
        'x': 1,
        'y': 2,
    })
    

    print(f'[{backend} - {d.base_key}] mutating: ', d['x5'].n, '=', d['x5'].n + 1)
    d['x5'].n += 1
    print(f'[{backend} - {d.base_key}] mutated: ', d['x5'].n)
    
    d['x5'].n += 1
    print(f'[{backend} - {d.base_key}] mutated: ', d['x5'].n)

    d['x5'].n *= 5

    y['x5'] += 2
    y['x5'] *= 5

    print(f'[{backend} - {compression}:{compression_level} - {kwargs} - {d.base_key}] test msgpack advanced: ', y, '=', list(d.keys()))
    for k,v in d.items():
        if k == 'xy':
            print(f'[{backend} - {compression}:{compression_level} - {kwargs} - {d.base_key}] test msgpack advanced: {k} {v} {type(v)}')
            continue
        assert y[k] == v.n, f'[{backend} - {compression}:{compression_level} - {kwargs}] test msgpack advanced: {k} {y[k]} {v} {type(v)}'
    d.clear()
    assert len(d) == 0


def test_pickle_advanced(backend: str = 'local', compression: str = None, compression_level: int = None, **kwargs):
    """
    Pickle Test - The object is pickled and thus the type is perserved
    """
    d = PersistentDict(
        name='test',
        serializer='pickle',
        backend_type=backend,
        base_key='test.pickle',
        serializer_kwargs={
            'compression': compression,
            'compression_level': compression_level,
        },
        **kwargs
    )
    y = {}
    for i in range(10):
        i_int = random.randint(0, 1000)
        y[f'x{i}'] = i_int
        d[f'x{i}'] = X(n = i_int)
    
    d.setdefault('xy', {})
    d['xy'].update({
        'x': 1,
        'y': 2,
    })

    print(f'[{backend} - {d.base_key}] mutating: ', d['x5'].n, '=', d['x5'].n + 1)
    d['x5'].n += 1
    print(f'[{backend} - {d.base_key}] mutated: ', d['x5'].n)
    
    d['x5'].n += 1
    print(f'[{backend} - {d.base_key}] mutated: ', d['x5'].n)

    d['x5'].n *= 5
    # print(f'[{backend} - {d.base_key}] mutated: ', d['x5'].n)

    y['x5'] += 2
    y['x5'] *= 5

    print(f'[{backend} - {compression}:{d.compression_level} - {kwargs} - {d.base_key}] test pickle advanced: ', y, '=', list(d.keys()))
    for k,v in d.items():
        if k == 'xy':
            print(f'[{backend} - {compression}:{d.compression_level} - {kwargs} - {d.base_key}] test pickle advanced: {k} {v} {type(v)}')
            continue

        assert y[k] == v.n, f'[{backend} - {compression}:{d.compression_level} - {kwargs}] test pickle advanced: {k} {y[k]} {v} {type(v)}'
    for key in d:
        print(f'[{backend} - {compression}:{d.compression_level} - {kwargs} - {d.base_key}] test pickle advanced: {key} {d[key]} {type(d[key])}')
    d.clear()
    assert len(d) == 0

def test_basic_advanced(compression_level: int = None, **kwargs):
    """
    Test Basic Functionality
    """
    fp = pathlib.Path(__file__).parent

    for compression in {
        None,
        'gzip',
        'zlib',
        'lz4',
        'zstd',
    }:

        test_json_advanced(backend='local', compression=compression, compression_level=compression_level, file_path = fp, **kwargs)
        test_msgpack_advanced(backend='local',compression=compression, compression_level=compression_level, file_path = fp, **kwargs)
        test_pickle_advanced(backend='local', compression=compression, compression_level=compression_level, file_path = fp, **kwargs)


        test_json_advanced(backend='redis', compression=compression, compression_level=compression_level, **kwargs)
        # test_msgpack_advanced(backend='redis', compression=compression, compression_level=compression_level, **kwargs)
        test_pickle_advanced(backend='redis', compression=compression, compression_level=compression_level, **kwargs)

        test_json_advanced(backend='auto', compression=compression, compression_level=compression_level, **kwargs)
        test_pickle_advanced(backend='auto', compression=compression, compression_level=compression_level, **kwargs)



async def entrypoint():
    # await run_basic_tests()
    test_basic_advanced()



if __name__ == '__main__':
    asyncio.run(entrypoint())
