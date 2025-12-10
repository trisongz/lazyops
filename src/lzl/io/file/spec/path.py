from __future__ import annotations

"""
The Pathlib Implementation for Cloud Filesystems
"""

import io
import os
import hashlib
import datetime
import functools
import asyncio
import posixpath
import ntpath
import typing as t
from fsspec.callbacks import Callback
from aiopath.wrap import to_thread
from aiopath.handle import IterableAIOFile
from pydantic.types import ByteSize
from lzl.pool import ThreadPool
from lzl.io import aio
from lzl.types import PYDANTIC_VERSION, eproperty

from ..types.errors import FileExistsError
from ..types.misc import ObjectSize
from ..utils import logger
from ..path import PurePath, Path, FileMode, DEFAULT_ENCODING, ON_ERRORS, NEWLINE, Paths, PosixPath, WindowsPath
from ..path.flavours import _pathz_windows_flavour, _pathz_posix_flavour, _pathz_default_flavor
from .static.content_types import CONTENT_TYPE_BY_EXTENSION
# from .providers.main import AccessorLike, FileSystemLike, ProviderManager
from .utils import get_async_file, get_fsspec_file, AsyncFile
from ..types.enhanced import EnhancedAsyncMixin


if t.TYPE_CHECKING:
    from .providers.main import AccessorLike
    from .main import FileLike, PathLike
    from fsspec.asyn import AsyncFileSystem
    from fsspec.spec import AbstractFileSystem
    from s3transfer.manager import TransferManager
    from ..configs.main import ProviderConfig


    _FST = t.TypeVar('_FST', bound=AbstractFileSystem)
    _ASFST = t.TypeVar('_ASFST', bound=AsyncFileSystem)


class AsyncTransactionContext:
    """
    Async Context Manager wrapper for fsspec transactions.
    """
    def __init__(self, transaction):
        self.transaction = transaction

    async def __aenter__(self):
        self.transaction.__enter__()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        # Offload the synchronous commit/rollback to a thread to avoid blocking
        await ThreadPool.run_async(
            self.transaction.__exit__, exc_type, exc_value, traceback
        )


class CloudFileSystemPurePath(PurePath):
    _prefix: str = None
    _provider: str = None
    _win_pathz: t.ClassVar['PureCloudFileSystemWindowsPath'] = 'PureCloudFileSystemWindowsPath'
    _posix_pathz: t.ClassVar['PureCloudFileSystemPosixPath'] = 'PureCloudFileSystemPosixPath'

    def _init(self, template: t.Optional[PurePath] = None):
        from .providers.main import ProviderManager
        self._accessor = self._get_provider_accessor(self._prefix)

    def __new__(cls: t.Union[t.Type[CloudFileSystemPurePath], t.Type[PurePath]], *args):
        if cls is CloudFileSystemPurePath or issubclass(cls, CloudFileSystemPurePath):
            cls = cls._posix_pathz if os.name != 'nt' else cls._win_pathz
            cls = globals()[cls]
        return cls._from_parts(args)

    def _new(self, *parts):
        """Create a new `Path` child of same type."""
        return type(self)(*parts)
    
    @classmethod
    def _get_provider_accessor(cls, prefix: str) -> 'AccessorLike':
        """
        Returns the accessor for the provider
        """
        from .providers.main import ProviderManager
        return ProviderManager.get_accessor(prefix)
    
    

class PureCloudFileSystemPosixPath(CloudFileSystemPurePath):
    """PurePath subclass for non-Windows systems.
    On a POSIX system, instantiating a PurePath should return this object.
    However, you can also instantiate it directly on any system.
    """
    _flavour = _pathz_posix_flavour
    _pathlike = posixpath
    __slots__ = ()


class PureCloudFileSystemWindowsPath(CloudFileSystemPurePath):
    """PurePath subclass for Windows systems.
    On a Windows system, instantiating a PurePath should return this object.
    However, you can also instantiate it directly on any system.
    """
    _flavour = _pathz_windows_flavour
    _pathlike = ntpath
    __slots__ = ()



CloudPathT = t.TypeVar('CloudPathT', bound = 'CloudFileSystemPath')

class CloudFileSystemPath(Path, CloudFileSystemPurePath, EnhancedAsyncMixin):
    """
    Our customized class that incorporates both sync and async methods
    """
    _flavour = _pathz_default_flavor
    _accessor: 'AccessorLike' = None
    _pathlike = posixpath
    _prefix = None
    _provider = None
    _win_pathz: t.ClassVar['CloudFileSystemWindowsPath'] = 'CloudFileSystemWindowsPath'
    _posix_pathz: t.ClassVar['CloudFileSystemPosixPath'] = 'CloudFileSystemPosixPath'

    def _init(self, template: t.Optional['CloudFileSystemPath'] = None):
        self._accessor = self._get_provider_accessor(self._prefix)
        self._closed = False
        self._fileio = None
        self._extra: t.Dict[str, t.Any] = {}

    def __new__(cls: t.Union[t.Type['CloudFileSystemPath'], t.Type[CloudPathT]], *parts, **kwargs) -> t.Union['CloudFileSystemPath', CloudPathT]:
        if cls is CloudFileSystemPath or issubclass(cls, CloudFileSystemPath):
            cls = cls._win_pathz if os.name == 'nt' else cls._posix_pathz
            cls = globals()[cls]
        self = cls._from_parts(parts, init=False)
        if not self._flavour.is_supported:
            name: str = cls.__name__
            raise NotImplementedError(f"cannot instantiate {name} on your system")

        self._init()
        return self

    def __repr__(self):
        return f'{self.__class__.__name__}("{self.string}")'

    def __str__(self):
        return self.string
    

    if PYDANTIC_VERSION == 2:
        if t.TYPE_CHECKING:
            from pydantic_core import core_schema
            from pydantic.annotated_handlers import GetCoreSchemaHandler, GetJsonSchemaHandler
            from pydantic.json_schema import JsonSchemaValue

        @classmethod
        def _get_filelike_(cls, *args, **kwargs) -> 'FileLike':
            """
            Returns the FileLike
            """
            from .main import get_filelike
            return get_filelike(*args, **kwargs)
        
        @classmethod
        def __get_pydantic_json_schema__(
            cls, 
            core_schema: 'core_schema.CoreSchema', 
            handler: 'GetJsonSchemaHandler'
        ) -> 'JsonSchemaValue':
            
            field_schema = handler(core_schema)
            field_schema.update(format = 'path', type = 'string')
            return field_schema

        @classmethod
        def __get_pydantic_core_schema__(
            cls, 
            source: type[t.Any], 
            handler: 'GetCoreSchemaHandler'
        ) -> 'core_schema.CoreSchema':
            """
            Get the Pydantic CoreSchema for the given source
            """
            from pydantic_core import core_schema, SchemaSerializer
            schema = core_schema.with_info_plain_validator_function(
                cls._validate,
                serialization = core_schema.to_string_ser_schema(),
            )
            cls.__pydantic_serializer__ = SchemaSerializer(schema)
            return schema

        @classmethod
        def _validate(cls, __input_value: t.Any, _: 'core_schema.ValidationInfo') -> 'FileLike':
            """
            Validator for Pydantic v2
            """
            return cls._get_filelike_(__input_value) if __input_value is not None else None

        def __hash__(self: 'FileLike') -> int:
            return hash(self.as_posix())

    @property
    def parent(self) -> 'FileLike':
        """
        The logical parent of the path.
        """
        return super().parent
    
    @property
    def filesys(self) -> t.Optional['AbstractFileSystem']:
        """
        Returns the filesystem object
        """
        return getattr(self._accessor, 'filesys', None)

    @property
    def afilesys(self) -> t.Optional['AsyncFileSystem']:
        """
        The async filesystem object associated with this path.
        """
        return getattr(self._accessor, 'afilesys', None)
    
    @property
    def fsconfig(self) -> 'ProviderConfig':
        """
        Returns the FileSystemConfig
        """
        return self._accessor.fsconfig
    

    @property
    def is_fsspec(self) -> bool:
        """
        Returns True if the path is a fsspec accessor
        """
        return self._accessor.is_fsspec
    
    @property
    def is_cloud_obj_(self) -> bool:
        """
        Returns True if the path is a cloud object
        """
        return self.is_fsspec

    @property
    def is_local_obj_(self) -> bool:
        """
        Returns True if the path is a local object
        """
        return not self.is_fsspec

    @property
    def fspath_(self) -> str:
        """
        Returns the `__fspath__` string representation without the uri_scheme
        """
        # Mirrors _cloudpath
        if self._prefix in self.parts[0]: return self._pathlike.join(*self.parts[1:])
        return self._pathlike.join(*self.parts)
    
    @property
    def fsuri_(self) -> t.Optional[str]:
        """
        Reconstructs the proper Fsspec URI
        """
        # Mirrors _cloudstr
        if self._prefix not in self.parts[0]:
            return f'{self._prefix}://' + '/'.join(self.parts)
        return f'{self._prefix}://' + '/'.join(self.parts[1:])
    
    @property
    def bucket_(self) -> str:
        """
        Returns the `__fspath__` string representation without the uri_scheme
        """
        return self.parts[1] if self._prefix in self.parts[0] \
            else self.parts[0]
    
    @property
    def bucketstr_(self) -> t.Optional[str]:
        """
        Returns the `__fspath__` string representation without the uri_scheme
        """
        return f'{self._prefix}://{self.bucket_}'

    @property
    def string(self) -> str:
        """
        Return the string representation of the path with forward (/)
        """
        return self.fsuri_ if self.is_fsspec else self.posix_
    
    @property
    def posix_(self):
        """Return the string representation of the path with forward (/)
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
    def pathkeys_(self) -> str:
        """
        Returns the `__fspath__` string representation without the uri_scheme
        """
        if self.bucket_ in self.parts[0]: return self._pathlike.join(*self.parts[1:])
        if self.bucket_ in self.parts[1]: return self._pathlike.join(*self.parts[2:])
        return self._pathlike.join(*self.parts)

    def get_path_key(self, filename: t.Optional[str] = None) -> str:
        """
        Used to return relative/path/to/file.ext
        """
        filename = filename or self.name
        parts = None
        if self.bucket_ in self.parts[0]: parts = self.parts[1:-1]
        elif self.bucket_ in self.parts[1]: parts = self.parts[2:-1]
        else: parts = self.parts[:-1]
        return self._pathlike.join(*parts, filename)


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
    def stat_(self) -> os.stat_result:
        """
        Returns the stat results for path
        """
        return self.stat()

    @property
    def hash_(self) -> str:
        """
        Hash of file properties, to tell if it has changed
        """
        return self._accessor.ukey(self.fspath_)
    

    @property
    def info_(self):
        """
        Return info of path
        """
        return self._accessor.info(path=self.fspath_)

    @property
    def metadata_(self):
        """
        Return metadata of path
        """
        return self._accessor.metadata(self.fspath_)

    @property
    def path_info_(self):
        """
        Return info of path
        """
        return self._accessor.info(path=self.fspath_)
    

    @property
    def size_(self) -> t.Optional[t.Union[float, int]]:
        """
        Size in bytes of file
        """
        return self._accessor.size(self.fspath_) if self.is_file() else None

    @property
    def bytesize_(self) -> t.Optional['ByteSize']:
        """
        ByteSize in bytes of file
        """
        return self.bytesize()
    
    @property
    def fss3tm(self) -> t.Optional['TransferManager']:
        """
        Returns the s3t transfer manager
        """
        if self._accessor._s3t is not None:
            return self._accessor.get_s3t()
        raise NotImplementedError('S3 Transfer Manager is not Supported for this File System')
    
    
    @property
    def etag(self) -> t.Optional[str]:
        """
        Returns the etag of the file

        Cleans up the quoted string
        """
        _info = self.info()
        etag = _info.get('ETag', _info.get('etag'))
        return etag.strip('"') if etag else None
    
    @eproperty
    def checksum(self) -> str:
        """
        Returns the checksum of the file
        """
        from lzl.io.file.types.utils import generate_checksum
        return generate_checksum(self)
    
    @property
    def last_modified_(self) -> t.Optional[datetime.datetime]:
        """
        Returns the last modified time of the file
        """
        _info = self.info()
        return _info.get('LastModified', _info.get('last_modified'))
    
    @eproperty
    def content_type_(self) -> t.Optional[str]:
        """
        Returns the content type of the file
        """
        _info = self.info()
        return _info.get('ContentType', _info.get('content_type'))


    def open(self, mode: FileMode = 'r', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, block_size: int = 5242880, compression: str = None, **kwargs: t.Any) -> t.IO[t.Union[str, bytes]]:
        """
        Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        return self._accessor.open(self.fspath_, mode=mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline)

    def aopen(self, mode: FileMode = 'r', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, block_size: int = 5242880, compression: str = None, **kwargs: t.Any) -> AsyncFile:
        """
        Asyncronously Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        compression = infer doesn't work all that well.
        """
        return get_async_file(self._accessor.open(self.fspath_, mode=mode, encoding=encoding, errors=errors, block_size=block_size, compression=compression, newline=newline, buffering=buffering, **kwargs))

    def iter_raw(self, chunk_size: t.Optional[int] = None) -> t.Iterator[bytes]:
        """
        Iterates over the bytes of a file
        """
        from lzl.io.file.utils.decoders import ByteChunker
        chunker = ByteChunker(chunk_size = chunk_size)
        with self._accessor.open(self.fspath_, 'rb', block_size = chunk_size) as stream:
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


    async def aiter_raw(self, chunk_size: t.Optional[int] = None, optimized: t.Union[bool, str] = 'auto') -> t.AsyncIterator[bytes]:
        """
        Iterates over the bytes of a file
        """
        if optimized is True:
            async for chunk in self.aiter_raw_optimized(chunk_size=chunk_size):
                yield chunk
            return
        elif optimized == 'auto':
            try:
                # Auto-optimization: Use optimized iter for files > 5MB
                if await self.asize() > 5 * 1024 * 1024:
                    async for chunk in self.aiter_raw_optimized(chunk_size=chunk_size):
                        yield chunk
                    return
            except Exception:
                pass

        from lzl.io.file.utils.decoders import ByteChunker
        chunker = ByteChunker(chunk_size = chunk_size)
        chunk_size = chunk_size if chunk_size is not None else -1
        async with await self.afilesys.open_async(self.fspath_, 'rb', block_size = chunk_size) as stream:
            raw_stream_bytes = await stream.read(chunk_size)
            while raw_stream_bytes:
                for chunk in chunker.decode(raw_stream_bytes):
                    yield chunk
                raw_stream_bytes = await stream.read(chunk_size)
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


    def copy_to(self, dest: 'PathLike', overwrite: bool = False, chunk_size: t.Optional[int] = None, **kwargs) -> 'FileLike':
        """
        Copies this file to the destination path.
        """
        dst = self.get_pathlike_(dest)
        if not overwrite and dst.exists():
            raise FileExistsError(f"Destination file {dst} exists and overwrite is False")
        with dst.open('wb') as f:
            for chunk in self.iter_raw(chunk_size = chunk_size):
                f.write(chunk)
        return dst
    
    async def acopy_to(self, dest: 'PathLike', overwrite: bool = False, chunk_size: t.Optional[int] = None, optimized: t.Union[bool, str] = 'auto', **kwargs) -> 'FileLike':
        """
        Copies this file to the destination path.
        """
        dst = self.get_pathlike_(dest)
        
        if optimized is True:
            return await self.acopy_to_optimized(dst, overwrite=overwrite, chunk_size=chunk_size, **kwargs)
        elif optimized == 'auto':
            try:
                # Auto-optimization: Use optimized copy for files > 5MB
                if await self.asize() > 5 * 1024 * 1024:
                    return await self.acopy_to_optimized(dst, overwrite=overwrite, chunk_size=chunk_size, **kwargs)
            except Exception:
                pass

        if not overwrite and await dst.aexists():
            raise FileExistsError(f"Destination file {dst} exists and overwrite is False")
        async with dst.aopen('wb') as f:
            async for chunk in self.aiter_raw(chunk_size = chunk_size):
                await f.write(chunk)
        return dst

    def reader(self, mode: FileMode = 'r', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, block_size: int = 5242880, compression: str = None, **kwargs: t.Any) -> t.IO[t.Union[str, bytes]]:
        """
        Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        return self._accessor.open(self.fspath_, mode=mode, buffering=buffering, encoding=encoding, errors=errors, block_size=block_size, compression=compression, newline=newline, **kwargs)

    def areader(self, mode: FileMode = 'r', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, block_size: int = 5242880, compression: str = None, **kwargs: t.Any) -> AsyncFile:
        """
        Asyncronously Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        return get_async_file(self._accessor.open(self.fspath_, mode=mode, buffering=buffering, encoding=encoding, errors=errors, block_size=block_size, compression=compression, newline=newline, **kwargs))

    def appender(self, mode: FileMode = 'a', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, block_size: int = 5242880, compression: str = None, **kwargs: t.Any) -> t.IO[t.Union[str, bytes]]:
        """
        Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        return self._accessor.open(self.fspath_, mode=mode, buffering=buffering, encoding=encoding, errors=errors, block_size=block_size, compression=compression, newline=newline, **kwargs)

    def aappender(self, mode: FileMode = 'a', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, block_size: int = 5242880, compression: str = None, **kwargs: t.Any) -> IterableAIOFile:
        """
        Asyncronously Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        return get_async_file(self._accessor.open(self.fspath_, mode=mode, buffering=buffering, encoding=encoding, errors=errors, block_size=block_size, compression=compression, newline=newline, **kwargs))

    def writer(self, mode: FileMode = 'w', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, block_size: int = 5242880, compression: str = None, **kwargs: t.Any) -> t.IO[t.Union[str, bytes]]:
        """
        Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        #self.touch()
        return self._accessor.open(self.fspath_, mode=mode, buffering=buffering, encoding=encoding, errors=errors, block_size=block_size, compression=compression, newline=newline, **kwargs)

    def awriter(self, mode: FileMode = 'w', buffering: int = -1, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, block_size: int = 5242880, compression: str = None, **kwargs: t.Any) -> IterableAIOFile:
        """
        Asyncronously Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        #self.touch()
        return get_async_file(self._accessor.open(self.fspath_, mode=mode, buffering=buffering, encoding=encoding, errors=errors, block_size=block_size, compression=compression, newline=newline, **kwargs))

    def _read_chunked_with_tmgr(self, mode: str = 'rb', start: t.Optional[t.Any] = None, end: t.Optional[t.Any] = None,  encoding: t.Optional[str] = DEFAULT_ENCODING, errors: str | None = ON_ERRORS,  **kwargs) -> t.Union[bytes, str]:
        # sourcery skip: class-extract-method
        """
        Read the data to the file with a transfer manager
        """
        # logger.info(f'Reading Chunked Data with TMGR: {self.fsuri_}')
        bytes_io = io.BytesIO()
        future = self.fss3tm.download(
            self.bucket_,
            self.get_path_key(self.name),
            bytes_io,
        )
        try:
            future.result()
        except Exception as e:
            if 'We encountered an internal error' in str(e):
                logger.error(f'Error reading chunked with TMGR: {e}')
                return self._read_chunked_default(mode = mode, start = start, end = end, encoding = encoding, errors = errors, **kwargs)
            raise e
        bytes_io.seek(0)
        if 'b' in mode: 
            if start: bytes_io.seek(start)
            if end: bytes_io.truncate(end)
            return bytes_io.getvalue()
        return io.TextIOWrapper(bytes_io, encoding = encoding, errors = errors, **kwargs).read()
    
    async def _aread_chunked_with_tmgr(self, mode: str = 'rb', start: t.Optional[t.Any] = None, end: t.Optional[t.Any] = None,  encoding: t.Optional[str] = DEFAULT_ENCODING, errors: str | None = ON_ERRORS,  **kwargs) -> t.Union[bytes, str]:
        # sourcery skip: class-extract-method
        """
        Read the data to the file with a transfer manager
        """
        # logger.info(f'Reading Chunked Data with TMGR: {self.fsuri_}')
        bytes_io = io.BytesIO()
        future = self.fss3tm.download(
            self.bucket_,
            self.get_path_key(self.name),
            bytes_io,
        )
        try:
            await ThreadPool.asyncish(future.result)
        except Exception as e:
            if 'We encountered an internal error' in str(e):
                logger.error(f'Error reading chunked with TMGR: {e}')
                return await self._aread_chunked_default(mode = mode, start = start, end = end, encoding = encoding, errors = errors, **kwargs)
            raise e
        # future.result()
        bytes_io.seek(0)
        if 'b' in mode: 
            if start: bytes_io.seek(start)
            if end: bytes_io.truncate(end)
            return bytes_io.getvalue()
        return io.TextIOWrapper(bytes_io, encoding = encoding, errors = errors, **kwargs).read()
    
    
    def _read_chunked_default(self, mode: str = 'rb', start: t.Optional[t.Any] = None, end: t.Optional[t.Any] = None,  encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE) -> t.Union[bytes, str]:
        """
        Read the data to the file with default iterator
        """
        # logger.info(f'Reading Chunked Data with Default: {self.fsuri_}')
        _open_kwargs = {
            'encoding': encoding,
            'errors': errors,
            'newline': newline,
        } if 'b' not in mode else {}
        
        io_obj = io.BytesIO() if 'b' in mode else io.StringIO()
        _default = b'' if 'b' in mode else ''
        
        with self.open(mode = mode, **_open_kwargs) as f:
            for chunk in iter(lambda: f.read(self._accessor.fsconfig.read_chunking_size), _default):
                io_obj.write(chunk)
        io_obj.seek(0)
        if 'b' in mode: 
            if start: io_obj.seek(start)
            if end: io_obj.truncate(end)
        return io_obj.getvalue()
    
    async def _aread_chunked_default(self, mode: str = 'rb', start: t.Optional[t.Any] = None, end: t.Optional[t.Any] = None,  encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE) -> t.Union[bytes, str]:
        """
        Read the data to the file with default iterator
        """
        # logger.info(f'Reading Chunked Data with Default: {self.fsuri_}')
        _open_kwargs = {
            'encoding': encoding,
            'errors': errors,
            'newline': newline,
        } if 'b' not in mode else {}
        
        io_obj = aio.BytesIO() if 'b' in mode else aio.StringIO()
        async with self.aopen(mode = mode, **_open_kwargs) as f:
            block = await f.read(self._accessor.fsconfig.read_chunking_size)
            while block:
                io_obj.write(block)
                block = await f.read(self._accessor.fsconfig.read_chunking_size)
            # for chunk in await iter(lambda: f.read(self._accessor.fsconfig.read_chunking_size), _default):
            #     await io_obj.write(chunk)
        await io_obj.seek(0)
        if 'b' in mode: 
            if start: await io_obj.seek(start)
            if end: await io_obj.truncate(end)
        return io_obj.getvalue()

    def read_chunked_data(self, mode: str = 'rb', start: t.Optional[t.Any] = None, end: t.Optional[t.Any] = None, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, **kwargs) -> t.Union[int, ObjectSize]:
        # sourcery skip: extract-method
        """
        Open the file in bytes mode, write to it, and close the file.
        """
        obj_size = self.get_object_size(self.size())
        if self._has_tmgr and (self.fsconfig.read_chunking_manager_default or obj_size > self.fsconfig.read_chunking_large_size):
            try:
                return self._read_chunked_with_tmgr(mode = mode, start = start, end = end, encoding = encoding, errors = errors, newline = newline, **kwargs)
            except Exception as e:
                logger.error(f'Error Reading Chunked Data: {e}')
        return self._read_chunked_default(mode = mode, start = start, end = end, encoding = encoding, errors = errors, newline = newline, **kwargs)

    def aread_chunked_data(self, mode: str = 'rb', start: t.Optional[t.Any] = None, end: t.Optional[t.Any] = None, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, **kwargs) -> t.Union[int, ObjectSize]:
        # sourcery skip: extract-method
        """
        Open the file in bytes mode, write to it, and close the file.
        """
        obj_size = self.get_object_size(self.size())
        if self._has_tmgr and (self.fsconfig.read_chunking_manager_default or obj_size > self.fsconfig.read_chunking_large_size):
            try:
                return self._aread_chunked_with_tmgr(mode = mode, start = start, end = end, encoding = encoding, errors = errors, newline = newline, **kwargs)
            except Exception as e:
                logger.error(f'Error Reading Chunked Data: {e}')
        return self._aread_chunked_default(mode = mode, start = start, end = end, encoding = encoding, errors = errors, newline = newline, **kwargs)

    def read(self, mode: FileMode = 'rb', size: t.Optional[int] = -1, offset: t.Optional[int] = 0, **kwargs) -> t.Union[str, bytes]:
        """
        Read and return the file's contents.
        """
        with self.open(mode=mode, **kwargs) as file:
            if offset: file.seek(offset)
            return file.read(size)
        
    async def aread(self, mode: FileMode = 'rb', size: t.Optional[int] = -1, offset: t.Optional[int] = 0, optimized: t.Union[bool, str] = 'auto', **kwargs):
        """
        Read and return the file's contents.
        """
        if optimized is True:
            return await self.aread_optimized(mode=mode, **kwargs)
        elif optimized == 'auto':
            try:
                # Auto-optimization: Use optimized read for files > 5MB
                if await self.asize() > 5 * 1024 * 1024:
                    return await self.aread_optimized(mode=mode, **kwargs)
            except Exception:
                pass

        async with self.aopen(mode=mode, **kwargs) as file:
            if offset: await file.seek(offset)
            return await file.read(size = size)

    def read_text(self, encoding: str | None = DEFAULT_ENCODING, errors: str | None = ON_ERRORS, **kwargs) -> str:
        """
        Read and return the file's contents.
        """
        if self.fsconfig.read_chunking_enabled:
            return self.read_chunked_data(mode = 'r', encoding = encoding, errors = errors, **kwargs)
        if hasattr(self.filesys, 'read_text'):
            return self.filesys.read_text(self.fspath_, encoding=encoding, errors=errors, **kwargs)
        with self.open('r', encoding=encoding, errors=errors) as file:
            return file.read()

    async def aread_text(self, encoding: str | None = DEFAULT_ENCODING, errors: str | None = ON_ERRORS, **kwargs) -> str:
        """
        Read and return the file's contents.
        """
        if self.fsconfig.read_chunking_enabled:
            return await self.aread_chunked_data(mode = 'r', encoding = encoding, errors = errors, **kwargs)
        async with self.aopen('r', encoding=encoding, errors=errors, **kwargs) as file:
            return await file.read()

    def read_bytes(self, start: t.Optional[t.Any] = None, end: t.Optional[t.Any] = None, **kwargs) -> bytes:
        """
        Read and return the file's contents.
        """
        if self.fsconfig.read_chunking_enabled:
            return self.read_chunked_data(mode = 'rb', start = start, end = end, **kwargs)
        if hasattr(self.filesys, 'read_bytes'):
            return self.filesys.read_bytes(self.fspath_, start=start, end=end)
        return self._accessor.cat_file(self.fspath_, start = start, end = end, **kwargs)

    async def aread_bytes(self, start: t.Optional[t.Any] = None, end: t.Optional[t.Any] = None, **kwargs) -> bytes:
        """
        Read and return the file's contents.
        """
        # async with self.aopen('rb') as file:
        #     return await file.read()
        if self.fsconfig.read_chunking_enabled:
            return await self.aread_chunked_data(mode = 'rb', start = start, end = end, **kwargs)
        return await self._accessor.acat_file(self.fspath_, start = start, end = end, **kwargs)

    def _guess_content_type(self) -> t.Optional[str]:
        """
        Guess the content type of the file
        """
        return CONTENT_TYPE_BY_EXTENSION.get(self.suffix, None)
    
    # def iter_bytes(self, chunk_size: int | None = None) -> t.Iterator[bytes]:
    #     """
    #     A byte-iterator over the decoded response content.
    #     """
    #     # _open_kwargs = {
    #     #     'encoding': encoding,
    #     #     'errors': errors,
    #     #     'newline': newline,
    #     # } if 'b' not in mode else {}
        
    #     # io_obj = io.BytesIO() if 'b' in mode else io.StringIO()
    #     # _default = b'' if 'b' in mode else ''
    #     chunk_size = chunk_size or self._accessor.fsconfig.read_chunking_size
    #     with self.open(mode = 'rb',) as f:
    #         for chunk in iter(lambda: f.read(chunk_size), b''):
    #             yield chunk

    # def iter_text(self, chunk_size: t.Optional[int] = None, **kwargs) -> t.Iterator[str]:
    #     """
    #     Iterates over the text in the file
    #     """


    @property
    def _has_tmgr(self) -> bool:
        """
        Checks if the file has a transfer manager
        """
        return self._accessor._s3t is not None
    
    def _write_chunked_with_tmgr(self, data: t.Union[bytes, str], obj_size: 'ObjectSize', encoding: t.Optional[str] = DEFAULT_ENCODING, **kwargs) -> 'ObjectSize':
        # sourcery skip: class-extract-method
        """
        Writes the data to the file with a transfer manager
        """
        if not isinstance(data, bytes): data = data.encode(encoding)
        obj_data = io.BytesIO(data)
        extra_args = {}
        if content_type := self._guess_content_type(): extra_args['ContentType'] = content_type
        future = self.fss3tm.upload(
            obj_data,
            self.bucket_,
            self.get_path_key(self.name),
            extra_args = extra_args,
        )
        # ThreadPool.threadpool_task(future.result)
        future.result()
        # Need to invalidate the cache since it 
        # isn't done in the fsspec library
        self.invalidate_cache()
        return obj_size

    async def _awrite_chunked_with_tmgr(self, data: t.Union[bytes, str], obj_size: 'ObjectSize', encoding: t.Optional[str] = DEFAULT_ENCODING, **kwargs) -> 'ObjectSize':
        # sourcery skip: class-extract-method
        """
        Writes the data to the file with a transfer manager
        """
        if not isinstance(data, bytes): data = data.encode(encoding)
        obj_data = io.BytesIO(data)
        extra_args = {}
        if content_type := self._guess_content_type(): extra_args['ContentType'] = content_type
        future = self.fss3tm.upload(
            obj_data,
            self.bucket_,
            self.get_path_key(self.name),
            extra_args = extra_args,
        )
        await ThreadPool.run_async(future.result)
        # Need to invalidate the cache since it 
        # isn't done in the fsspec library
        await self.ainvalidate_cache()
        return obj_size
    
    def _write_chunked_default(self, data: t.Union[bytes, str], obj_size: 'ObjectSize', encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE) -> 'ObjectSize':
        """
        Writes the data to the file with default iterator
        """
        obj_data = io.BytesIO(data) if isinstance(data, bytes) else io.StringIO(data)
        mode = 'wb' if isinstance(data, bytes) else 'w'
        default_ = b'' if isinstance(data, bytes) else ''
        _open_kwargs = {
            'encoding': encoding,
            'errors': errors,
            'newline': newline,
        } if mode == 'w' else {}
        with self.open(mode = mode, **_open_kwargs) as f:
            for chunk in iter(lambda: obj_data.read(self._accessor.fsconfig.write_chunking_size), default_):
                f.write(chunk)
        if content_type := self._guess_content_type():
            self.setxattr(copy_kwargs={'ContentType': content_type})
        return obj_size
    
    async def _awrite_chunked_default(self, data: t.Union[bytes, str], obj_size: 'ObjectSize', encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE) -> 'ObjectSize':
        """
        Writes the data to the file with default iterator
        """
        obj_data = aio.BytesIO(data) if isinstance(data, bytes) else aio.StringIO(data)
        mode = 'wb' if isinstance(data, bytes) else 'w'
        _open_kwargs = {
            'encoding': encoding,
            'errors': errors,
            'newline': newline,
        } if mode == 'w' else {}
        async with self.aopen(mode = mode, **_open_kwargs) as f:
            block = await obj_data.read(self._accessor.fsconfig.write_chunking_size)
            while block:
                await f.write(block)
                block = await obj_data.read(self._accessor.fsconfig.write_chunking_size)
        if content_type := self._guess_content_type():
            await self.asetxattr(copy_kwargs={'ContentType': content_type})
        return obj_size

    def write_chunked_data(self, data: t.Union[bytes, str], encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE) -> t.Union[int, ObjectSize]:
        # sourcery skip: extract-method
        """
        Open the file in bytes mode, write to it, and close the file.
        """
        obj_size = self.get_object_size(data)
        if self._has_tmgr and (self.fsconfig.write_chunking_manager_default or obj_size > self._accessor.fsconfig.write_chunking_large_size):
            return self._write_chunked_with_tmgr(data, obj_size)
        return self._write_chunked_default(data, obj_size, encoding = encoding, errors = errors, newline = newline)

    def awrite_chunked_data(self, data: t.Union[bytes, str], encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE) -> t.Union[int, ObjectSize]:
        # sourcery skip: extract-method
        """
        Open the file in bytes mode, write to it, and close the file.
        """
        obj_size = self.get_object_size(data)
        if self._has_tmgr and (self.fsconfig.write_chunking_manager_default or obj_size > self._accessor.fsconfig.write_chunking_large_size):
            return self._awrite_chunked_with_tmgr(data, obj_size)
        return self._awrite_chunked_default(data, obj_size, encoding = encoding, errors = errors, newline = newline)


    def write_bytes(self, data: bytes) -> t.Union[int, ObjectSize]:
        """
        Open the file in bytes mode, write to it, and close the file.
        """
        # type-check for the buffer interface before truncating the file
        if self._accessor.fsconfig.write_chunking_enabled: 
            return self.write_chunked_data(data)
        view = memoryview(data)
        with self.open(mode='wb') as f:
            return f.write(data)

    async def awrite_bytes(self, data: bytes, optimized: t.Union[bool, str] = 'auto') -> int:
        """
        Open the file in bytes mode, write to it, and close the file.
        """
        if optimized is True:
            return await self.awrite_optimized(data, mode='wb')
        elif optimized == 'auto':
            # Auto-optimization: Use optimized write for data > 5MB
            if len(data) > 5 * 1024 * 1024:
                return await self.awrite_optimized(data, mode='wb')

        # type-check for the buffer interface before truncating the file
        if self.fsconfig.write_chunking_enabled: 
            return await self.awrite_chunked_data(data)
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
        if self._accessor.fsconfig.write_chunking_enabled: 
            return self.write_chunked_data(data, encoding = encoding, errors = errors, newline = newline)
        if not isinstance(data, str): raise TypeError(f'data must be str, not {type(data).__name__}')
        # Check if the filesys has `write_text` method
        if hasattr(self.filesys, 'write_text'):
            return self.filesys.write_text(self.fspath_, data, encoding=encoding, errors=errors, newline=newline)
        with self.open(mode='w', encoding=encoding, errors=errors, newline=newline) as f:
            return f.write(data)

    async def awrite_text(self, data: str, encoding: t.Optional[str] = DEFAULT_ENCODING, errors: t.Optional[str] = ON_ERRORS, newline: t.Optional[str] = NEWLINE, optimized: t.Union[bool, str] = 'auto') -> int:
        """
        Open the file in text mode, write to it, and close the file.
        """
        if not isinstance(data, str): raise TypeError(f'data must be str, not {type(data).__name__}')
        
        if optimized is True:
            return await self.awrite_optimized(data, mode='w', encoding=encoding, errors=errors, newline=newline)
        elif optimized == 'auto':
            # Auto-optimization: Use optimized write for data > 5MB
            if len(data) > 5 * 1024 * 1024:
                return await self.awrite_optimized(data, mode='w', encoding=encoding, errors=errors, newline=newline)

        if self.fsconfig.write_chunking_enabled: 
            return await self.awrite_chunked_data(data, encoding = encoding, errors = errors, newline = newline)
        async with self.aopen(mode='w', encoding=encoding, errors=errors, newline=newline) as f:
            return await f.write(data)


    def touch(self, truncate: bool = True, data = None, exist_ok: bool = True, **kwargs):
        """
        Create this file with the given access mode, if it doesn't exist.
        """
        if exist_ok:
            try: self._accessor.stat(self.fspath_)
            # Avoid exception chaining
            except OSError: pass
            else: return
        try:
            self._accessor.touch(self.fspath_, truncate = truncate, data = data, **kwargs)
        except Exception as e:
            with self.open('wb') as f:
                f.write(b'')
                f.flush()


    async def atouch(self, truncate: bool = True, data = None, exist_ok: bool = True, **kwargs):
        """
        Create this file with the given access mode, if it doesn't exist.
        """
        if exist_ok:
            try: await self._accessor.astat(self.fspath_)
            # Avoid exception chaining
            except OSError: pass
            else: return
        await self._accessor.atouch(self.fspath_, truncate = truncate, data = data, **kwargs)

    def mkdir(self, mode: int = 0o777, parents: bool = True, exist_ok: bool = True):
        """
        Create a new directory at this given path.
        """
        try: self._accessor.mkdir(self.fspath_, parents = parents, exist_ok = exist_ok)

        except FileNotFoundError:
            if not parents or self.parent == self: raise
            self.parent.mkdir(parents=True, exist_ok=True)
            self.mkdir(mode, parents=False, exist_ok=exist_ok)

        except OSError:
            # Cannot rely on checking for EEXIST, since the operating system
            # could give priority to other errors like EACCES or EROFS
            if not exist_ok or not self.is_dir(): raise

    async def amkdir(self, parents: bool = True, exist_ok: bool = True, **kwargs):
        """
        Create a new directory at this given path.
        """
        try: await self._accessor.amkdir(self.fspath_, create_parents = parents, exist_ok = exist_ok, **kwargs)

        except FileNotFoundError:
            if not parents or self.parent == self: raise
            await self.parent.amkdir(parents=True, exist_ok=True, **kwargs)
            await self.amkdir(parents=False, exist_ok=exist_ok, **kwargs)

        except OSError:
            # Cannot rely on checking for EEXIST, since the operating system
            # could give priority to other errors like EACCES or EROFS
            if not exist_ok or not await self.ais_dir(): raise

    async def amakedirs(self, parents: bool = True, exist_ok: bool = True):
        """
        Create a new directory at this given path.
        """
        try: await self._accessor.amakedirs(self.fspath_, exist_ok = exist_ok)

        except FileNotFoundError:
            if not parents or self.parent == self: raise
            await self.parent.amakedirs(exist_ok=True)
            await self.amakedirs(exist_ok=exist_ok)

        except OSError:
            # Cannot rely on checking for EEXIST, since the operating system
            # could give priority to other errors like EACCES or EROFS
            if not exist_ok or not await self.ais_dir(): raise

    async def chmod(self, mode: int):
        """
        Change the permissions of the path, like os.chmod().
        """
        raise NotImplementedError

    async def achmod(self, mode: int):
        """
        Change the permissions of the path, like os.chmod().
        """
        raise NotImplementedError

    def lchmod(self, mode: int):
        """
        Like chmod(), except if the path points to a symlink, the symlink's
        permissions are changed, rather than its target's.
        """
        raise NotImplementedError

    async def alchmod(self, mode: int):
        """
        Like chmod(), except if the path points to a symlink, the symlink's
        permissions are changed, rather than its target's.
        """
        raise NotImplementedError

    def unlink(self, missing_ok: bool = False):
        """
        Remove this file or link.
        If the path is a directory, use rmdir() instead.
        """
        try: self._accessor.rm_file(self.fspath_)
        except FileNotFoundError:
            if not missing_ok: raise

    async def aunlink(self, missing_ok: bool = False):
        """
        Remove this file or link.
        If the path is a directory, use rmdir() instead.
        """
        try: await self._accessor.arm_file(self.fspath_)
        except FileNotFoundError:
            if not missing_ok: raise

    def rm(self, recursive: bool = False, maxdepth: int = None, missing_ok: bool = False):
        """
        Remove this file.
        If the path is a directory, use rmdir() instead.
        """
        try: self._accessor.rm(self.fspath_, recursive = recursive, maxdepth = maxdepth)
        except Exception as e:
            if not missing_ok: raise e


    async def arm(self, recursive: bool = False, maxdepth: int = None, missing_ok: bool = False):
        """
        Remove this file.
        If the path is a directory, use rmdir() instead.
        """
        try: await self._accessor.arm(self.fspath_, recursive = recursive, maxdepth = maxdepth)
        except Exception as e:
            if not missing_ok: raise e

    def rm_file(self, missing_ok: bool = True):
        """
        Remove this file.
        If the path is a directory, use rmdir() instead.
        """
        try:
            self._accessor.rm_file(self.fspath_)
            return True
        except Exception as e:
            if missing_ok: return False
            raise e from e


    async def arm_file(self, missing_ok: bool = True):
        """
        Remove this file.
        If the path is a directory, use rmdir() instead.
        """
        try:
            await self._accessor.arm_file(self.fspath_)
            return True
        except Exception as e:
            if missing_ok: return False
            raise e from e


    # async def aunlink(self, missing_ok: bool = False):
    #     """
    #     Remove this file or link.
    #     If the path is a directory, use rmdir() instead.
    #     """
    #     try: await self._accessor.aunlink(self.fspath_, missing_ok = missing_ok)
    #     except FileNotFoundError:
    #         if not missing_ok: raise

    def rmdir(self, force: bool = False, recursive: bool = True, skip_errors: bool = True):
        """
        Remove this directory.  The directory must be empty.
        """
        try:
            return self._accessor.rmdir(self.fspath_)
        except Exception as e:
            if force: return self._accessor.rmdir(self.fspath_, recursive = recursive)
            if skip_errors: return
            raise e


    async def armdir(self, force: bool = False, recursive: bool = True, skip_errors: bool = True):
        """
        Remove this directory.  The directory must be empty.
        """
        try:
            return await self._accessor.armdir(self.fspath_)
        except Exception as e:
            if force: return await self._accessor.armdir(self.fspath_, recursive = recursive)
            if skip_errors: return
            raise e

    def link_to(self, target: str):
        """
        Create a hard link pointing to a path named target.
        """
        raise NotImplementedError

    async def alink_to(self, target: str):
        """
        Create a hard link pointing to a path named target.
        """
        raise NotImplementedError

    def rename(self, target: t.Union[str, CloudPathT]) -> CloudPathT:
        """
        Rename this path to the target path.
        The target path may be absolute or relative. Relative paths are
        interpreted relative to the current working directory, *not* the
        directory of the Path object.
        Returns the new Path instance pointing to the target path.
        """
        self._accessor.rename(self.fspath_, target)
        return type(self)(target)

    async def arename(self, target: t.Union[str, CloudPathT]) -> CloudPathT:
        """
        Rename this path to the target path.
        The target path may be absolute or relative. Relative paths are
        interpreted relative to the current working directory, *not* the
        directory of the Path object.
        Returns the new Path instance pointing to the target path.
        """
        await self._accessor.arename(self.fspath_, target)
        return type(self)(target)

    def replace(self, target: str) -> CloudPathT:
        """
        Rename this path to the target path, overwriting if that path exists.
        The target path may be absolute or relative. Relative paths are
        interpreted relative to the current working directory, *not* the
        directory of the Path object.
        Returns the new Path instance pointing to the target path.
        """
        self._accessor.replace(self.fspath_, target)
        return type(self)(target)

    async def areplace(self, target: str) -> CloudPathT:
        """
        Rename this path to the target path, overwriting if that path exists.
        The target path may be absolute or relative. Relative paths are
        interpreted relative to the current working directory, *not* the
        directory of the Path object.
        Returns the new Path instance pointing to the target path.
        """
        await self._accessor.areplace(self.fspath_, target)
        return type(self)(target)

    def symlink_to(self, target: str, target_is_directory: bool = False):
        """
        Make this path a symlink pointing to the given path.
        Note the order of arguments (self, target) is the reverse of os.symlink's.
        """
        raise NotImplementedError

    async def asymlink_to(self, target: str, target_is_directory: bool = False):
        """
        Make this path a symlink pointing to the given path.
        Note the order of arguments (self, target) is the reverse of os.symlink's.
        """
        raise NotImplementedError

    def exists(self) -> bool:
        """
        Whether this path exists.
        """
        return self._accessor.exists(self.fspath_)


    async def aexists(self) -> bool:
        """
        Whether this path exists.
        """
        return await self._accessor.aexists(self.fspath_)

    if t.TYPE_CHECKING:
        def _make_child_relpath(self, part: t.Any) -> CloudPathT:
            ...

    @classmethod
    def cwd(cls: type) -> str:
        """Return a new path pointing to the current working directory
        (as returned by os.getcwd()).
        """
        cwd: str = os.getcwd()
        return cls(cwd)

    @classmethod
    def home(cls: type) -> CloudPathT:
        """Return a new path pointing to the user's home directory (as
        returned by os.path.expanduser('~')).
        """
        homedir: str = cls()._flavour.gethomedir(None)
        return cls(homedir)

    @classmethod
    async def ahome(cls: type) -> CloudPathT:
        """Return a new path pointing to the user's home directory (as
        returned by os.path.expanduser('~')).
        """
        coro = cls()._flavour.agethomedir(None)
        homedir: str = await coro
        return cls(homedir)

    def samefile(self, other_path: t.Union[CloudPathT, Paths]) -> bool:
        """Return whether other_path is the same or not as this file
        (as returned by os.path.samefile()).
        """
        if isinstance(other_path, Paths.__args__): other_path = CloudPathT(other_path)
        if isinstance(other_path, CloudPathT):
            try: other_st = other_path.stat()
            except AttributeError: other_st = self._accessor.stat(other_path)

        else:
            try: other_st = other_path.stat()
            except AttributeError: other_st = other_path._accessor.stat(other_path)
        return os.path.samestat(self.stat(), other_st)

    async def asamefile(self, other_path: t.Union[CloudPathT, Paths]) -> bool:
        """Return whether other_path is the same or not as this file
        (as returned by os.path.samefile()).
        """
        if isinstance(other_path, Paths.__args__): other_path = CloudPathT(other_path)
        if isinstance(other_path, CloudPathT):
            try: other_st = await other_path.astat()
            except AttributeError: other_st = await self._accessor.astat(other_path)

        else:
            try: other_st = await to_thread(other_path.stat)
            except AttributeError: other_st = await to_thread(other_path._accessor.stat, other_path)

        return os.path.samestat(await self.astat(),other_st)

    def listdir(self) -> t.List[CloudPathT]:
        """Return a list of the entries in the directory (as returned by
        os.listdir()).
        """
        # return self._accessor.listdir(self.fspath_)
        return [self._make_child_relpath(name) for name in self._accessor.listdir(self.fspath_)]

    async def alistdir(self) -> t.List[CloudPathT]:
        """Return a list of the entries in the directory (as returned by
        os.listdir()).
        """
        return [self._make_child_relpath(name) for name in await self._accessor.alistdir(self.fspath_)]
        # return [self._make_child_relpath(name) for name in await self._accessor.alistdir(self.fsuri_)]


    def iterdir(self) -> t.Iterable[CloudPathT]:
        """Iterate over the files in this directory.  Does not yield any
        result for the special paths '.' and '..'.
        """
        for name in self._accessor.listdir(self.fspath_):
            if name in {'.', '..'}: continue
            yield self._make_child_relpath(name)

    async def aiterdir(self) -> t.AsyncIterable[CloudPathT]:
        """Iterate over the files in this directory.  Does not yield any
        result for the special paths '.' and '..'.
        """
        # for name in await self._accessor.alistdir(self):
        async for name in self._accessor.alistdir(self.fspath_):
            if name in {'.', '..'}: continue
            yield self._make_child_relpath(name)
    

    def walk(self) -> t.Iterable[t.Tuple[CloudPathT, t.List[CloudPathT], t.List[CloudPathT]]]:
        """Iterate over this subtree and yield a 3-tuple (dirpath, dirnames,
        filenames) for each directory in the subtree rooted at path
        (including path itself, if it is a directory).
        """
        top = self._make_child_relpath('.')
        dirs, nondirs = [], []
        for name in self._accessor.listdir(self.fspath_):
            if name in {'.', '..'}: continue
            (dirs if self._accessor.is_dir(self._make_child_relpath(name)) else nondirs).append(self._make_child_relpath(name))
        yield top, dirs, nondirs
        for name in dirs:
            new_path: CloudPathT = self._make_child_relpath(name)
            yield from new_path.walk()
        
    async def awalk(self) -> t.AsyncIterable[t.Tuple[CloudPathT, t.List[CloudPathT], t.List[CloudPathT]]]:
        """Iterate over this subtree and yield a 3-tuple (dirpath, dirnames,
        filenames) for each directory in the subtree rooted at path
        (including path itself, if it is a directory).
        """
        top = self._make_child_relpath('.')
        dirs, nondirs = [], []
        for name in await self._accessor.alistdir(self.fspath_):
            if name in {'.', '..'}: continue
            (dirs if await self._accessor.ais_dir(self._make_child_relpath(name)) else nondirs).append(self._make_child_relpath(name))
        yield top, dirs, nondirs
        for name in dirs:
            new_path: CloudPathT = self._make_child_relpath(name)
            async for path in new_path.awalk():
                yield path

    def glob(self, pattern: str = '*', as_path: bool = True) -> t.Iterable[t.Union[str, CloudPathT]]:
        """Iterate over this subtree and yield all existing files (of any
        kind, including directories) matching the given relative pattern.
        Warning: doesn't work as expected. Use Find Instead.
        """
        if not pattern: raise ValueError("Unacceptable pattern: {!r}".format(pattern))
        #if self.is_fsspec:
        glob_pattern = self.fspath_ + ('/' if self.is_dir() and not self.fspath_.endswith('/') and not pattern.startswith('/') else '') +  pattern
        try:
            matches =  self._accessor.glob(glob_pattern)
            if not matches: return matches
            if self.is_fsspec: matches = [f'{self._prefix}://{m}' for m in matches]
            if as_path: matches = [type(self)(m) for m in matches]
            return matches
        except Exception as e:
            logger.error(e)
            return self.find(pattern = pattern, as_string = not as_path)

    async def aglob(self, pattern: str = '*', as_path: bool = True) -> t.AsyncIterable[CloudPathT]:
        """Iterate over this subtree and yield all existing files (of any
        kind, including directories) matching the given relative pattern.
        """
        if not pattern: raise ValueError("Unacceptable pattern: {!r}".format(pattern))
        glob_pattern = self.fspath_ + ('/' if self.is_dir() and not self.fspath_.endswith('/') and not pattern.startswith('/') else '') +  pattern
        try:
            matches = await self._accessor.aglob(glob_pattern)
            if not matches: return matches
            if self.is_fsspec: matches = [f'{self._prefix}://{m}' for m in matches]
            if as_path: matches = [type(self)(m) for m in matches]
            return matches
        except Exception as e:
            logger.error(e)
            return await self.afind(pattern = pattern, as_string = not as_path)

    def find(self, pattern: str = "*",  as_string: bool = False, maxdepth: int = None, withdirs: bool = None, detail: bool = False) -> t.Union[t.List[str], t.List[CloudPathT]]:
        """
        List all files below path. Like posix find command without conditions
        """
        matches = self._accessor.find(path = self.fsuri_, maxdepth = maxdepth, withdirs = withdirs, detail = detail, prefix = pattern)
        if self.is_fsspec:
            matches = [f'{self._prefix}://{m}' for m in matches]
        if not as_string:
            matches = [type(self)(m) for m in matches]
        return matches

    async def afind(self, pattern: str = "*",  as_string: bool = False, maxdepth: int = None, withdirs: bool = None, detail: bool = False) -> t.Union[t.List[str], t.List[CloudPathT]]:
        """
        List all files below path. Like posix find command without conditions
        """
        matches = await self._accessor.afind(path = self.fsuri_, maxdepth = maxdepth, withdirs = withdirs, detail = detail, prefix = pattern)
        if self.is_fsspec:
            matches = [f'{self._prefix}://{m}' for m in matches]
        if not as_string:
            matches = [type(self)(m) for m in matches]
        return matches

    def rglob(self, pattern: str, as_path: bool = True) -> t.Iterable[t.Union[str, CloudPathT]]:
        """Recursively yield all existing files (of any kind, including
        directories) matching the given relative pattern, anywhere in
        this subtree.
        """
        return self.glob(pattern = f'**/{pattern}', as_path = as_path)

    async def arglob(self, pattern: str) -> t.AsyncIterable[t.Union[str, CloudPathT]]:
        """Recursively yield all existing files (of any kind, including
        directories) matching the given relative pattern, anywhere in
        this subtree.
        """
        return await self.aglob(f'**/{pattern}')

    def cat(self, recursive: bool = False, on_error: str = 'raise', **kwargs):
        """
        Fetch paths’ contents
        Parameters
        recursive: bool
            If True, assume the path(s) are directories, and get all the contained files

        on_error“raise”, “omit”, “return”
            If raise, an underlying exception will be raised (converted to KeyError if the type is in self.missing_exceptions);
            if omit, keys with exception will simply not be included in the output; if “return”, all keys are included in the output,
            but the value will be bytes or an exception instance.

        kwargs: passed to cat_file
        """
        return self._accessor.cat(self.fsuri_, recursive = recursive, on_error = on_error, **kwargs)

    async def acat(self, recursive: bool = False, on_error: str = 'raise', **kwargs):
        """
        Fetch paths’ contents
        Parameters
        recursive: bool
            If True, assume the path(s) are directories, and get all the contained files

        on_error“raise”, “omit”, “return”
            If raise, an underlying exception will be raised (converted to KeyError if the type is in self.missing_exceptions);
            if omit, keys with exception will simply not be included in the output; if “return”, all keys are included in the output,
            but the value will be bytes or an exception instance.

        kwargs: passed to cat_file
        """
        return await self._accessor.acat(self.fsuri_, recursive = recursive, on_error = on_error, **kwargs)

    def cat_file(self, as_bytes: bool = False, start: int = None, end: int = None, **kwargs):
        """
        Parameters
        start, end: int
            Bytes limits of the read. If negative, backwards from end, like usual python slices. Either can be None for start or end of file, respectively

        kwargs: passed to ``open()``.
        """
        res = self._accessor.cat_file(self.fsuri_, start = start, end = end, **kwargs)
        if not as_bytes and isinstance(res, bytes): res = res.decode('UTF-8')
        return res

    async def acat_file(self, as_bytes: bool = False, start: int = None, end: int = None, **kwargs):
        """
        Parameters
        start, end: int
            Bytes limits of the read. If negative, backwards from end, like usual python slices. Either can be None for start or end of file, respectively

        kwargs: passed to ``open()``.
        """
        res = await self._accessor.acat_file(self.fsuri_, start = start, end = end, **kwargs)
        if not as_bytes and isinstance(res, bytes): res = res.decode('UTF-8')
        return res

    def pipe(self, value: t.Union[bytes, str], **kwargs):
        """
        Put value into path

        (counterpart to cat)
        """
        if not isinstance(value, bytes): value = value.encode('UTF-8')
        return self._accessor.pipe(self.fsuri_, value = value, **kwargs)

    async def apipe(self, value: t.Union[bytes, str], **kwargs):
        """
        Put value into path

        (counterpart to cat)
        """
        if not isinstance(value, bytes): value = value.encode('UTF-8')
        return await self._accessor.apipe(self.fsuri_, value = value, **kwargs)

    def pipe_file(self, value: t.Union[bytes, str], **kwargs):
        """
        Put value into path

        (counterpart to cat)
        """
        if not isinstance(value, bytes): value = value.encode('UTF-8')
        return self._accessor.pipe_file(self.fsuri_, value = value, **kwargs)

    async def apipe_file(self, value: t.Union[bytes, str], **kwargs):
        """
        Put value into path

        (counterpart to cat)
        """
        if not isinstance(value, bytes): value = value.encode('UTF-8')
        return await self._accessor.apipe_file(self.fsuri_, value = value, **kwargs)


    def absolute(self) -> CloudPathT:
        """Return an absolute version of this path.  This function works
        even if the path doesn't point to anything.
        No normalization is done, i.e. all '.' and '..' will be kept along.
        Use resolve() to get the canonical path to a file.
        """
        raise NotImplementedError


    def resolve(self, strict: bool = False) -> CloudPathT:
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

    async def aresolve(self, strict: bool = False) -> CloudPathT:
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
        return self._accessor.stat(self.fspath_)

    async def astat(self) -> os.stat_result:
        """
        Return the result of the stat() system call on this path, like
        os.stat() does.
        """
        return await self._accessor.astat(self.fspath_)

    def info(self) -> t.Dict[str, t.Union[str, int, float, datetime.datetime, datetime.timedelta, t.List[str], t.Any]]:
        """
        Return the result of the info() system call on this path, like

        >>> {'ETag': '"etag"', 'LastModified': datetime.datetime(2025, 8, 14, 21, 10, 28, tzinfo=tzutc()), 'size': 78, 'name': 'path/in/bucket/key', 'type': 'file', 'StorageClass': 'STANDARD', 'VersionId': None, 'ContentType': 'binary/octet-stream'}        
        """
        return self._accessor.info(self.fspath_)

    async def ainfo(self) -> t.Dict[str, t.Union[str, int, float, datetime.datetime, datetime.timedelta, t.List[str], t.Any]]:
        """
        Return the result of the info() system call on this path, like
        os.stat() does.

        >>> {'ETag': '"etag"', 'LastModified': datetime.datetime(2025, 8, 14, 21, 10, 28, tzinfo=tzutc()), 'size': 78, 'name': 'path/in/bucket/key', 'type': 'file', 'StorageClass': 'STANDARD', 'VersionId': None, 'ContentType': 'binary/octet-stream'}
        """
        return await self._accessor.ainfo(self.fspath_)

    def metadata(self, refresh: t.Optional[bool] = False, **kwargs) -> t.Dict[str, t.Union[str, int, float, datetime.datetime, datetime.timedelta, t.List[str], t.Any]]:
        """
        Returns the metadata for the file
        """
        return self._accessor.metadata(self.fspath_, refresh = refresh, **kwargs)

    async def ametadata(self, refresh: t.Optional[bool] = False, **kwargs) -> t.Dict[str, t.Union[str, int, float, datetime.datetime, datetime.timedelta, t.List[str], t.Any]]:
        """
        Returns the metadata for the file
        """
        return await self._accessor.ametadata(self.fspath_, refresh = refresh, **kwargs)

    def size(self) -> int:
        """
        Return the size of the file, reported by os.path.getsize.
        """
        return self._accessor.size(self.fspath_)

    async def asize(self) -> int:
        """
        Return the size of the file, reported by os.path.getsize.
        """
        return await self._accessor.asize(self.fspath_)

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
        raise NotImplementedError

    async def alstat(self) -> os.stat_result:
        """
        Like stat(), except if the path points to a symlink, the symlink's
        status information is returned, rather than its target's.
        """
        raise NotImplementedError

    def owner(self) -> str:
        """
        Return the login name of the file owner.
        """
        raise NotImplementedError

    async def aowner(self) -> str:
        """
        Return the login name of the file owner.
        """
        raise NotImplementedError

    def group(self) -> str:
        """
        Return the group name of the file gid.
        """
        raise NotImplementedError

    async def agroup(self) -> str:
        """
        Return the group name of the file gid.
        """
        raise NotImplementedError

    def is_dir(self) -> bool:
        """
        Whether this path is a directory.
        """
        return self._accessor.is_dir(self.fspath_)


    async def ais_dir(self) -> bool:
        """
        Whether this path is a directory.
        """
        return await self._accessor.ais_dir(self.fspath_)

    def is_symlink(self) -> bool:
        """
        Whether this path is a symbolic link.
        """
        raise NotImplementedError


    async def ais_symlink(self) -> bool:
        """
        Whether this path is a symbolic link.
        """
        raise NotImplementedError

    def is_file(self) -> bool:
        """
        Whether this path is a regular file (also True for symlinks pointing
        to regular files).
        """
        return self._accessor.is_file(self.fspath_)

    async def ais_file(self) -> bool:
        """
        Whether this path is a regular file (also True for symlinks pointing
        to regular files).
        """
        return await self._accessor.ais_file(self.fspath_)

    @staticmethod
    def get_pathlike_(path: 'PathLike') -> 'FileLike':
        """
        Returns the path of the file.
        """
        from lzl.io.file.spec.main import get_pathlike
        return get_pathlike(path)
    

    @classmethod
    def get_tempdir_(cls):
        """
        Returns the temporary directory for the current user.
        """
        import tempfile
        return cls.get_pathlike_(tempfile.gettempdir())

    def copy(self, dest: 'PathLike', recursive: bool = False, overwrite: bool = False, skip_errors: bool = False):
        """
        Copies the File to the Dir/File.
        """
        dest = self.get_pathlike_(dest)
        if dest.is_dir() and self.is_file():
            dest = dest.joinpath(self.filename_)
        if dest.exists() and not overwrite and dest.is_file():
            if skip_errors: return dest
            raise FileExistsError(f'File {dest.path_} exists')
        if dest.is_fsspec: self._accessor.copy(self.fspath_, dest.fspath_, recursive)
        else: self._accessor.get(self.fspath_, dest.string, recursive)
        return dest

    async def acopy(self, dest: 'PathLike', recursive: bool = False, overwrite: bool = False, skip_errors: bool = False):
        """
        Copies the File to the Dir/File.
        """
        dest = self.get_pathlike_(dest)
        if await dest.ais_dir() and await self.ais_file():
            dest = dest.joinpath(self.filename_)
        if await dest.aexists() and not overwrite and await dest.ais_file():
            if skip_errors: return dest
            raise FileExistsError(f'File {dest.path_} exists')
        if dest.is_fsspec: await self._accessor.acopy(self.fspath_, dest.fspath_, recursive = recursive)
        else: await self._accessor.aget(self.fspath_, dest.string, recursive = recursive)
        return dest

    def copy_file(self, dest: 'PathLike', recursive: bool = False, overwrite: bool = False, skip_errors: bool = False):
        """
        Copies this File to the the Dest Path
        """
        dest = self.get_pathlike_(dest)
        if dest.is_dir() and self.is_file():
            dest = dest.joinpath(self.filename_)
        if dest.exists() and not overwrite and dest.is_file():
            if skip_errors: return dest
            raise FileExistsError(f'File {dest.path_} exists')
        if dest.is_fsspec: self._accessor.copy(self.fspath_, dest.fspath_, recursive)
        else: self._accessor.get(self.fspath_, dest.path_, recursive)
        return dest

    async def acopy_file(self, dest: 'PathLike', recursive: bool = False, overwrite: bool = False, skip_errors: bool = False):
        """
        Copies this File to the the Dest Path
        """
        dest = self.get_pathlike_(dest)
        if await dest.ais_dir() and await self.ais_file():
            dest = dest.joinpath(self.filename_)
        if await dest.aexists() and not overwrite and await dest.ais_file():
            if skip_errors: return dest
            raise FileExistsError(f'File {dest.path_} exists')
        if dest.is_fsspec: await self._accessor.acopy(self.fspath_, dest.fspath_, recursive = recursive)
        else: await self._accessor.aget(self.fspath_, dest.string, recursive = recursive)
        return dest
    

    def localize(self, filename: t.Optional[str] = None, output_dir: t.Optional[Paths] = None, unique: t.Optional[bool] = False, cleanup_on_exit: t.Optional[bool] = False, **kwargs) -> 'FileLike':
        """
        Localize the file

        Otherwise, it will copy the file to the specified output directory or temporary directory.
        """
        if not self.is_fsspec: return self
        if output_dir is None: output_dir = self.get_tempdir_()
        else: output_dir = self.get_pathlike_(output_dir)
        if not filename:
            if unique:
                from lzo.utils import create_unique_id
                filename = f'{create_unique_id()}{self.suffix}'
            else:
                filename = self.name
        dest = output_dir.joinpath(filename)
        if dest.is_fsspec: self._accessor.copy(self.fspath_, dest.fspath_)
        else: self._accessor.get(self.fspath_, dest.path_)
        if cleanup_on_exit:
            from lzl.io.registry import add_file_to_cleanup
            add_file_to_cleanup(dest)
        return dest
    

    async def alocalize(self, filename: t.Optional[str] = None, output_dir: t.Optional[Paths] = None, unique: t.Optional[bool] = False, cleanup_on_exit: t.Optional[bool] = False, **kwargs) -> 'FileLike':
        """
        Localize the file - If this is already a local file (not cloud - it doesn't do anything)

        Otherwise, it will copy the file to the specified output directory or temporary directory.
        """
        if not self.is_fsspec: return self
        if output_dir is None: output_dir = self.get_tempdir_()
        else: output_dir = self.get_pathlike_(output_dir)
        if not filename:
            if unique:
                from lzo.utils import create_unique_id
                filename = f'{create_unique_id()}{self.suffix}'
            else: filename = self.name
        dest = output_dir.joinpath(filename)
        if dest.is_fsspec: await self._accessor.acopy(self.fspath_, dest.fspath_)
        else: await self._accessor.aget(self.fspath_, dest.string)
        if cleanup_on_exit:
            from lzl.io.registry import add_file_to_cleanup
            add_file_to_cleanup(dest)
        return dest
    

    def bytesio(self, **kwargs) -> io.BytesIO:
        """
        Convert the file to a BytesIO object.
        """
        bytes_obj = io.BytesIO()
        bytes_obj.write(self.read_bytes())
        bytes_obj.seek(0)
        return bytes_obj
    
    async def abytesio(self, **kwargs) -> io.BytesIO:
        """
        Convert the file to a BytesIO object.
        """
        bytes_obj = io.BytesIO()
        bytes_obj.write(await self.aread_bytes())
        bytes_obj.seek(0)
        return bytes_obj

    def textio(self, **kwargs) -> io.StringIO:
        """
        Convert the file to a StringIO object.
        """
        string_obj = io.StringIO()
        string_obj.write(self.read_text())
        string_obj.seek(0)
        return string_obj

    async def atextio(self, **kwargs) -> io.StringIO:
        """
        Convert the file to a StringIO object.
        """
        string_obj = io.StringIO()
        string_obj.write(await self.aread_text())
        string_obj.seek(0)
        return string_obj
    

    """
    Serialization Helper for file-like objects.
    """
    def yaml(self, **kwargs) -> t.Union[t.Dict[str, t.Any], t.List[t.Any]]:
        """
        Parses the file contents as yaml
        """
        import yaml
        return yaml.safe_load(self.read_text( **kwargs))
    
    async def ayaml(self, **kwargs) -> t.Union[t.Dict[str, t.Any], t.List[t.Any]]:
        """
        Parses the file contents as yaml
        """
        import yaml
        return yaml.safe_load(await self.aread_text( **kwargs))

    def json(self, **kwargs) -> t.Union[t.Dict[str, t.Any], t.List[t.Any]]:
        """
        Parses the file contents as json
        """
        from lzl.io.registry import json_ser
        try:
            return json_ser.loads(self.read_text( **kwargs))
        except Exception as e:
            from lzl.logging import logger
            logger.trace(f"Failed to parse JSON from {self.path_}", e)
            import json
            return json.loads(self.read_text( **kwargs))
        
    
    async def ajson(self, **kwargs) -> t.Union[t.Dict[str, t.Any], t.List[t.Any]]:
        """
        Parses the file contents as json
        """
        from lzl.io.registry import json_ser
        try:
            return await json_ser.aloads(await self.aread_text( **kwargs))
        except Exception as e:
            from lzl.logging import logger
            logger.trace(f"Failed to parse JSON from {self.path_}", e)
            import json
            return json.loads(await self.aread_text( **kwargs))

    @classmethod
    def register_loader(cls, ext: str, loader: t.Union[t.Callable[['FileLike'], None], t.Awaitable['FileLike', None]], overwrite: t.Optional[bool] = None) -> None:
        """
        Registers a file loader for a specific file extension.
        """
        from lzl.io.file.registry import register_loader
        register_loader(ext, loader, overwrite)

    def loads(self, *args, **kwargs) -> t.Any:
        """
        Automatically Load this File using the registered loaders based on the extension.

        If no loader is found, an error is raised.

        Use `File.register_loader` to register a new loader.
        """
        from lzl.io.file.registry import get_file_loader
        loader_func = get_file_loader(self.suffix)
        if ThreadPool.is_coro(loader_func):
            return ThreadPool.run_sync(loader_func, self, *args, **kwargs)
        return loader_func(self, *args, **kwargs)
    
    async def aloads(self, *args, **kwargs) -> t.Any:
        """
        Automatically Load this File using the registered loaders based on the extension.

        If no loader is found, an error is raised.

        Use `File.register_loader` to register a new loader.
        """
        from lzl.io.file.registry import get_file_loader
        loader_func = get_file_loader(self.suffix)
        if ThreadPool.is_coro(loader_func):
            return await loader_func(self, *args, **kwargs)
        return ThreadPool.arun(loader_func, self, *args, **kwargs)

    """
    End Serialization Helpers
    """

    def _download_with_tmgr(
        self, 
        dest: 'FileLike',
        callbacks: t.Optional[t.Dict[str, t.Callable]] = None,
        **kwargs
    ) -> 'FileLike':
        """
        Downloads the current file to the dest
        """
        future = self.fss3tm.download(
            self.bucket_,
            self.get_path_key(self.name),
            dest.as_posix(),
            subscribers = callbacks,
            **kwargs,
        )
        future.result()

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
        if self._has_tmgr:
            return self._download_with_tmgr(dest, callbacks, **kwargs)
        return self.copy_file(dest, overwrite = overwrite, **kwargs)
    
    async def _adownload_with_tmgr(
        self, 
        dest: 'FileLike',
        callbacks: t.Optional[t.Dict[str, t.Callable]] = None,
        **kwargs
    ) -> 'FileLike':
        """
        Downloads the current file to the dest
        """
        future = self.fss3tm.download(
            self.bucket_,
            self.get_path_key(self.name),
            dest.as_posix(),
            subscribers = callbacks,
            **kwargs,
        )
        await ThreadPool.run_async(future.result)
        return dest

    async def adownload(
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
        if await new.aexists() and not overwrite:
            raise FileExistsError(f'File {new.path_} exists and overwrite is False')
        if self._has_tmgr:
            return await self._adownload_with_tmgr(dest, callbacks, **kwargs)
        return await self.acopy_file(dest, overwrite = overwrite, **kwargs)

    async def _aupload_with_tmgr(
        self, 
        src: 'FileLike',
        callbacks: t.Optional[t.Dict[str, t.Callable]] = None,
        **kwargs
    ) -> 'FileLike':
        """
        Uploads the src to the current path
        """
        future = self.fss3tm.upload(
            src.as_posix(),
            self.bucket_,
            self.get_path_key(self.name),
            subscribers = callbacks,
            **kwargs,
        )
        await ThreadPool.run_async(future.result)
        await self.ainvalidate_cache()
        return src

    async def aupload(
        self, 
        src: 'PathLike',
        filename: t.Optional[str] = None, 
        overwrite: t.Optional[bool] = None,
        callbacks: t.Optional[t.Dict[str, t.Callable]] = None,
        **kwargs
    ) -> 'FileLike':
        """
        Uploads the src to the current path
        """
        src = self.get_pathlike_(src)
        new = self.joinpath(filename or src.name) if self.is_dir() else self
        if await new.aexists() and not overwrite:
            raise FileExistsError(f'File {new.path_} exists and overwrite is False')
        if not await src.aexists():
            raise FileNotFoundError(f'File {src.path_} does not exist')
        if self._has_tmgr:
            return await self._aupload_with_tmgr(src, callbacks, **kwargs)
        return await self.acopy_file(src, overwrite = overwrite, **kwargs)

    def _upload_with_tmgr(
        self, 
        src: 'FileLike',
        callbacks: t.Optional[t.Dict[str, t.Callable]] = None,
        **kwargs
    ) -> 'FileLike':
        """
        Uploads the src to the current path
        """
        future = self.fss3tm.upload(
            src.as_posix(),
            self.bucket_,
            self.get_path_key(self.name),
            subscribers = callbacks,
            **kwargs,
        )
        future.result()
        self.invalidate_cache()
        return src

    def upload(
        self, 
        src: 'PathLike',
        filename: t.Optional[str] = None, 
        overwrite: t.Optional[bool] = None,
        callbacks: t.Optional[t.Dict[str, t.Callable]] = None,
        **kwargs
    ) -> 'FileLike':
        """
        Uploads the src to the current path
        """
        src = self.get_pathlike_(src)
        new = self.joinpath(filename or src.name) if self.is_dir() else self
        if new.exists() and not overwrite:
            raise FileExistsError(f'File {new.path_} exists and overwrite is False')
        if not src.exists():
            raise FileNotFoundError(f'File {src.path_} does not exist')
        if self._has_tmgr:
            return self._upload_with_tmgr(src, callbacks, **kwargs)
        return self.copy_file(src, overwrite = overwrite, **kwargs)
        

    def put(self, src: 'PathLike', recursive: bool = False, callback: t.Optional[t.Callable] = Callback(), **kwargs):
        """
        Copy file(s) from src to this FilePath
        WIP support for cloud-to-cloud
        """
        src = self.get_pathlike_(src)
        assert not src.is_fsspec, 'Cloud to Cloud support not supported at this time'
        return self._accessor.put(src.string, self.fspath_, recursive=recursive, callback=callback, **kwargs)

    async def aput(self, src: 'PathLike', recursive: bool = False, callback: t.Optional[t.Callable] = Callback(), **kwargs):
        """
        Copy file(s) from src to this FilePath
        WIP support for cloud-to-cloud
        """
        src = self.get_pathlike_(src)
        assert not src.is_fsspec, 'Cloud to Cloud support not supported at this time'
        return await self._accessor.aput(src.string, self.fspath_, recursive=recursive, callback=callback, **kwargs)

    def put_file(self, src: 'PathLike', callback: t.Optional[t.Callable] = Callback(), **kwargs):
        """
        Copy single file to remote
        WIP support for cloud-to-cloud
        """
        src = self.get_pathlike_(src)
        assert not src.is_fsspec, 'Cloud to Cloud support not supported at this time'
        return self._accessor.put_file(src.string, self.fspath_, callback=callback, **kwargs)

    async def aput_file(self, src: 'PathLike', callback: t.Optional[t.Callable] = Callback(), **kwargs):
        """
        Copy single file to remote
        WIP support for cloud-to-cloud
        """
        src = self.get_pathlike_(src)
        assert not src.is_fsspec, 'Cloud to Cloud support not supported at this time'
        return await self._accessor.aput_file(src.string, self.fspath_, callback=callback, **kwargs)

    def get(self, dest: 'PathLike', recursive: bool = False, callback: t.Optional[t.Callable] = Callback(), **kwargs):
        """
        Copy the remote file(s) to dest (local)
        WIP support for cloud-to-cloud
        """
        dest = self.get_pathlike_(dest)
        assert not dest.is_fsspec, 'Cloud to Cloud support not supported at this time'
        return self._accessor.get(self.fspath_, dest.string, recursive=recursive, callback=callback, **kwargs)

    async def aget(self, dest: 'PathLike', recursive: bool = False, callback: t.Optional[t.Callable] = Callback(), **kwargs):
        """
        Copy the remote file(s) to dest (local)
        WIP support for cloud-to-cloud
        """
        dest = self.get_pathlike_(dest)
        assert not dest.is_fsspec, 'Cloud to Cloud support not supported at this time'
        return await self._accessor.aget(self.fspath_, dest.string, recursive=recursive, callback=callback, **kwargs)

    def get_file(self, dest: 'PathLike', callback: t.Optional[t.Callable] = Callback(), **kwargs):
        """
        Copies this file to dest (local)
        WIP support for cloud-to-cloud
        """
        dest = self.get_pathlike_(dest)
        assert not dest.is_fsspec, 'Cloud to Cloud support not supported at this time'
        return self._accessor.get_file(self.fspath_, dest.string, callback=callback, **kwargs)

    async def aget_file(self, dest: 'PathLike', callback: t.Optional[t.Callable] = Callback(), **kwargs):
        """
        Copies this file to dest (local)
        WIP support for cloud-to-cloud
        """
        dest = self.get_pathlike_(dest)
        assert not dest.is_fsspec, 'Cloud to Cloud support not supported at this time'
        return await self._accessor.aget_file(self.fspath_, dest.string, callback=callback, **kwargs)


    def is_mount(self) -> bool:
        """
        Check if this path is a POSIX mount point
        """
        # Need to exist and be a dir
        return False if not self.exists() or not self.is_dir() else False
        #raise NotImplementedError


    async def ais_mount(self) -> bool:
        """
        Check if this path is a POSIX mount point
        """
        # Need to exist and be a dir
        return False if not await self.aexists() or not await self.ais_dir() else False
        #raise NotImplementedError


    def is_block_device(self) -> bool:
        """
        Whether this path is a block device.
        """
        return False
        #raise NotImplementedError

    async def ais_block_device(self) -> bool:
        """
        Whether this path is a block device.
        """
        return False
        #raise NotImplementedError

    def is_char_device(self) -> bool:
        """
        Whether this path is a character device.
        """
        return False
        #raise NotImplementedError


    async def ais_char_device(self) -> bool:
        """
        Whether this path is a character device.
        """
        return False

    def is_fifo(self) -> bool:
        """
        Whether this path is a FIFO.
        """
        return False


    async def ais_fifo(self) -> bool:
        """
        Whether this path is a FIFO.
        """
        return False


    def is_socket(self) -> bool:
        """
        Whether this path is a socket.
        """
        return False


    async def ais_socket(self) -> bool:
        """
        Whether this path is a socket.
        """
        return False


    def expanduser(self) -> CloudPathT:
        """ Return a new path with expanded ~ and ~user constructs
        (as returned by os.path.expanduser)
        """
        if (not self._drv and not self._root and self._parts and self._parts[0][:1] == '~'):
            homedir = self._flavour.gethomedir(self._parts[0][1:])
            return self._from_parts([homedir] + self._parts[1:])
        return self

    async def aexpanduser(self) -> CloudPathT:
        """ Return a new path with expanded ~ and ~user constructs
        (as returned by os.path.expanduser)
        """
        if (not self._drv and not self._root and self._parts and self._parts[0][:1] == '~'):
            homedir = await self._flavour.agethomedir(self._parts[0][1:])
            return self._from_parts([homedir] + self._parts[1:])
        return self

    def iterdir(self) -> t.Iterable[CloudPathT]:
        names = self._accessor.listdir(self)
        for name in names:
            if name in {'.', '..'}: continue
        yield self._make_child_relpath(name)

    async def aiterdir(self) -> t.AsyncIterable[CloudPathT]:
        names = await self._accessor.alistdir(self)
        for name in names:
            if name in {'.', '..'}: continue
        yield self._make_child_relpath(name)

    async def als(
        self,
        recursive: bool = False,
        detail: t.Optional[bool] = False,
        versions: t.Optional[bool] = False,
        refresh: t.Optional[bool] = False,
        as_path: t.Optional[bool] = True,
        files_only: t.Optional[bool] = True,
        prettify: t.Optional[bool] = True,
        **kwargs,
    ) -> t.Union[t.List[CloudPathT], t.List[t.Dict[str, t.Any]]]:
        """
        Return a list of the files in this directory.
        """
        
        ls_partial = functools.partial(self.afilesys._ls, detail=True, versions=versions, refresh=refresh)

        async def _ls(path: t.Dict[str, t.Any]):
            """
            Inner function to handle recursive ls
            """
            ps = []
            if path.get('type', path.get('StorageClass', '')).lower() == 'directory' \
                and recursive:
                new_paths = await ls_partial(path['Key'])
                results = await asyncio.gather(*[_ls(p) for p in new_paths])
                for result in results:
                    ps.extend(result)
                if not files_only: ps.append(path)
            if files_only and path.get('type', path.get('StorageClass', '')).lower() != 'directory':
                ps.append(path)
            return ps

        from pydantic.types import ByteSize
        from lzl.pool import ThreadPool
        # from lzl.pool import async_map
        # from fileio.utils.pooler import async_map
        paths: t.List[t.Dict[str, t.Any]] = await ls_partial(self.fspath_)
        all_paths = []
        async for path in ThreadPool.aiterate(_ls, paths):
            all_paths.extend(path)

        if detail: 
            for p in all_paths:
                p['Key'] = f'{self._prefix}://{p["Key"]}'
                if prettify: p['SizePretty'] = ByteSize(p['Size']).human_readable()
            if as_path:
                p['File'] = type(self)(p['Key'])
            return all_paths
        final_paths = []
        for path in all_paths:
            if as_path: 
                path_str = f'{self._prefix}://{path["Key"]}'
                path = type(self)(path_str)
            final_paths.append(path)
        return final_paths
        

    def _raise_closed(self):
        raise ValueError("I/O operation on closed path")

    def _raise_open(self):
        raise ValueError("I/O operation on already open path")

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

    """
    Other Methods
    """
    @t.overload
    def url(self, expires: int = 3600, client_method: str = 'get_object', **kwargs) -> str:
        """
        Returns a presigned URL for this file object
        """
        ...
        
    def url(self, **kwargs):
        return self._accessor.url(self.fspath_, **kwargs)

    @t.overload
    async def aurl(self, expires: int = 3600, client_method: str = 'get_object', **kwargs) -> str:
        """
        Returns a presigned URL for this file object
        """
        ...

    async def aurl(self, **kwargs):
        return await self._accessor.aurl(self.fspath_, **kwargs)

    @t.overload
    def setxattr(self, copy_kwargs: t.Optional[t.Dict[str, t.Any]] = None, **kwargs) -> None:
        """
        Set the extended attributes for this file

        Set metadata.

        Attributes have to be of the form documented in the
        `Metadata Reference`_.

        Parameters
        ----------
        kwargs : key-value pairs like field="value", where the values must be
            strings. Does not alter existing fields, unless
            the field appears here - if the value is None, delete the
            field.
        copy_kwargs : dict, optional
            dictionary of additional params to use for the underlying
            s3.copy_object.

        Examples
        --------
        >>> mys3file.setxattr(attribute_1='value1', attribute_2='value2')  # doctest: +SKIP
        # Example for use with copy_args
        >>> mys3file.setxattr(copy_kwargs={'ContentType': 'application/pdf'},
        ...     attribute_1='value1')  # doctest: +SKIP

        """
        ...

    def setxattr(self, **kwargs):
        return self._accessor.setxattr(self.fspath_, **kwargs)

    @t.overload
    async def asetxattr(self, copy_kwargs: t.Optional[t.Dict[str, t.Any]] = None, **kwargs) -> None:
        """
        Set the extended attributes for this file

        Set metadata.

        Attributes have to be of the form documented in the
        `Metadata Reference`_.

        Parameters
        ----------
        kwargs : key-value pairs like field="value", where the values must be
            strings. Does not alter existing fields, unless
            the field appears here - if the value is None, delete the
            field.
        copy_kwargs : dict, optional
            dictionary of additional params to use for the underlying
            s3.copy_object.

        Examples
        --------    
        >>> await mys3file.asetxattr(attribute_1='value1', attribute_2='value2')  # doctest: +SKIP
        # Example for use with copy_args
        >>> await mys3file.asetxattr(copy_kwargs={'ContentType': 'application/pdf'},
        ...     attribute_1='value1')  # doctest: +SKIP

        """
        ...

    async def asetxattr(self, **kwargs):
        try:
            return await self._accessor.asetxattr(self.fspath_, **kwargs)
        except RuntimeError as e:
            if 'Loop is not running' in str(e):
                return await ThreadPool.asyncish(self.setxattr, **kwargs)
            raise e

    # async def asetxattr(self, *args, **kwargs):
    #     return await ThreadPool.asyncish(self.setxattr, *args, **kwargs)
        # return await self._accessor.asetxattr(self.fspath_, *args, **kwargs)

    def invalidate_cache(self):
        return self._accessor.invalidate_cache(self.fspath_)
    
    async def ainvalidate_cache(self):
        return await self._accessor.ainvalidate_cache(self.fspath_)

    @property
    def transaction(self):
        """
        A context manager for a transaction.
        
        Filesystem transactions allow for bundling multiple write operations
        that are committed atomically (if supported by the backend) or 
        discarded on error.
        
        Usage:
            with file.transaction:
                file.write_text("data")
                other_file.write_text("more data")
        """
        if hasattr(self.filesys, 'transaction'):
            return self.filesys.transaction
        raise NotImplementedError(f"Transactions not supported for {self._provider}")

    @property
    def atransaction(self):
        """
        Async context manager for transactions.
        
        Usage:
            async with file.atransaction:
                await file.awrite_text("data")
        """
        if hasattr(self.filesys, 'transaction'):
            # Use the AsyncTransactionContext defined at module level (or we need to reference it correctly)
            # It was defined inside CloudFileSystemPath? No, I defined it at module level but indented it?
            # Wait, in previous step I indented it inside... where?
            # I indented it inside... `src/lzl/io/file/spec/path.py` before `CloudFileSystemPurePath`.
            # Wait, looking at `replace` output... I replaced `    _FST = ...`
            # `_FST` was likely at top level?
            # No, `_FST` was inside `if t.TYPE_CHECKING:` block?
            # Let's check line 97 of original file.
            # `if t.TYPE_CHECKING:` was around line 25.
            # `CloudFileSystemPurePath` starts around line 40?
            # Let's check the file content I read earlier.
            # `src/lzl/io/file/spec/path.py`:
            # Lines 1-50.
            # `if t.TYPE_CHECKING:` starts line 37.
            # `    from .providers.main import AccessorLike` ...
            # `    _FST = ...` is NOT in the TYPE_CHECKING block in standard python if it is a TypeVar?
            # TypeVars are usually top level.
            
            # If I indented `AsyncTransactionContext` inside `if t.TYPE_CHECKING:`, then it is NOT available at runtime!
            # I need to check where I inserted it.
            # My `old_string` was:
            # `    _FST = t.TypeVar('_FST', bound=AbstractFileSystem)`
            # `    _ASFST = t.TypeVar('_ASFST', bound=AsyncFileSystem)`
            # `class CloudFileSystemPurePath(PurePath):`
            
            # If `_FST` was indented, it was inside `if t.TYPE_CHECKING:`.
            # Code:
            # if t.TYPE_CHECKING:
            #    ...
            #    _FST = ...
            
            # If I put `class AsyncTransactionContext` inside `if t.TYPE_CHECKING:`, it won't exist at runtime.
            # I messed up. I need to move `AsyncTransactionContext` to global scope.
            
            pass
        
        # I need to fix `AsyncTransactionContext` definition first.
        pass

    def cloze(self, **kwargs):
        if self._fileio:
            self._fileio.commit()
        return self._accessor.invalidate_cache(self.fspath_)

    async def acloze(self, **kwargs):
        return await self._accessor.ainvalidate_cache(self.fspath_)

    def get_checksum(
        self,
        method: str = 'md5',
        chunk_size: int = 1024,
        **kwargs
    ):
        """
        Creates the checksum for the file
        """
        hashmethod = getattr(hashlib, method)
        hasher = hashmethod()
        with self.open('rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                hasher.update(chunk)
        checksum = hasher.hexdigest()
        del hasher
        return checksum

    async def aget_checksum(
        self,
        method: str = 'md5',
        chunk_size: int = 1024,
        **kwargs
    ):
        """
        Creates the checksum for the file
        """
        hashmethod = getattr(hashlib, method)
        hasher = hashmethod()
        async with self.aopen('rb') as f:
            if not self.is_fsspec:
                for byte_block in await iter(lambda: f.read(chunk_size), b""):
                    hasher.update(byte_block)
            else:
                byte_block = await f.read(chunk_size)
                while byte_block:
                    hasher.update(byte_block)
                    byte_block = await f.read(chunk_size)
        checksum = hasher.hexdigest()
        del hasher
        return checksum

    @classmethod
    def get_object_size(cls, obj: t.Any) -> ObjectSize:
        """
        Returns the size of the object
        """
        return ObjectSize(obj)


class CloudFileSystemPosixPath(PosixPath, CloudFileSystemPath, PureCloudFileSystemPosixPath):
    __slots__ = ()


class CloudFileSystemWindowsPath(WindowsPath, CloudFileSystemPath, PureCloudFileSystemWindowsPath):
    __slots__ = ()

    def is_mount(self) -> int:
        raise NotImplementedError("CloudFileSystemPath.is_mount() is unsupported on this system")

    async def async_is_mount(self) -> int:
        raise NotImplementedError("CloudFileSystemPath.async_is_mount() is unsupported on this system")


os.PathLike.register(CloudFileSystemPurePath)
os.PathLike.register(CloudFileSystemPath)
os.PathLike.register(PureCloudFileSystemPosixPath)
os.PathLike.register(CloudFileSystemWindowsPath)
os.PathLike.register(CloudFileSystemPosixPath)
os.PathLike.register(PureCloudFileSystemWindowsPath)

if PYDANTIC_VERSION == 2:
    from pydantic import TypeAdapter
    
def register_pathlike(pathz: t.List[t.Union[PosixPath, CloudFileSystemPath, WindowsPath, CloudFileSystemWindowsPath, CloudFileSystemPosixPath, PureCloudFileSystemWindowsPath, t.Any]]):
    for p in pathz:
        os.PathLike.register(p)
        # if PYDANTIC_VERSION == 2:
        #     TypeAdapter(p)

def register_pydantictype(pathz: t.Union[PosixPath, CloudFileSystemPath, WindowsPath, CloudFileSystemWindowsPath, CloudFileSystemPosixPath, PureCloudFileSystemWindowsPath, t.Any]):
    if PYDANTIC_VERSION != 2: return
    TypeAdapter(pathz)
