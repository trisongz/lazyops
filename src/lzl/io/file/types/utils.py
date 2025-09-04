from __future__ import annotations

import os
import inspect
import typing as t
# import aiopath.selectors
# import aiopath.scandir
from aiopath.wrap import func_to_async_func
from hashlib import md5
try:
    import xxhash
    _xxhash_available = True
except ImportError:
    xxhash = None
    _xxhash_available = False


if t.TYPE_CHECKING:
    from ..compat._aiopath.scandir import EntryWrapper
    # from aiopath.scandir import EntryWrapper
    from .base import FilePath


def scandir_sync(*args, **kwargs) -> t.Iterable['EntryWrapper']:
    """
    Sync version of scandir
    """
    from ..compat._aiopath.scandir import _scandir_results
    yield from _scandir_results(*args, **kwargs)


close = func_to_async_func(os.close)
sync_close = os.close


def generate_checksum_xxhash(p: 'FilePath', chunk_size: int = 8192) -> str:
    """
    Generates a checksum
    """
    if not _xxhash_available:
        raise RuntimeError("xxhash is not available")
    with p.open('rb') as f:
        file_hash = xxhash.xxh3_128()
        chunk = f.read(chunk_size)
        while chunk:
            file_hash.update(chunk)
            chunk = f.read(chunk_size)
    return file_hash.hexdigest()



def generate_checksum(p: 'FilePath', chunk_size: int = 8192) -> str:
    """
    Generates a checksum
    """
    if _xxhash_available: return generate_checksum_xxhash(p, chunk_size)
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
    md5s = []
    with open(inputfile,'rb') as fp:
        while True:
            data = fp.read(partsize)
            if not data: break
            md5s.append(md5(data))
    if len(md5s) > 1:
        digests = b"".join(m.digest() for m in md5s)
        new_md5 = md5(digests)
        return f'"{new_md5.hexdigest()}-{len(md5s)}"'
    elif len(md5s) == 1: # file smaller than chunk size
        return f'"{md5s[0].hexdigest()}"'
    else: # empty file
        return '""'


    # md5_digests = []
    # with inputfile.open('rb') as f:
    #     md5_digests.extend(md5(chunk).digest() for chunk in iter(lambda: f.read(partsize), b''))
    # return f"{md5(b''.join(md5_digests)).hexdigest()}-{len(md5_digests)}"


def iscoroutinefunction(obj):
    if inspect.iscoroutinefunction(obj): return True
    return bool(hasattr(obj, '__call__') and inspect.iscoroutinefunction(obj.__call__))
