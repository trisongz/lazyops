import os
import asyncio
from types import coroutine
from fileio import PathIO
from io import (
    FileIO,
    TextIOBase,
    BufferedReader,
    BufferedWriter,
    BufferedRandom,
)
from functools import partial, singledispatch, wraps
from typing import TypeVar, Union
from aiofiles.threadpool.binary import AsyncBufferedIOBase, AsyncBufferedReader, AsyncFileIO
from aiofiles.threadpool.text import AsyncTextIOWrapper
from aiofiles.base import AiofilesContextManager
from tensorflow.python.platform.gfile import GFile
from tensorflow.python.lib.io import file_io as tfio
from tensorflow.python.lib.io import _pywrap_file_io
#io import stat, rename, create_dir, remove

def async_open(
    file,
    mode="r",
    buffering=-1,
    encoding=None,
    errors=None,
    newline=None,
    closefd=True,
    opener=None,
    *,
    loop=None,
    executor=None
):
    return AiofilesContextManager(
        _open(
            file,
            mode=mode,
            buffering=buffering,
            encoding=encoding,
            errors=errors,
            newline=newline,
            closefd=closefd,
            opener=opener,
            loop=loop,
            executor=executor,
        )
    )


@coroutine
def _open(
    file,
    mode="r",
    buffering=-1,
    encoding=None,
    errors=None,
    newline=None,
    closefd=True,
    opener=None,
    *,
    loop=None,
    executor=None
):
    """Open an asyncio file."""
    if loop is None:
        loop = asyncio.get_event_loop()
    pathio = PathIO(file)
    cb = partial(
        pathio.open,
        #file,
        mode=mode,
        #buffering=buffering,
        encoding=encoding,
        #errors=errors,
        #newline=newline,
        #closefd=closefd,
        #opener=opener,
    )
    f = yield from loop.run_in_executor(executor, cb)

    return wrap(f, loop=loop, executor=executor)


@singledispatch
def wrap(file, *, loop=None, executor=None):
    raise TypeError("Unsupported io type: {}.".format(file))


@wrap.register(TextIOBase)
def _(file, *, loop=None, executor=None):
    return AsyncTextIOWrapper(file, loop=loop, executor=executor)


@wrap.register(BufferedWriter)
def _(file, *, loop=None, executor=None):
    return AsyncBufferedIOBase(file, loop=loop, executor=executor)


@wrap.register(BufferedReader)
@wrap.register(BufferedRandom)
def _(file, *, loop=None, executor=None):
    return AsyncBufferedReader(file, loop=loop, executor=executor)


@wrap.register(FileIO)
def _(file, *, loop=None, executor=None):
    return AsyncFileIO(file, loop, executor)


@wrap.register(GFile)
def _(file, *, loop=None, executor=None):
    return AsyncFileIO(file, loop, executor)


def pathlike_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run


aio_stat = pathlike_wrap(tfio.stat)
aio_rename = pathlike_wrap(tfio.rename)
aio_remove = pathlike_wrap(tfio.delete_file)
aio_mkdir = pathlike_wrap(tfio.create_dir)
aio_rmdir = pathlike_wrap(tfio.delete_recursively)

stat_results = TypeVar("stat_results", str, Union[_pywrap_file_io.FileStatistics, os.stat_result])