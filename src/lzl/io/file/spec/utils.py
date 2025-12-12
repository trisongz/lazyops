from __future__ import annotations

import os
import anyio
import contextlib
import typing as t

# We'll try the latest method first, then fallback to the older one
try:
    from aiopath.wrap import func_as_method_coro, method_as_method_coro as to_async_method
except ImportError:
    from aiopath.wrap import func_to_async_method as func_as_method_coro, to_async_method
from .static import ASYNC_SYNTAX_MAPPING
from ..utils.logs import logger
from ..utils.helpers import iscoroutinefunction
from ..path import Paths, FileMode, Handle, ENCODING, ERRORS, SEP

if t.TYPE_CHECKING:
    from fsspec.spec import AbstractBufferedFile
    from fsspec.asyn import AsyncFileSystem, AbstractAsyncStreamedFile
    from _typeshed import OpenBinaryMode, OpenTextMode, ReadableBuffer, WriteableBuffer
    from .providers.main import AccessorLike

def rewrite_async_syntax(obj, provider: str = 's3'):
    """
    Basically - we're rewriting all the fsspec's async method
    from _method to async_method for syntax
    """
    _names = ASYNC_SYNTAX_MAPPING.get(provider, ASYNC_SYNTAX_MAPPING.get('s3'))
    if not _names: return obj
    
    for attr in dir(obj):
        if attr.startswith('_') and not attr.startswith('__'):
            try:
                attr_val = getattr(obj, attr)
            except Exception:
                continue
            if iscoroutinefunction(attr_val) and _names.get(attr):
                setattr(obj, _names[attr], attr_val)
    return obj


@contextlib.asynccontextmanager
async def get_async_handle(
    name: 'Paths', 
    mode: 'FileMode' = 'r', 
    buffering: int = -1, 
    encoding: str | None = ENCODING, 
    errors: str | None = ERRORS, 
    newline: str | None = SEP
) -> t.AsyncContextManager['Handle']:
    """
    Get a handle to a file
    """
    file: anyio.AsyncFile
    if 'b' in mode: file = await anyio.open_file(name, mode)
    else: file = await anyio.open_file(name, mode, encoding = encoding, buffering = buffering, errors = errors, newline=newline)
    yield file
    await file.aclose()


@contextlib.asynccontextmanager
async def get_async_file(
    filelike: 'Paths'
) -> t.AsyncContextManager[Handle]:
    """
    Creates an Async File
    """
    file: anyio.AsyncFile
    filelike = t.cast(t.IO[t.Union[str, bytes, os.PathLike, t.Any]], filelike)
    file = anyio.AsyncFile(filelike)
    yield file
    await file.aclose()



class AsyncFile(anyio.AsyncFile):
    """
    Wraps the file object to provide a more intuitive interface
    """

    def __init__(self, fp: t.Union['AbstractAsyncStreamedFile', t.IO[t.AnyStr]], is_asyn: t.Optional[bool] = False) -> None:
        self._fp: t.Union['AbstractAsyncStreamedFile', t.Any] = fp
        self._is_asyn = is_asyn

    async def aclose(self) -> None:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.close):
                return await self._fp.close()
            return await anyio.to_thread.run_sync(self._fp.close)
        return await super().aclose()

    async def read(self, size: int = -1) -> t.AnyStr:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.read):
                return await self._fp.read(size)
            return await anyio.to_thread.run_sync(self._fp.read, size)
        return super().read(size)

    async def read1(self, size: int = -1) -> bytes:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.read):
                return await self._fp.read(size)
            return await anyio.to_thread.run_sync(self._fp.read, size)
        return await super().read1(size)

    async def readline(self) -> t.AnyStr:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.readline):
                return await self._fp.readline()
            return await anyio.to_thread.run_sync(self._fp.readline)
        return await super().readline()

    async def readlines(self) -> list[t.AnyStr]:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.readlines):
                return await self._fp.readlines()
            return await anyio.to_thread.run_sync(self._fp.readlines)
        return await super().readlines()
    
    async def readinto(self, b: WriteableBuffer) -> bytes:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.readinto):
                return await self._fp.readinto(b)
            return await anyio.to_thread.run_sync(self._fp.readinto, b)
        return await super().readinto(b)

    async def readinto1(self, b: WriteableBuffer) -> bytes:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.readinto1):
                return await self._fp.readinto1(b)
            return await anyio.to_thread.run_sync(self._fp.readinto1, b)
        return await super().readinto1(b)

    async def write(self, b: ReadableBuffer | str) -> int:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.write):
                return await self._fp.write(b)
            return await anyio.to_thread.run_sync(self._fp.write, b)
        return await super().write(b)

    async def writelines(self, lines: t.Iterable[ReadableBuffer] | t.Iterable[str]) -> None:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.writelines):
                return await self._fp.writelines(lines)
            return await anyio.to_thread.run_sync(self._fp.writelines, lines)
        return await super().writelines(lines)
    
    async def truncate(self, size: int | None = None) -> int:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.truncate):
                return await self._fp.truncate(size)
            return await anyio.to_thread.run_sync(self._fp.truncate, size)
        return await super().truncate(size)

    async def seek(self, offset: int, whence: int | None = os.SEEK_SET) -> int:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.seek):
                return await self._fp.seek(offset, whence)
            return await anyio.to_thread.run_sync(self._fp.seek, offset, whence)
        return await super().seek(offset, whence)

    async def tell(self) -> int:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.tell):
                return await self._fp.tell()
            return await anyio.to_thread.run_sync(self._fp.tell)
        return await super().tell()

    async def flush(self, *args) -> None:
        if self._is_asyn:
            if iscoroutinefunction(self._fp.flush):
                return await self._fp.flush(*args)
            return await anyio.to_thread.run_sync(self._fp.flush, *args)
        return await super().flush()


@contextlib.asynccontextmanager
async def get_fsspec_file(
    accessor: 'AccessorLike', 
    path: Paths, 
    mode: FileMode = 'rb', 
    **kwargs
) -> t.AsyncContextManager[Handle]:
    """
    Helper function to open a file from a filesystem
    """
    if 'wb' in mode and hasattr(accessor.afilesys, 'open_async'):
        asyncfile: 'AbstractAsyncStreamedFile' = await accessor.afilesys.open_async(path, mode, **kwargs)
        if not hasattr(asyncfile, '_closed'):
            setattr(asyncfile, '_closed', False)
        filelike = t.cast(t.IO[t.Union[str, bytes, os.PathLike, t.Any]], asyncfile) 
    else:
        syncfile: 'AbstractBufferedFile' = accessor.open(path, mode, **kwargs)
        filelike = t.cast(t.IO[t.Union[str, bytes, os.PathLike, t.Any]], syncfile)
    file = AsyncFile(filelike, is_asyn = True)
    try:
        yield file
    finally:
        await file.aclose()


if t.TYPE_CHECKING:
    from .cloudfs import CloudFileSystemMeta

def _dummy_func(*args, **kwargs) -> t.Optional[t.Any]:
    pass

async def _adummy_func(*args, **kwargs)  -> t.Optional[t.Any]:
    pass



def create_method_fs(cfs: t.Type['CloudFileSystemMeta'], name: t.Union[str, t.List[str]],  func: t.Optional[t.Callable] = None, fs_type: str = 'fs') -> t.Optional[t.Callable]:
    """
    Creates a method from the filesystem
    """
    if not hasattr(cfs, fs_type):
        return _dummy_func
    fs_module = getattr(cfs, fs_type)
    if not isinstance(name, list): name = [name]
    for n in name:
        if hasattr(fs_module, n):
            return func(getattr(fs_module, n)) if func else getattr(fs_module, n)
    return _dummy_func

def create_async_method_fs(cfs: t.Type['CloudFileSystemMeta'], name: t.Union[str, t.List[str]], func: t.Optional[t.Callable] = None, fs_type: str = 'fsa') -> t.Optional[t.Union[t.Callable, t.Coroutine]]:
    """
    Creates an async method from the filesystem
    """
    if not hasattr(cfs, fs_type):
        return _adummy_func
    fs_module = getattr(cfs, fs_type)
    if not isinstance(name, list): name = [name]
    for n in name:
        if hasattr(fs_module, n):
            return func(getattr(fs_module, n)) if func else getattr(fs_module, n)
    return _adummy_func

def create_staticmethod(cfs: t.Type['CloudFileSystemMeta'], name: t.Union[str, t.List[str]], fs_type: str = 'fs'):
    """
    Creates a staticmethod from the filesystem
    """
    return create_method_fs(cfs, name = name, func = staticmethod, fs_type = fs_type)


def create_async_coro(cfs: t.Type['CloudFileSystemMeta'], name: t.Union[str, t.List[str]], fs_type: str = 'fs'):
    """
    Creates an async coroutine from the filesystem
    """
    return create_async_method_fs(cfs, name = name, func = to_async_method, fs_type = fs_type)

