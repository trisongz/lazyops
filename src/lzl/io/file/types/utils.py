from __future__ import annotations

import os
import inspect
import typing as t
import aiopath.selectors
import aiopath.scandir
from aiopath.wrap import func_to_async_func
from hashlib import md5

if t.TYPE_CHECKING:
    from aiopath.scandir import EntryWrapper
    from .base import FilePath


def scandir_sync(*args, **kwargs) -> t.Iterable['EntryWrapper']:
    """
    Sync version of scandir
    """
    yield from aiopath.scandir._scandir_results(*args, **kwargs)


close = func_to_async_func(os.close)
sync_close = os.close


def generate_checksum(p: 'FilePath') -> str:
    """
    Generates a checksum
    """
    with p.open('rb') as f:
        file_hash = md5()
        chunk = f.read(8192)
        while chunk:
            file_hash.update(chunk)
            chunk = f.read(8192)
    return file_hash.hexdigest()


def calc_etag(inputfile: 'FilePath', partsize: int = 8388608):
    """
    Calculate the etag
    """
    md5_digests = []
    with inputfile.open('rb') as f:
        md5_digests.extend(md5(chunk).digest() for chunk in iter(lambda: f.read(partsize), b''))
    return f"{md5(b''.join(md5_digests)).hexdigest()}-{len(md5_digests)}"


def iscoroutinefunction(obj):
    if inspect.iscoroutinefunction(obj): return True
    return bool(hasattr(obj, '__call__') and inspect.iscoroutinefunction(obj.__call__))
