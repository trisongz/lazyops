
import lazyops.libs.sqlcache.base
import os
import io
import zlib
import gzip
import codecs
import struct
import sqlite3
import errno
import pickletools
import dill as pkl
import os.path as op
import functools as ft
import contextlib as cl

from fileio.lib.types import File, FileLike
from typing import Any, Iterable, AsyncIterable, Optional
from lazyops.utils.pooler import ThreadPooler
from lazyops.libs.sqlcache.types import BaseMedium
from lazyops.libs.sqlcache.constants import (
    UNKNOWN,
    MODE_NONE,
    MODE_RAW,
    MODE_TEXT,
    MODE_BINARY,
    MODE_PICKLE,
    KeyT,
    ValueT,
    WindowsExceptionError,
)


class Disk(BaseMedium):
    """
    Disk Based Medium 
    
    Store key and value serialization for SQLite database and files.
    """

    def __init__(
        self, 
        directory: Optional[FileLike] = None, 
        min_file_size: int = 0, 
        pickle_protocol: int = 3, 
        **config
    ):
        """Initialize disk instance.
        :param str directory: directory path
        :param int min_file_size: minimum size for file use
        :param int pickle_protocol: pickle protocol for serialization
        :param dict config: dict to pass to update sql settings
        """
        self._directory = File(directory) or File.get_tempdir(prefix = 'lazyops')
        self.min_file_size = min_file_size
        self.pickle_protocol = pickle_protocol
        self.config = config


    def store(self, value: ValueT, read: bool, key: KeyT = UNKNOWN):
        """Convert `value` to fields size, mode, filename, and value for Store
        table.
        :param value: value to convert
        :param bool read: True when value is file-like object
        :param key: key for item (default UNKNOWN)
        :return: (size, mode, filename, value) tuple for Store table
        """
        # pylint: disable=unidiomatic-typecheck
        type_value = type(value)
        min_file_size = self.min_file_size

        if (
            (type_value is str and len(value) < min_file_size)
            or (
                type_value is int
                and -9223372036854775808 <= value <= 9223372036854775807
            )
            or (type_value is float)
        ):
            return 0, MODE_RAW, None, value
        elif type_value is bytes:
            if len(value) < min_file_size:
                return 0, MODE_RAW, None, sqlite3.Binary(value)
            filename, full_path = self.filename(key, value)
            self._write(full_path, io.BytesIO(value), 'xb')
            return len(value), MODE_BINARY, filename, None
        elif type_value is str:
            filename, full_path = self.filename(key, value)
            self._write(full_path, io.StringIO(value), 'x', 'UTF-8')
            # size = op.getsize(full_path)
            size = full_path.size()
            # size = (full_path.info())['size']
            return size, MODE_TEXT, filename, None
        elif read:
            reader = ft.partial(value.read, 2**22)
            filename, full_path = self.filename(key, value)
            iterator = iter(reader, b'')
            size = self._write(full_path, iterator, 'xb')
            return size, MODE_BINARY, filename, None

        result = self.serialize(result)
        if len(result) < min_file_size:
            return 0, MODE_PICKLE, None, sqlite3.Binary(result)
        filename, full_path = self.filename(key, value)
        self._write(full_path, io.BytesIO(result), 'xb')
        return len(result), MODE_PICKLE, filename, None
    
    async def astore(self, value: ValueT, read: bool, key: KeyT = UNKNOWN):
        """Convert `value` to fields size, mode, filename, and value for Store
        table.
        :param value: value to convert
        :param bool read: True when value is file-like object
        :param key: key for item (default UNKNOWN)
        :return: (size, mode, filename, value) tuple for Store table
        """
        # pylint: disable=unidiomatic-typecheck
        type_value = type(value)
        min_file_size = self.min_file_size

        if (
            (type_value is str and len(value) < min_file_size)
            or (
                type_value is int
                and -9223372036854775808 <= value <= 9223372036854775807
            )
            or (type_value is float)
        ):
            return 0, MODE_RAW, None, value
        elif type_value is bytes:
            if len(value) < min_file_size:
                return 0, MODE_RAW, None, sqlite3.Binary(value)
            filename, full_path = self.filename(key, value)
            await self._awrite(full_path, io.BytesIO(value), 'xb')
            return len(value), MODE_BINARY, filename, None
        elif type_value is str:
            filename, full_path = self.filename(key, value)
            await self._awrite(full_path, io.StringIO(value), 'x', 'UTF-8')
            size = await full_path.async_size()
            # size = (await full_path.async_info())['size']
            # size = op.getsize(full_path)
            return size, MODE_TEXT, filename, None
        elif read:
            reader = ft.partial(value.read, 2**22)
            filename, full_path = self.filename(key, value)
            iterator = iter(reader, b'')
            size = await self._awrite(full_path, iterator, 'xb')
            return size, MODE_BINARY, filename, None

        result = await self.aserialize(value)
        # result = pkl.dumps(value, protocol=self.pickle_protocol)
        if len(result) < min_file_size:
            return 0, MODE_PICKLE, None, sqlite3.Binary(result)
        filename, full_path = self.filename(key, value)
        await self._awrite(full_path, io.BytesIO(result), 'xb')
        return len(result), MODE_PICKLE, filename, None
    
    def _write(self, full_path: FileLike, iterator: Iterable, mode: str, encoding: str = None):
        # full_dir, _ = op.split(full_path)
        full_dir = full_path.parent
        for count in range(1, 11):
            with cl.suppress(OSError):
                full_dir.mkdir(parents=True, exist_ok=True)
                # os.makedirs(full_dir)

            try:
                # Another cache may have deleted the directory before
                # the file could be opened.
                writer = full_path.open(mode = mode, encoding = encoding)
                # writer = open(full_path, mode, encoding=encoding)
            except OSError:
                if count == 10:
                    # Give up after 10 tries to open the file.
                    raise
                continue

            with writer:
                size = 0
                for chunk in iterator:
                    size += len(chunk)
                    writer.write(chunk)
                return size
    
    async def _awrite(self, full_path: FileLike, iterator: Iterable, mode: str, encoding: str = None):
        full_dir = full_path.parent
        for count in range(1, 11):
            with cl.suppress(OSError):
                full_dir.mkdir(parents=True, exist_ok=True)

            try:
                # Another cache may have deleted the directory before
                # the file could be opened.
                writer = full_path.async_open(mode = mode, encoding = encoding)
            except OSError:
                if count == 10:
                    # Give up after 10 tries to open the file.
                    raise
                continue

            async with writer:
                size = 0
                for chunk in iterator:
                    size += len(chunk)
                    await writer.write(chunk)
                return size

    def fetch(self, mode: int, filename: str, value: ValueT, read: bool):
        """Convert fields `mode`, `filename`, and `value` from Store table to
        value.
        :param int mode: value mode raw, binary, text, or pickle
        :param str filename: filename of corresponding value
        :param value: database value
        :param bool read: when True, return an open file handle
        :return: corresponding Python value
        """
        # pylint: disable=no-self-use,unidiomatic-typecheck
        if mode == MODE_RAW:
            return bytes(value) if type(value) is sqlite3.Binary else value
        elif mode == MODE_BINARY:
            if read:
                return self._directory.joinpath(filename).open('rb')
                # return open(op.join(self._directory, filename), 'rb')
            return self._directory.joinpath(filename).read_bytes()
            # with open(op.join(self._directory, filename), 'rb') as reader:
            #     return reader.read()
        elif mode == MODE_TEXT:
            return self._directory.joinpath(filename).read_text(encoding='UTF-8')
            # full_path = op.join(self._directory, filename)
            # with open(full_path, 'r', encoding='UTF-8') as reader:
            #     return reader.read()
        elif mode == MODE_PICKLE:
            if value is not None: return self.deserialize(io.BytesIO(value))
            return self.deserialize(self._directory.joinpath(filename).read_bytes())
            # with open(op.join(self._directory, filename), 'rb') as reader:
            #     return pkl.load(reader)

    async def afetch(self, mode: int, filename: str, value: ValueT, read: bool):
        """Convert fields `mode`, `filename`, and `value` from Store table to
        value.
        :param int mode: value mode raw, binary, text, or pickle
        :param str filename: filename of corresponding value
        :param value: database value
        :param bool read: when True, return an open file handle
        :return: corresponding Python value
        """
        if mode == MODE_RAW:
            return bytes(value) if type(value) is sqlite3.Binary else value
        elif mode == MODE_BINARY:
            if read: return self._directory.joinpath(filename).async_open('rb')
            return await self._directory.joinpath(filename).async_read_bytes()
        
        elif mode == MODE_TEXT:
            return await self._directory.joinpath(filename).async_read_text(encoding='UTF-8')

        elif mode == MODE_PICKLE:
            if value is not None: return await self.adeserialize(io.BytesIO(value))
            return await self.adeserialize(await self._directory.joinpath(filename).async_read_bytes())

    def filename(self, key: KeyT = UNKNOWN, value: ValueT = UNKNOWN):
        """Return filename and full-path tuple for file storage.
        Filename will be a randomly generated 28 character hexadecimal string
        with ".val" suffixed. Two levels of sub-directories will be used to
        reduce the size of directories. On older filesystems, lookups in
        directories with many files may be slow.
        The default implementation ignores the `key` and `value` parameters.
        In some scenarios, for example :meth:`Store.push
        <diskcache.Store.push>`, the `key` or `value` may not be known when the
        item is stored in the cache.
        :param key: key for item (default UNKNOWN)
        :param value: value for item (default UNKNOWN)
        """
        # pylint: disable=unused-argument
        hex_name = codecs.encode(os.urandom(16), 'hex').decode('utf-8')
        sub_dir = op.join(hex_name[:2], hex_name[2:4])
        name = f'{hex_name[4:]}.val'
        directory = self._directory.joinpath(sub_dir)
        # directory = op.join(self._directory, sub_dir)
        try:
            directory.mkdir(parents=True, exist_ok=True)
            # os.makedirs(directory)
        except OSError as error:
            if error.errno != errno.EEXIST:
                raise
        
        filename = op.join(sub_dir, name)
        full_path = self._directory.joinpath(filename)
        # full_path = op.join(self._directory, filename)
        return filename, full_path

    def remove(self, filename: str):
        """Remove a file given by `filename`.
        This method is cross-thread and cross-process safe. If an "error no
        entry" occurs, it is suppressed.
        :param str filename: relative path to file
        """
        # full_path = op.join(self._directory, filename)
        full_path = self._directory.joinpath(filename)
        try:
            # os.remove(full_path)
            full_path.unlink()

        except WindowsExceptionError:
            pass
        except OSError as error:
            if error.errno != errno.ENOENT:
                # ENOENT may occur if two caches attempt to delete the same
                # file at the same time.
                raise

    async def aremove(self, filename: str):
        """Remove a file given by `filename`.
        This method is cross-thread and cross-process safe. If an "error no
        entry" occurs, it is suppressed.
        :param str filename: relative path to file
        """
        # full_path = op.join(self._directory, filename)
        full_path = self._directory.joinpath(filename)
        try:
            # os.remove(full_path)
            await full_path.async_unlink()

        except WindowsExceptionError:
            pass
        except OSError as error:
            if error.errno != errno.ENOENT:
                # ENOENT may occur if two caches attempt to delete the same
                # file at the same time.
                raise


class CompressedDisk(Disk):
    "Store key and value using with zlib compression."

    def __init__(
        self, 
        directory: Optional[FileLike] = None, 
        compression_level: int = 3, 
        **config
    ):
        """Initialize Pickle disk instance.
        Keys and values are compressed using the zlib library. The
        `compress_level` is an integer from 0 to 9 controlling the level of
        compression; 1 is fastest and produces the least compression, 9 is
        slowest and produces the most compression, and 0 is no compression.
        :param str directory: directory path
        :param int compression_level: zlib compression level (default 3)
        :param kwargs: super class arguments
        """
        self.compression_level = compression_level
        super().__init__(directory = directory, **config)

    
    def serialize(self, value: ValueT, protocol: Optional[Any] = None, optimize: Optional[bool] = False, **kwargs) -> bytes:
        """
        Serialize value to bytes
        """
        protocol = protocol or self.pickle_protocol
        data = pkl.dumps(value, protocol=self.pickle_protocol)
        if optimize: data = pickletools.optimize(data)
        data = zlib.compress(data, self.compression_level)
        return data
    

    def deserialize(self, data: bytes, **kwargs) -> ValueT:
        """
        Deserialize bytes to value
        """
        return pkl.loads(zlib.decompress(data))

