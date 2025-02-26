from __future__ import annotations

import io
import os
import shutil
import tempfile
import pathlib
import typing as t
import anyio
from pydantic.types import ByteSize
# from aiopath.selectors import _make_selector
# from aiopath.scandir import EntryWrapper, scandir_async
from stat import S_ISDIR, S_ISLNK, S_ISREG, S_ISSOCK, S_ISBLK, S_ISCHR, S_ISFIFO
from aiopath.wrap import (
    func_to_async_func,
    func_to_async_method as func_as_method_coro,
    coro_to_async_method as coro_as_method_coro,
    to_async_method,
    method_to_async_method,
    to_thread,
)
from aiopath.handle import (
    IterableAIOFile,
    get_handle,
    AsyncFile,
)
from lzl import load
from ..path import *
from ..path import (
    _ignore_error,
    _sync_make_selector,
    _getfinalpathname, _async_getfinalpathname,
    _PosixFlavour, _WindowsFlavour
)
from ..path.flavours import (
    _pathz_posix_flavour, _pathz_windows_flavour
)
from .misc import ObjectSize
from .errors import *
from .utils import (
    scandir_sync,
    close,
    sync_close,
    generate_checksum,
    calc_etag,
)

# method_to_async_method = method_as_method_coro

if t.TYPE_CHECKING:
    from fsspec import AbstractFileSystem
    from fsspec.asyn import AsyncFileSystem
    from ..compat._aiopath.scandir import EntryWrapper
    # from aiopath.scandir import EntryWrapper
    from ..main import FileLike, PathLike


class _FileAccessor(NormalAccessor):
    # Sync methods
    stat = os.stat
    info = get_file_info
    size = os.path.getsize
    walk = os.walk

    lstat = os.lstat
    open = os.open
    listdir = os.listdir
    chmod = os.chmod
    is_dir = os.path.isdir

    copy = shutil.copy
    copy_file = shutil.copyfile

    mkdir = os.mkdir
    unlink = os.unlink

    rmdir = os.rmdir
    rename = os.rename
    replace = os.replace
    symlink = staticmethod(NormalAccessor.symlink)
    utime = os.utime
    readlink = NormalAccessor.readlink
    remove = os.remove

    # Async Methods
    astat = func_as_method_coro(os.stat)
    ainfo = func_as_method_coro(get_file_info)
    asize = func_as_method_coro(os.path.getsize)
    awalk = func_as_method_coro(os.walk)

    alstat = func_as_method_coro(os.lstat)
    aopen = func_as_method_coro(os.open)
    alistdir = func_as_method_coro(os.listdir)
    achmod = func_as_method_coro(os.chmod)
    ais_dir = func_as_method_coro(os.path.isdir)

    acopy = func_as_method_coro(shutil.copy)
    acopy_file = func_as_method_coro(shutil.copyfile)

    if hasattr(NormalAccessor, 'lchmod'):
        lchmod = NormalAccessor.lchmod
        alchmod = method_to_async_method(NormalAccessor.lchmod)

    amkdir = func_as_method_coro(os.mkdir)
    aunlink = func_as_method_coro(os.unlink)

    if hasattr(NormalAccessor, 'link'):
        link = NormalAccessor.link
        alink = method_to_async_method(NormalAccessor.link)

    armdir = func_as_method_coro(os.rmdir)
    arename = func_as_method_coro(os.rename)
    areplace = func_as_method_coro(os.replace)
    asymlink = staticmethod(method_to_async_method(NormalAccessor.symlink))
    autime = func_as_method_coro(os.utime)
    areadlink = method_to_async_method(NormalAccessor.readlink)
    aremove = func_as_method_coro(os.remove)

    def owner(self, path: str) -> str:
        try:
            import pwd
            stat = self.stat(path)
            return pwd.getpwuid(stat.st_uid).pw_name

        except ImportError as e:
            raise NotImplementedError("Path.owner() is unsupported on this system") from e

    async def aowner(self, path: str) -> str:
        try:
            import pwd
            stat = await self.astat(path)
            return pwd.getpwuid(stat.st_uid).pw_name
        except ImportError as e: raise NotImplementedError("Path.owner() is unsupported on this system") from e

    def group(self, path: str) -> str:
        try:
            import grp
            stat = self.stat(path)
            return grp.getgrgid(stat.st_gid).gr_name

        except ImportError as e: raise NotImplementedError("Path.group() is unsupported on this system") from e

    async def agroup(self, path: str) -> str:
        try:
            import grp
            stat = await self.astat(path)
            return grp.getgrgid(stat.st_gid).gr_name

        except ImportError as e: raise NotImplementedError("Path.group() is unsupported on this system") from e

    def scandir(self, *args, **kwargs) -> t.Iterable['EntryWrapper']:
        """
        Synchronous scandir
        """
        yield from scandir_sync(*args, **kwargs)

    async def ascandir(self, *args, **kwargs) -> t.AsyncIterable['EntryWrapper']:
        """
        Asynchronous scandir
        """
        from ..compat._aiopath.scandir import scandir_async
        async for entry in scandir_async(*args, **kwargs):
            yield entry

    def __enter__(self):
        """
        Context Manager
        """
        return self
    
    @property
    def is_fsspec(self):
        """
        Returns True if the path is a fsspec accessor
        """
        return hasattr(self, 'filesys')
    


_pathz_accessor = _FileAccessor()


class FilePurePath(PurePath):
    _prefix: str = None
    _provider: str = None
    _win_pathz: t.ClassVar = 'PureFileWindowsPath'
    _posix_pathz: t.ClassVar = 'PureFilePosixPath'

    def _init(self, template: t.Optional[PurePath] = None):
        self._accessor = _pathz_accessor

    def __new__(cls, *args):
        if cls is FilePurePath or issubclass(cls, FilePurePath): 
            cls = cls._win_pathz if os.name == 'nt' else cls._posix_pathz
            cls = globals()[cls]
        return cls._from_parts(args)



class PureFilePosixPath(FilePurePath):
    """PurePath subclass for non-Windows systems.
    On a POSIX system, instantiating a PurePath should return this object.
    However, you can also instantiate it directly on any system.
    """
    _flavour = _pathz_posix_flavour
    __slots__ = ()


class PureFileWindowsPath(FilePurePath):
    """PurePath subclass for Windows systems.
    On a Windows system, instantiating a PurePath should return this object.
    However, you can also instantiate it directly on any system.
    """
    _flavour = _pathz_windows_flavour
    __slots__ = ()

_FilePathT = t.TypeVar('_FilePathT', bound = 'FilePath')

class FilePath(Path, FilePurePath):
    """
    Our customized class that incorporates both sync and async methods
    """
    _flavour = _pathz_posix_flavour if os.name != 'nt' else _pathz_windows_flavour
    _accessor = _pathz_accessor
    _prefix = None
    _provider = None
    _win_pathz: t.ClassVar['FileWindowsPath'] = 'FileWindowsPath'
    _posix_pathz: t.ClassVar['FilePosixPath'] = 'FilePosixPath'

    def _init(self, template: t.Optional['FilePath'] = None):
        self._accessor = _pathz_accessor
        self._closed = False
        self._fileio = None

    def __new__(cls: t.Union['FilePath', t.Type[_FilePathT]], *args, **kwargs):
        #if cls is FilePath: cls = FileWindowsPath if os.name == 'nt' else FilePosixPath
        if cls is FilePath or issubclass(cls, FilePath): 
            cls = cls._win_pathz if os.name == 'nt' else cls._posix_pathz
            cls = globals()[cls]
        self = cls._from_parts(args, init=False)
        if not self._flavour.is_supported:
            name: str = cls.__name__
            raise NotImplementedError(f"cannot instantiate {name} on your system")

        self._init()
        return self
    
    @property
    def filesys(self) -> t.Optional['AbstractFileSystem']:
        """
        The filesystem object associated with this path.
        """
        return getattr(self._accessor, 'filesys', None)
    
    @property
    def afilesys(self) -> t.Optional['AsyncFileSystem']:
        """
        The filesystem object associated with this path.
        """
        return getattr(self._accessor, 'afilesys', None)
    
    @property
    def is_fsspec(self) -> bool:
        """
        Returns True if the path is a fsspec accessor
        """
        return self._accessor.is_fsspec

    @property
    def parent(self) -> 'FilePath':
        """
        The logical parent of the path.
        """
        return super().parent
    
    @property
    def checksum(self):
        """
        Returns the checksum of the file
        """
        return generate_checksum(self)
    
    @property
    def etag(self):
        """
        Returns the etag of the file
        """
        return calc_etag(self)
    
    
    @property
    def string(self) -> str:
        """
        Return the string representation of the path with forward (/)
        """
        return self.fsuri_ if self.is_fsspec else self.posix_
    

    @property
    def posix_(self):
        """
        Return the string representation of the path with forward (/)
        slashes."""
        f = self._flavour
        return str(self).replace(f.sep, '/')
    
    @property
    def path_(self) -> str:
        """
        Returns the path as a string
        """
        return self.fsuri_ if self.is_fsspec else str(self)
    
    @property
    def fspath_(self) -> str:
        """
        Returns the `__fspath__` string representation without the uri_scheme
        """
        # Mirrors _cloudpath
        return None

    @property
    def fsuri_(self) -> t.Optional[str]:
        """
        Reconstructs the proper Fsspec URI
        """
        # Mirrors _cloudstr
        return None
    
    @property
    def bucket_(self) -> str:
        """
        Returns the `__fspath__` string representation without the uri_scheme
        """
        return None
    
    @property
    def bucketstr_(self) -> t.Optional[str]:
        """
        Returns the `__fspath__` string representation without the uri_scheme
        """
        return None
    
    @property
    def pathkeys_(self) -> t.Optional[str]:
        """
        Returns the `__fspath__` string representation without the uri_scheme
        """
        return None
    
    @property
    def filename_(self) -> str:
        """
        Returns the filename if is file, else ''
        """
        return self.parts[-1] if self.is_file() else ''

    @property
    def ext_(self) -> str:
        """
        Returns the extension for a file
        """
        return self.suffix

    @property
    def extension(self) -> str:
        """
        Returns the extension for a file
        """
        return self.suffix
    
    @property
    def is_tempfile(self) -> bool:
        """
        Returns True if the path is a tempfile

        We assume cloud files are not temp
        """
        if self.is_fsspec: return False
        if self.is_dir(): return False
        tmpdir = tempfile.gettempdir()
        if tmpdir: return self.string.startswith(tmpdir)
        return 'tmp' in self.string or 'temp' in self.string

    @property
    def is_tempdir(self) -> bool:
        """
        Returns True if the path is a tempdir

        We assume cloud files are not temp
        """
        if self.is_fsspec: return False
        if self.is_file(): return False
        tmpdir = tempfile.gettempdir()
        return self.string == tmpdir if tmpdir else ('tmp' in self.string or 'temp' in self.string)
    
    @property
    def is_temp(self) -> bool:
        """
        Returns True if the path is a tempdir or tempfile

        We assume cloud files are not temp
        """
        return self.is_tempfile or self.is_tempdir

    
    @staticmethod
    def get_pathlike_(path: Paths):
        """
        Returns the path of the file.
        """
        from lzl.io.file.spec.main import get_pathlike
        return get_pathlike(path)
    
    def open(self, mode: FileMode = 'r', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, **kwargs) -> t.IO[t.Union[str, bytes]]:
        """
        Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        if self._closed: self._raise_closed()
        if 'b' in mode:
            return io.open(self, mode = mode, buffering = buffering, opener=self._opener)
        return io.open(self, mode, buffering, encoding, errors, newline, opener=self._opener)

    def aopen(self, mode: FileMode = 'r', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, **kwargs) -> AsyncFile:
        """
        Asyncronously Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        if 'b' in mode:
            return get_handle(self.path_, mode = mode, buffering = buffering)
        return get_handle(self.path_, mode, encoding=encoding, errors=errors, newline=newline)
    

    def iter_raw(self, chunk_size: t.Optional[int] = None) -> t.Iterator[bytes]:
        """
        Iterates over the bytes of a file
        """
        if self._closed: self._raise_closed()
        from lzl.io.file.utils.decoders import ByteChunker
        chunker = ByteChunker(chunk_size = chunk_size)
        chunk_size = chunk_size if chunk_size is not None else -1
        with self.open(mode = 'rb', buffering = chunk_size) as stream:
            for raw_stream_bytes in stream:
                yield from chunker.decode(raw_stream_bytes)
        yield from chunker.flush()

    def iter_text(self, chunk_size: int | None = None, encoding: str | None = None) -> t.Iterator[str]:
        """
        A str-iterator over the content
        """
        from lzl.io.file.utils.decoders import TextChunker, TextDecoder
        decoder = TextDecoder(encoding = encoding or "utf-8")
        chunker = TextChunker(chunk_size = chunk_size)
        for byte_content in self.iter_raw():
            text_content = decoder.decode(byte_content)
            yield from chunker.decode(text_content)

            text_content = decoder.flush()
            yield from chunker.decode(text_content)
            yield from chunker.flush()

    def iter_lines(self, chunk_size: int | None = None, encoding: str | None = None) -> t.Iterator[str]:
        """
        A line-by-line iterator over the file content.
        """
        from lzl.io.file.utils.decoders import LineDecoder
        decoder = LineDecoder()
        for text in self.iter_text(chunk_size = chunk_size, encoding = encoding):
            yield from decoder.decode(text)
        yield from decoder.flush()


    async def aiter_raw(self, chunk_size: t.Optional[int] = None) -> t.AsyncIterator[bytes]:
        """
        Iterates over the bytes of a file
        """
        if self._closed: self._raise_closed()
        from lzl.io.file.utils.decoders import ByteChunker
        chunker = ByteChunker(chunk_size = chunk_size)
        chunk_size = chunk_size if chunk_size is not None else -1
        async with self.aopen(mode = 'rb', buffering = chunk_size) as stream:
            async for raw_stream_bytes in stream:
                for chunk in chunker.decode(raw_stream_bytes):
                    yield chunk
        for chunk in chunker.flush():
            yield chunk

    async def aiter_text(self, chunk_size: int | None = None, encoding: str | None = None) -> t.AsyncIterator[str]:
        """
        A str-iterator over the content
        """
        from lzl.io.file.utils.decoders import TextChunker, TextDecoder
        decoder = TextDecoder(encoding = encoding or "utf-8")
        chunker = TextChunker(chunk_size = chunk_size)
        async for byte_content in self.aiter_raw():
            text_content = decoder.decode(byte_content)
            for chunk in chunker.decode(text_content):
                yield chunk
            text_content = decoder.flush()
            for chunk in chunker.decode(text_content):
                yield chunk
        
            for chunk in chunker.flush():
                yield chunk

    async def aiter_lines(self, chunk_size: int | None = None, encoding: str | None = None) -> t.AsyncIterator[str]:
        """
        A line-by-line iterator over the file content.
        """
        from lzl.io.file.utils.decoders import LineDecoder
        decoder = LineDecoder()
        async for text in self.aiter_text(chunk_size = chunk_size, encoding = encoding):
            for line in decoder.decode(text):
                yield line
        for line in decoder.flush():
            yield line


    def reader(self, mode: FileMode = 'r', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, **kwargs) -> t.IO[t.Union[str, bytes]]:
        """
        Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        if self._closed: self._raise_closed()
        return io.open(self, mode, buffering, encoding, errors, newline, opener=self._opener)
    
    def async_reader(self, mode: FileMode = 'r', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, **kwargs) -> AsyncFile:
        """
        Asyncronously Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        return get_handle(self.path_, mode, encoding=encoding, errors=errors, newline=newline)
    
    def appender(self, mode: FileMode = 'a', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, **kwargs) -> t.IO[t.Union[str, bytes]]:
        """
        Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        if self._closed: self._raise_closed()
        return io.open(self, mode, buffering, encoding, errors, newline, opener=self._opener)
    
    def aappender(self, mode: FileMode = 'a', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, **kwargs) -> AsyncFile:
        """
        Asyncronously Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        return get_handle(self.path_, mode, encoding=encoding, errors=errors, newline=newline)
    
    def writer(self, mode: FileMode = 'w', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, **kwargs) -> t.IO[t.Union[str, bytes]]:
        """
        Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        if self._closed: self._raise_closed()
        return io.open(self, mode, buffering, encoding, errors, newline, opener=self._opener)
    
    def awriter(self, mode: FileMode = 'w', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, **kwargs) -> AsyncFile:
        """
        Asyncronously Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        return get_handle(self.path_, mode, encoding=encoding, errors=errors, newline=newline)

    def read(self, mode: FileMode = 'rb', size: t.Optional[int] = -1, offset: t.Optional[int] = 0, **kwargs) -> t.Union[str, bytes]:
        with self.open(mode=mode, **kwargs) as file:
            if offset: file.seek(offset)
            return file.read(size)
            # return file.read(size, offset)

    async def aread(self, mode: FileMode = 'rb', size: t.Optional[int] = -1, offset: t.Optional[int] = 0, **kwargs):
        """
        Read and return the file's contents.
        """
        async with self.aopen(mode=mode, **kwargs) as file:
            if offset: await file.seek(offset)
            return await file.read(size)
            # return await file.read(size, offset)

    def read_text(self, encoding: str | None = DEFAULT_ENCODING, errors: str | None = ON_ERRORS) -> str:
        with self.open('r', encoding=encoding, errors=errors) as file:
            return file.read()

    async def aread_text(self, encoding: str | None = DEFAULT_ENCODING, errors: str | None = ON_ERRORS) -> str:
        """
        Read and return the file's contents.
        """
        async with self.aopen('r', encoding=encoding, errors=errors) as file:
            return await file.read()

    def read_bytes(self, start: t.Optional[t.Any] = None, end: t.Optional[t.Any] = None, **kwargs) -> bytes:
        """
        Read and return the file's contents.
        """
        with self.open('rb', **kwargs) as f:
            if start is not None:
                if start >= 0:
                    f.seek(start)
                else:
                    f_size = os.path.getsize(self.path_)
                    f.seek(max(0, f_size + start))
            if end is not None:
                if end < 0:
                    f_size = os.path.getsize(self.path_)
                    end = f_size + end
                return f.read(end - f.tell())
            return f.read()

    async def aread_bytes(self, **kwargs) -> bytes:
        async with self.aopen('rb', **kwargs) as f:
            return await f.read()

    def write_bytes(self, data: bytes) -> int:
        """
        Open the file in bytes mode, write to it, and close the file.
        """
        # type-check for the buffer interface before truncating the file
        view = memoryview(data)
        with self.open(mode='wb') as f:
            return f.write(data)

    async def awrite_bytes(self, data: bytes) -> int:
        """
        Open the file in bytes mode, write to it, and close the file.
        """
        # type-check for the buffer interface before truncating the file
        view = memoryview(data)
        async with self.aopen(mode='wb') as f:
            return await f.write(data)

    def append_text(self, data: str, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE) -> int:
        """
        Open the file in text mode, write to it, and close the file.
        """
        if not isinstance(data, str): raise TypeError(f'data must be str, not {type(data).__name__}')
        with self.open(mode='a', encoding=encoding, errors=errors, newline=newline) as f:
            n = f.write(data)
            n += f.write(newline)
            return n

    async def aappend_text(self, data: str, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE) -> int:
        """
        Open the file in text mode, write to it, and close the file.
        """
        if not isinstance(data, str): raise TypeError(f'data must be str, not {type(data).__name__}')
        async with self.aopen(mode='a', encoding=encoding, errors=errors, newline=newline) as f:
            n = await f.write(data)
            n += await f.write(newline)
            return n

    def write_text(self, data: str, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE) -> int:
        """
        Open the file in text mode, write to it, and close the file.
        """
        if not isinstance(data, str): raise TypeError(f'data must be str, not {type(data).__name__}')
        with self.open(mode='w', encoding=encoding, errors=errors, newline=newline) as f:
            return f.write(data)

    async def awrite_text(self, data: str, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE) -> int:
        """
        Open the file in text mode, write to it, and close the file.
        """
        if not isinstance(data, str): raise TypeError(f'data must be str, not {type(data).__name__}')
        async with self.aopen(mode='w', encoding=encoding, errors=errors, newline=newline) as f:
            return await f.write(data)

    def readlink(self) -> FilePath:
        """
        Return the path to which the symbolic link points.
        """
        path: str = self._accessor.readlink(self)
        obj = self._from_parts((path,), init=False)
        obj._init(template=self)
        return obj

    async def areadlink(self) -> FilePath:
        """
        Return the path to which the symbolic link points.
        """
        path: str = await self._accessor.areadlink(self)
        obj = self._from_parts((path,), init=False)
        obj._init(template=self)
        return obj

    def _opener(self, name, flags, mode=0o666):
        # A stub for the opener argument to built-in open()
        return self._accessor.open(self, flags, mode)
    
    def _async_opener(self, name, flags, mode=0o666):
        # A stub for the opener argument to built-in open()
        return self._accessor.aopen(self, flags, mode)

    def _raw_open(self, flags: int, mode: int = 0o777) -> int:
        """
        Open the file pointed by this path and return a file descriptor,
        as os.open() does.
        """
        if self._closed: self._raise_closed()
        return self._accessor.open(self, flags, mode)

    async def _async_raw_open(self, flags: int, mode: int = 0o777) -> int:
        """
        Open the file pointed by this path and return a file descriptor,
        as os.open() does.
        """
        return await self._accessor.aopen(self, flags, mode)

    def touch(self, mode: int = 0o666, exist_ok: bool = True):
        """
        Create this file with the given access mode, if it doesn't exist.
        """
        if exist_ok:
            try: self._accessor.utime(self, None)
            # Avoid exception chaining
            except OSError: pass
            else: return

        flags: int = os.O_CREAT | os.O_WRONLY
        if not exist_ok: flags |= os.O_EXCL
        fd = self._raw_open(flags, mode)
        sync_close(fd)

    async def atouch(self, mode: int = 0o666, exist_ok: bool = True):
        """
        Create this file with the given access mode, if it doesn't exist.
        """
        if exist_ok:
            try: await self._accessor.autime(self, None)
            # Avoid exception chaining
            except OSError: pass
            else: return

        flags: int = os.O_CREAT | os.O_WRONLY
        if not exist_ok: flags |= os.O_EXCL
        fd = await self._async_raw_open(flags, mode)
        await close(fd)

    def mkdir(self, mode: int = 0o777, parents: bool = True, exist_ok: bool = True):
        """
        Create a new directory at this given path.
        """
        try: self._accessor.mkdir(self, mode)

        except FileNotFoundError:
            if not parents or self.parent == self: raise
            self.parent.mkdir(parents=True, exist_ok=True)
            self.mkdir(mode, parents=False, exist_ok=exist_ok)

        except OSError:
            # Cannot rely on checking for EEXIST, since the operating system
            # could give priority to other errors like EACCES or EROFS
            if not exist_ok or not self.is_dir(): raise

    async def amkdir(self, mode: int = 0o777, parents: bool = True, exist_ok: bool = True):
        """
        Create a new directory at this given path.
        """
        try: await self._accessor.amkdir(self, mode)

        except FileNotFoundError:
            if not parents or self.parent == self: raise
            await self.parent.amkdir(parents=True, exist_ok=True)
            await self.amkdir(mode, parents=False, exist_ok=exist_ok)

        except OSError:
            # Cannot rely on checking for EEXIST, since the operating system
            # could give priority to other errors like EACCES or EROFS
            if not exist_ok or not await self.ais_dir(): raise

    async def chmod(self, mode: int):
        """
        Change the permissions of the path, like os.chmod().
        """
        self._accessor.chmod(self, mode)

    async def achmod(self, mode: int):
        """
        Change the permissions of the path, like os.chmod().
        """
        await self._accessor.achmod(self, mode)

    def lchmod(self, mode: int):
        """
        Like chmod(), except if the path points to a symlink, the symlink's
        permissions are changed, rather than its target's.
        """
        self._accessor.lchmod(self, mode)

    async def alchmod(self, mode: int):
        """
        Like chmod(), except if the path points to a symlink, the symlink's
        permissions are changed, rather than its target's.
        """
        await self._accessor.alchmod(self, mode)

    def unlink(self, missing_ok: bool = False):
        """
        Remove this file or link.
        If the path is a directory, use rmdir() instead.
        """
        try: self._accessor.unlink(self)
        except FileNotFoundError:
            if not missing_ok: raise

    async def aunlink(self, missing_ok: bool = False):
        """
        Remove this file or link.
        If the path is a directory, use rmdir() instead.
        """
        try: await self._accessor.aunlink(self)
        except FileNotFoundError:
            if not missing_ok: raise

    def copy(self, dest: Paths, recursive: bool = False, overwrite: bool = False, skip_errors: bool = False, **kwargs):
        """
        Copies the File to the Dir/File.
        """
        dest: 'FilePath' = self.get_pathlike_(dest)
        if dest.is_dir() and self.is_file():
            dest = dest.joinpath(self.filename_)
        
        if dest.exists() and not overwrite and dest.is_file():
            if skip_errors: return dest
            raise FileExistsError(f'File {dest.path_} exists')

        if not dest.is_fsspec:
            self._accessor.copy(self.path_, dest.path_, **kwargs)
            return dest
        dest._accessor.put(self.path_, dest.path_, recursive)
        return dest
    
    async def acopy(self, dest: Paths, recursive: bool = False, overwrite: bool = False, skip_errors: bool = False, **kwargs):
        """
        Copies the File to the Dir/File.
        """
        dest: 'FilePath' = self.get_pathlike_(dest)
        if await dest.ais_dir() and self.ais_file():
            dest = dest.joinpath(self.filename_)
        
        if await dest.aexists() and not overwrite and await dest.ais_file():
            if skip_errors: return dest
            FileExistsError(f'File {dest.path_} exists')

        if not dest.is_fsspec:
            await self._accessor.acopy(self.path_, dest.path_, **kwargs)
            return dest
        await dest._accessor.aput(self.path_, dest.path_, recursive)
        return dest
    
    def copy_file(self, dest: Paths, recursive: bool = False, overwrite: bool = False, skip_errors: bool = False, **kwargs):
        """
        Copies the File to the Dir/File.
        """
        dest: 'FilePath' = self.get_pathlike_(dest)
        if dest.is_dir() and self.is_file():
            dest = dest.joinpath(self.filename_)
        
        if dest.exists() and not overwrite and dest.is_file():
            if skip_errors: return dest
            raise FileExistsError(f'File {dest.path_} exists')

        if not dest.is_fsspec:
            self._accessor.copy_file(self.path_, dest.path_, **kwargs)
            return dest
        dest._accessor.put_file(self.path_, dest.path_, recursive)
        return dest

    async def acopy_file(self, dest: Paths, recursive: bool = False, overwrite: bool = False, skip_errors: bool = False, **kwargs):
        dest: 'FilePath' = self.get_pathlike_(dest)
        if await dest.ais_dir() and self.ais_file():
            dest = dest.joinpath(self.filename_)
        
        if await dest.aexists() and not overwrite and await dest.ais_file():
            if skip_errors: return dest
            raise FileExistsError(f'File {dest._path} exists')

        if not dest.is_fsspec:
            await self._accessor.acopy_file(self.path_, dest.path_, **kwargs)
            return dest
        await dest._accessor.aput_file(self.path_, dest.path_, recursive = recursive)
        return dest

    def download(
        self, 
        dest: 'PathLike',
        filename: t.Optional[str] = None,
        overwrite: t.Optional[bool] = None,
        callbacks: t.Optional[t.Dict[str, t.Callable]] = None,
        **kwargs
    ) -> 'FileLike':
        """
        Downloads the dest to the current path
        """
        dest = self.get_pathlike_(dest)
        new = dest.joinpath(filename or self.name) if self.is_dir() else self
        if new.exists() and not overwrite:
            raise FileExistsError(f'File {new.path_} exists and overwrite is False')
        if not dest.is_fsspec:
            raise NotImplementedError('Only fsspec is supported for now')
        return dest.download(self, filename = filename, overwrite = overwrite, callbacks = callbacks, **kwargs)
    
    def upload(
        self, 
        src: 'PathLike',
        filename: t.Optional[str] = None,
        overwrite: t.Optional[bool] = None,
        callbacks: t.Optional[t.Dict[str, t.Callable]] = None,
        **kwargs
    ) -> 'FileLike':
        """
        Uploads the current file to the dest
        """
        src = self.get_pathlike_(src)
        new = self.joinpath(filename or src.name) if self.is_dir() else self
        if new.exists() and not overwrite:
            raise FileExistsError(f'File {new.path_} exists and overwrite is False')
        if not src.exists():
            raise FileNotFoundError(f'File {src.path_} does not exist')
        if not src.is_fsspec:
            raise NotImplementedError('Only fsspec is supported for now')
        return src.upload(self, filename = filename, overwrite = overwrite, callbacks = callbacks, **kwargs)


    def rm(self, **kwargs):
        """
        Remove this file or dir
        """
        return self.rmdir(**kwargs) if self.is_dir() \
            else self._accessor.remove(self)
    
    async def arm(self, **kwargs):
        """
        Remove this file or dir
        """
        if await self.ais_dir(): return await self.armdir(**kwargs)
        await self._accessor.aremove(self)

    def rm_file(self, **kwargs):
        """
        Remove this file 
        """
        
        self._accessor.remove(self)
    
    async def arm_file(self, **kwargs):
        """
        Remove this file 
        """
        
        return await self._accessor.aremove(self)

    def rmdir(self, force: bool = False, recursive: bool = True, skip_errors: bool = True):
        """
        Remove this directory.  The directory must be empty.
        """
        
        self._accessor.rmdir(self)

    async def armdir(self):
        """
        Remove this directory.  The directory must be empty.
        """
        await self._accessor.armdir(self)

    def cat(self, as_bytes: bool = False, **kwargs):
        """
        Fetch paths’ contents
        """
        return self.read_bytes() if as_bytes else self.read_text()
    
    async def acat(self, as_bytes: bool = False, **kwargs):
        """
        Fetch paths’ contents
        """
        return await self.aread_bytes() if as_bytes else await self.aread_text()
    
    def cat_file(self, as_bytes: bool = False, **kwargs):
        """
        """
        return self.cat(as_bytes, **kwargs)
    
    async def acat_file(self, as_bytes: bool = False, **kwargs):
        """
        Parameters
        start, end: int
            Bytes limits of the read. If negative, backwards from end, like usual python slices. Either can be None for start or end of file, respectively

        kwargs: passed to ``open()``.
        """
        return await self.acat(as_bytes, **kwargs)


    def pipe(self, value: t.Union[bytes, str], **kwargs):
        """
        Put value into path

        (counterpart to cat)
        """
        if not isinstance(value, bytes): value = value.encode('UTF-8')
        return self.write_bytes(value, **kwargs)

    async def apipe(self, value: t.Union[bytes, str], **kwargs):
        """
        Put value into path

        (counterpart to cat)
        """
        if not isinstance(value, bytes): value = value.encode('UTF-8')
        return await self.awrite_bytes(value, **kwargs)

    def pipe_file(self, value: t.Union[bytes, str], **kwargs):
        """
        Put value into path

        (counterpart to cat)
        """
        if not isinstance(value, bytes): value = value.encode('UTF-8')
        return self.write_bytes(value, **kwargs)

    async def apipe_file(self, value: t.Union[bytes, str], **kwargs):
        """
        Put value into path

        (counterpart to cat)
        """
        if not isinstance(value, bytes): value = value.encode('UTF-8')
        return await self.awrite_bytes(value, **kwargs)

    def link_to(self, target: str):
        """
        Create a hard link pointing to a path named target.
        """
        self._accessor.link_to(self, target)
    
    async def alink_to(self, target: str):
        """
        Create a hard link pointing to a path named target.
        """
        await self._accessor.alink_to(self, target)

    def rename(self, target: t.Union[str, FilePath]) -> FilePath:
        """
        Rename this path to the target path.
        The target path may be absolute or relative. Relative paths are
        interpreted relative to the current working directory, *not* the
        directory of the Path object.
        Returns the new Path instance pointing to the target path.
        """
        self._accessor.rename(self, target)
        return type(self)(target)
    
    async def arename(self, target: t.Union[str, FilePath]) -> FilePath:
        """
        Rename this path to the target path.
        The target path may be absolute or relative. Relative paths are
        interpreted relative to the current working directory, *not* the
        directory of the Path object.
        Returns the new Path instance pointing to the target path.
        """
        await self._accessor.arename(self, target)
        return type(self)(target)

    def replace(self, target: str) -> FilePath:
        """
        Rename this path to the target path, overwriting if that path exists.
        The target path may be absolute or relative. Relative paths are
        interpreted relative to the current working directory, *not* the
        directory of the Path object.
        Returns the new Path instance pointing to the target path.
        """
        self._accessor.replace(self, target)
        return type(self)(target)
    
    async def areplace(self, target: str) -> FilePath:
        """
        Rename this path to the target path, overwriting if that path exists.
        The target path may be absolute or relative. Relative paths are
        interpreted relative to the current working directory, *not* the
        directory of the Path object.
        Returns the new Path instance pointing to the target path.
        """
        await self._accessor.areplace(self, target)
        return type(self)(target)

    def symlink_to(self, target: str, target_is_directory: bool = False):
        """
        Make this path a symlink pointing to the given path.
        Note the order of arguments (self, target) is the reverse of os.symlink's.
        """
        self._accessor.symlink(target, self, target_is_directory)
    
    async def asymlink_to(self, target: str, target_is_directory: bool = False):
        """
        Make this path a symlink pointing to the given path.
        Note the order of arguments (self, target) is the reverse of os.symlink's.
        """
        await self._accessor.asymlink(target, self, target_is_directory)

    def exists(self) -> bool:
        """
        Whether this path exists.
        """
        try: self.stat()
        except OSError as e:
            if not _ignore_error(e): raise
            return False
        except ValueError: return False
        return True

    async def aexists(self) -> bool:
        """
        Whether this path exists.
        """
        try: await self.astat()
        except OSError as e:
            if not _ignore_error(e): raise
            return False
        except ValueError: return False
        return True

    @classmethod
    def cwd(cls: type) -> str:
        """Return a new path pointing to the current working directory
        (as returned by os.getcwd()).
        """
        cwd: str = os.getcwd()
        return cls(cwd)

    @classmethod
    def home(cls: type) -> FilePath:
        """Return a new path pointing to the user's home directory (as
        returned by os.path.expanduser('~')).
        """
        homedir: str = cls()._flavour.gethomedir(None)
        return cls(homedir)

    @classmethod
    async def ahome(cls: type) -> FilePath:
        """Return a new path pointing to the user's home directory (as
        returned by os.path.expanduser('~')).
        """
        coro = cls()._flavour.agethomedir(None)
        homedir: str = await coro
        return cls(homedir)

    def samefile(self, other_path: t.Union[FilePath, Paths]) -> bool:
        """Return whether other_path is the same or not as this file
        (as returned by os.path.samefile()).
        """
        if isinstance(other_path, Paths.__args__): other_path = FilePath(other_path)
        if isinstance(other_path, FilePath):
            try: other_st = other_path.stat()
            except AttributeError: other_st = self._accessor.stat(other_path)

        else:
            try: other_st = other_path.stat()
            except AttributeError: other_st = other_path._accessor.stat(other_path)
        return os.path.samestat(self.stat(), other_st)

    async def asamefile(self, other_path: t.Union[FilePath, Paths]) -> bool:
        """Return whether other_path is the same or not as this file
        (as returned by os.path.samefile()).
        """
        if isinstance(other_path, Paths.__args__): other_path = FilePath(other_path)
        if isinstance(other_path, FilePath):
            try: other_st = await other_path.async_stat()
            except AttributeError: other_st = await self._accessor.astat(other_path)

        else:
            try: other_st = await to_thread(other_path.stat)
            except AttributeError: other_st = await to_thread(other_path._accessor.stat, other_path)

        return os.path.samestat(await self.astat(),other_st)

    def listdir(self) -> t.List[FilePath]:
        """Iterate over the files in this directory.  Does not yield any
        result for the special paths '.' and '..'.
        """
        return [self._make_child_relpath(name) for name in self._accessor.listdir(self)]
    
    async def alistdir(self) -> t.List[FilePath]:
        """Iterate over the files in this directory.  Does not yield any
        result for the special paths '.' and '..'.
        """
        return [self._make_child_relpath(name) for name in await self._accessor.alistdir(self)]

    def iterdir(self) -> t.Iterable[FilePath]:
        """Iterate over the files in this directory.  Does not yield any
        result for the special paths '.' and '..'.
        """
        for name in self._accessor.listdir(self):
            if name in {'.', '..'}: continue
            yield self._make_child_relpath(name)

    async def aiterdir(self) -> t.AsyncIterable[FilePath]:
        """Iterate over the files in this directory.  Does not yield any
        result for the special paths '.' and '..'.
        """
        for name in await self._accessor.alistdir(self):
            if name in {'.', '..'}: continue
            yield self._make_child_relpath(name)
        
    def walk(self) -> t.Iterable[t.Tuple[FilePath, t.List[FilePath], t.List[FilePath]]]:
        """Iterate over this subtree and yield a 3-tuple (dirpath, dirnames,
        filenames) for each directory in the subtree rooted at path
        (including path itself, if it is a directory).
        """
        top = self._make_child_relpath('.')
        dirs, nondirs = [], []
        for name in self._accessor.listdir(self):
            if name in {'.', '..'}: continue
            (dirs if self._accessor.is_dir(self._make_child_relpath(name)) else nondirs).append(name)
        yield top, dirs, nondirs
        for name in dirs:
            new_path = self._make_child_relpath(name)
            yield from new_path.walk()
        
    async def awalk(self) -> t.AsyncIterable[t.Tuple[FilePath, t.List[FilePath], t.List[FilePath]]]:
        """Iterate over this subtree and yield a 3-tuple (dirpath, dirnames,
        filenames) for each directory in the subtree rooted at path
        (including path itself, if it is a directory).
        """
        top = self._make_child_relpath('.')
        dirs, nondirs = [], []
        for name in await self._accessor.alistdir(self):
            if name in {'.', '..'}: continue
            (dirs if await self._accessor.ais_dir(self._make_child_relpath(name)) else nondirs).append(name)
        yield top, dirs, nondirs
        for name in dirs:
            new_path = self._make_child_relpath(name)
            async for path in new_path.async_walk():
                yield path

    def glob(self, pattern: str) -> t.List[FilePath]:
        """Iterate over this subtree and yield all existing files (of any
        kind, including directories) matching the given relative pattern.
        """
        if not pattern: raise ValueError("Unacceptable pattern: {!r}".format(pattern))
        # yield from self._accessor.glob()
        # just a hot fix
        import glob
        paths = glob.glob(self.joinpath(pattern).as_posix())
        return [self.__class__(path) for path in paths]

        # drv, root, pattern_parts = self._flavour.parse_parts((pattern,))
        # if drv or root: raise NotImplementedError("Non-relative patterns are unsupported")
        # selector = _sync_make_selector(tuple(pattern_parts), self._flavour)
        # for p in selector.select_from(self):
        #     yield p
        # yield from selector.select_from(self)

    async def aglob(self, pattern: str) -> t.List[FilePath]:
        """Iterate over this subtree and yield all existing files (of any
        kind, including directories) matching the given relative pattern.
        """
        from ..compat._aiopath.selectors import _make_selector
        if not pattern: raise ValueError("Unacceptable pattern: {!r}".format(pattern))

        drv, root, pattern_parts = self._flavour.parse_parts((pattern,))
        if drv or root: raise NotImplementedError("Non-relative patterns are unsupported")
        selector = _make_selector(tuple(pattern_parts), self._flavour)
        paths = []
        async for p in selector.select_from(self):
            paths.append(p)
            # yield p
        return paths

    def rglob(self, pattern: str) -> t.List[FilePath]:
        """Recursively yield all existing files (of any kind, including
        directories) matching the given relative pattern, anywhere in
        this subtree.
        """
        import glob
        paths = glob.glob(self.joinpath(pattern).as_posix(), recursive=True)
        return [self.__class__(path) for path in paths]
        # drv, root, pattern_parts = self._flavour.parse_parts((pattern,))
        # if drv or root: raise NotImplementedError("Non-relative patterns are unsupported")
        # parts = ("**", *pattern_parts)
        # selector = _sync_make_selector(parts, self._flavour)
        # yield from selector.select_from(self)

    async def arglob(self, pattern: str) -> t.List[FilePath]:
        """Recursively yield all existing files (of any kind, including
        directories) matching the given relative pattern, anywhere in
        this subtree.
        """
        from ..compat._aiopath.selectors import _make_selector
        drv, root, pattern_parts = self._flavour.parse_parts((pattern,))
        if drv or root: raise NotImplementedError("Non-relative patterns are unsupported")
        parts = ("**", *pattern_parts)
        selector = _make_selector(parts, self._flavour)
        async for p in selector.select_from(self):
            yield p

    def absolute(self) -> FilePath:
        """Return an absolute version of this path.  This function works
        even if the path doesn't point to anything.
        No normalization is done, i.e. all '.' and '..' will be kept along.
        Use resolve() to get the canonical path to a file.
        """
        if self.is_absolute(): return self
        obj = self._from_parts([os.getcwd()] + self._parts, init=False)
        obj._init(template=self)
        return obj

    def resolve(self, strict: bool = False) -> FilePath:
        """
        Make the path absolute, resolving all symlinks on the way and also
        normalizing it (for example turning slashes into backslashes under
        Windows).
        """
        s: t.Optional[str] = self._flavour.resolve(self, strict=strict)

        if s is None:
            self.stat()
            path = self.absolute()
            s = str(path)

        # Now we have no symlinks in the path, it's safe to normalize it.
        normed: str = self._flavour.pathmod.normpath(s)
        obj = self._from_parts((normed,), init=False)
        obj._init(template=self)
        return obj

    async def aresolve(self, strict: bool = False) -> FilePath:
        """
        Make the path absolute, resolving all symlinks on the way and also
        normalizing it (for example turning slashes into backslashes under
        Windows).
        """
        s: t.Optional[str] = await self._flavour.aresolve(self, strict=strict)

        if s is None:
            await self.astat()
            path = await self.absolute()
            s = str(path)

        # Now we have no symlinks in the path, it's safe to normalize it.
        normed: str = self._flavour.pathmod.normpath(s)
        obj = self._from_parts((normed,), init=False)
        obj._init(template=self)
        return obj

    def stat(self) -> os.stat_result:
        """
        Return the result of the stat() system call on this path, like
        os.stat() does.
        """
        return self._accessor.stat(self)
    
    async def astat(self) -> os.stat_result:
        """
        Return the result of the stat() system call on this path, like
        os.stat() does.
        """
        return await self._accessor.astat(self)
    
    def info(self) -> t.Dict[str, t.Any]:
        """
        Return the result of the stat() system call on this path, like
        os.stat() does.
        """
        return get_file_info(self.path_)
        # return self._accessor.info(self._path)
    
    async def ainfo(self) -> t.Dict[str, t.Any]:
        """
        Return the result of the stat() system call on this path, like
        os.stat() does.
        """
        return await self._accessor.ainfo(self)
    
    def size(self) -> int:
        """
        Return the size of the file in bytes, reported by os.path.getsize().
        """
        return os.path.getsize(self.path_)
        # return self._accessor.size(self._path)

    async def asize(self) -> int:
        """
        Return the size of the file in bytes, reported by os.path.getsize().
        """
        return await self._accessor.asize(self.path_)
    
    def bytesize(self) -> ByteSize:
        """
        Return the size of the file in bytes, reported by os.path.getsize().
        """
        return ByteSize(self.size())
    
    async def abytesize(self) -> ByteSize:
        """
        Return the size of the file in bytes, reported by os.path.getsize().
        """
        return ByteSize(await self.asize())

    def lstat(self) -> os.stat_result:
        """
        Like stat(), except if the path points to a symlink, the symlink's
        status information is returned, rather than its target's.
        """
        return self._accessor.lstat(self)
    
    async def alstat(self) -> os.stat_result:
        """
        Like stat(), except if the path points to a symlink, the symlink's
        status information is returned, rather than its target's.
        """
        return await self._accessor.alstat(self)

    def owner(self) -> str:
        """
        Return the login name of the file owner.
        """
        return self._accessor.owner(self)
    
    async def aowner(self) -> str:
        """
        Return the login name of the file owner.
        """
        return await self._accessor.aowner(self)

    def group(self) -> str:
        """
        Return the group name of the file gid.
        """
        return self._accessor.group(self)
    
    async def agroup(self) -> str:
        """
        Return the group name of the file gid.
        """
        return await self._accessor.agroup(self)

    def is_dir(self) -> bool:
        """
        Whether this path is a directory.
        """
        try:
            stat = self.stat()
            return S_ISDIR(stat.st_mode)

        except OSError as e:
            if not _ignore_error(e): raise
            return False

        except ValueError: return False
    
    async def ais_dir(self) -> bool:
        """
        Whether this path is a directory.
        """
        try:
            stat = await self.astat()
            return S_ISDIR(stat.st_mode)

        except OSError as e:
            if not _ignore_error(e): raise
            return False

        except ValueError: return False

    def is_symlink(self) -> bool:
        """
        Whether this path is a symbolic link.
        """
        try:
            lstat = self.lstat()
            return S_ISLNK(lstat.st_mode)

        except OSError as e:
            if not _ignore_error(e): raise
            return False

        except ValueError: return False
    
    async def ais_symlink(self) -> bool:
        """
        Whether this path is a symbolic link.
        """
        try:
            lstat = await self.alstat()
            return S_ISLNK(lstat.st_mode)

        except OSError as e:
            if not _ignore_error(e): raise
            return False

        except ValueError: return False

    def is_file(self) -> bool:
        """
        Whether this path is a regular file (also True for symlinks pointing
        to regular files).
        """
        try:
            stat = self.stat()
            return S_ISREG(stat.st_mode)

        except OSError as e:
            if not _ignore_error(e): raise
            return False

        except ValueError: return False

    async def ais_file(self) -> bool:
        """
        Whether this path is a regular file (also True for symlinks pointing
        to regular files).
        """
        try:
            stat = await self.astat()
            return S_ISREG(stat.st_mode)

        except OSError as e:
            if not _ignore_error(e): raise
            return False

        except ValueError: return False

    def is_mount(self) -> bool:
        """
        Check if this path is a POSIX mount point
        """
        # Need to exist and be a dir
        if not self.exists() or not self.is_dir(): return False

        try:
            parent_stat = self.parent.stat()
            parent_dev = parent_stat.st_dev
        except OSError: return False

        stat = self.stat()
        dev = stat.st_dev
        return True if dev != parent_dev \
            else stat.st_ino == parent_stat.st_ino

    async def ais_mount(self) -> bool:
        """
        Check if this path is a POSIX mount point
        """
        # Need to exist and be a dir
        if not await self.aexists() or not await self.ais_dir(): return False

        try:
            parent_stat = await self.parent.astat()
            parent_dev = parent_stat.st_dev
        except OSError: return False

        stat = await self.astat()
        dev = stat.st_dev
        return True if dev != parent_dev \
            else stat.st_ino == parent_stat.st_ino

    def is_block_device(self) -> bool:
        """
        Whether this path is a block device.
        """
        try:
            stat = self.stat()
            return S_ISBLK(stat.st_mode)

        except OSError as e:
            if not _ignore_error(e): raise
            return False

        except ValueError: return False

    async def ais_block_device(self) -> bool:
        """
        Whether this path is a block device.
        """
        try:
            stat = await self.astat()
            return S_ISBLK(stat.st_mode)

        except OSError as e:
            if not _ignore_error(e): raise
            return False

        except ValueError: return False

    def is_char_device(self) -> bool:
        """
        Whether this path is a character device.
        """
        try:
            stat = self.stat()
            return S_ISCHR(stat.st_mode)
        except OSError as e:
            if not _ignore_error(e): raise
            return False
        except ValueError: return False
    
    async def ais_char_device(self) -> bool:
        """
        Whether this path is a character device.
        """
        try:
            stat = await self.stat()
            return S_ISCHR(stat.st_mode)
        except OSError as e:
            if not _ignore_error(e): raise
            return False
        except ValueError: return False

    def is_fifo(self) -> bool:
        """
        Whether this path is a FIFO.
        """
        try:
            stat = self.stat()
            return S_ISFIFO(stat.st_mode)
        except OSError as e:
            if not _ignore_error(e): raise
            return False
        except ValueError: return False

    async def ais_fifo(self) -> bool:
        """
        Whether this path is a FIFO.
        """
        try:
            stat = await self.astat()
            return S_ISFIFO(stat.st_mode)
        except OSError as e:
            if not _ignore_error(e): raise
            return False
        except ValueError: return False

    def is_socket(self) -> bool:
        """
        Whether this path is a socket.
        """
        try:
            stat = self.stat()
            return S_ISSOCK(stat.st_mode)
        except OSError as e:
            if not _ignore_error(e): raise
            return False
        except ValueError: return False
    
    async def ais_socket(self) -> bool:
        """
        Whether this path is a socket.
        """
        try:
            stat = await self.astat()
            return S_ISSOCK(stat.st_mode)
        except OSError as e:
            if not _ignore_error(e): raise
            return False
        except ValueError: return False

    def expanduser(self) -> FilePath:
        """ Return a new path with expanded ~ and ~user constructs
        (as returned by os.path.expanduser)
        """
        if (not self._drv and not self._root and self._parts and self._parts[0][:1] == '~'):
            homedir = self._flavour.gethomedir(self._parts[0][1:])
            return self._from_parts([homedir] + self._parts[1:])
        return self
    
    async def aexpanduser(self) -> FilePath:
        """ Return a new path with expanded ~ and ~user constructs
        (as returned by os.path.expanduser)
        """
        if (not self._drv and not self._root and self._parts and self._parts[0][:1] == '~'):
            homedir = await self._flavour.agethomedir(self._parts[0][1:])
            return self._from_parts([homedir] + self._parts[1:])
        return self

    def iterdir(self) -> t.Iterable[FilePath]:
        names = self._accessor.listdir(self)
        for name in names:
            if name in {'.', '..'}: continue
            yield self._make_child_relpath(name)
    
    async def aiterdir(self) -> t.AsyncIterable[FilePath]:
        names = await self._accessor.alistdir(self)
        for name in names:
            if name in {'.', '..'}: continue
            yield self._make_child_relpath(name)

    def _raise_closed(self):
        raise ValueError("I/O operation on closed path")
    
    def _raise_open(self):
        raise ValueError("I/O operation on already open path")
    
    def prepare(
        self, 
        dir_mode: t.Optional[int] = 511, 
        parents: t.Optional[bool] = True, 
        exist_ok: t.Optional[bool] = True, 
        touch: t.Optional[bool] = None, 
        file_mode: t.Optional[int] = 438,
        **kwargs
    ):
        """
        Prepare the file for I/O operations
        - will create the parent directory if it doesn't exist
        - only handles local filesystem operations
        """
        if self.is_fsspec: return
        if self.is_file():
            self.parent.mkdir(mode = dir_mode, parents = parents, exist_ok = exist_ok)
            if touch: self.touch(mode = file_mode, exist_ok = exist_ok)
        else:
            self.mkdir(mode = dir_mode, parents = parents, exist_ok = exist_ok)
    
    async def aprepare(
        self,
        dir_mode: t.Optional[int] = 511,
        parents: t.Optional[bool] = True, 
        exist_ok: t.Optional[bool] = True, 
        touch: t.Optional[bool] = None, 
        file_mode: t.Optional[int] = 438,
        **kwargs
    ):
        """
        Prepare the file for I/O operations
        - will create the parent directory if it doesn't exist
        - only handles local filesystem operations
        """
        if self.is_fsspec: return
        if self.is_file():
            await self.parent.amkdir(mode = dir_mode, parents = parents, exist_ok = exist_ok)
            if touch: await self.atouch(mode = file_mode, exist_ok = exist_ok)
        else:
            await self.amkdir(mode = dir_mode, parents = parents, exist_ok = exist_ok)
    
    @classmethod
    def get_object_size(cls, obj: t.Any) -> ObjectSize:
        """
        Returns the size of the object
        """
        return ObjectSize(obj)

    # We sort of assume that it will be used to open a file
    def __enter__(self):
        #if self._fileio: self._raise_open()
        #if not self._fileio:
        #    self._fileio = self.open()
        if self._closed: self._raise_closed()
        return self

    def __exit__(self, t, v, tb):
        self._closed = True
    
    async def __aenter__(self):
        if self._closed: self._raise_closed()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._closed = True



try:
    from pydantic_core import core_schema
    from pydantic import GetCoreSchemaHandler, ValidationInfo
    _has_pydantic_validator = True
except ImportError:
    _has_pydantic_validator = False



class FilePosixPath(PosixPath, FilePath, PureFilePosixPath):
    __slots__ = ()

    if _has_pydantic_validator:
        @classmethod
        def pydantic_validate(cls, value: t.Union[str, Path]) -> 'FilePosixPath':
            """
            Validate the value of the path
            """
            return cls(value)

        @classmethod
        def __get_pydantic_core_schema__(
            cls, 
            source_type: t.Any, 
            handler: GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            """
            Get the Pydantic CoreSchema for the given source
            """
            from_str_schema = core_schema.chain_schema(
                [
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(cls.pydantic_validate),
                ]
            )
            return core_schema.json_or_python_schema(
                json_schema=from_str_schema,
                python_schema = core_schema.union_schema(
                    [
                        # check if it's an instance first before doing any further work
                        core_schema.is_instance_schema(FilePosixPath),
                        from_str_schema,
                    ]
                ),
                serialization = core_schema.plain_serializer_function_ser_schema(
                    lambda instance: instance.as_posix()
                ),
            )


class FileWindowsPath(WindowsPath, FilePath, PureFileWindowsPath):
    __slots__ = ()


os.PathLike.register(FilePurePath)
os.PathLike.register(FilePath)
os.PathLike.register(PureFilePosixPath)
os.PathLike.register(FileWindowsPath)
os.PathLike.register(FilePosixPath)
os.PathLike.register(PureFileWindowsPath)