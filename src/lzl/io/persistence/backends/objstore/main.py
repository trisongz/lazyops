from __future__ import annotations

"""
Remote Object Storage Backend Dict-Like Persistence
"""

import concurrent.futures
from lzl.pool import ThreadPool
from lzo.types import Literal, eproperty
from lzl.io.file import File
from typing import TypeVar, Generic, Any, Dict, Optional, Union, Tuple, Iterable, List, Type, Callable, Generator, AsyncGenerator, TYPE_CHECKING
from ..base import BaseStatefulBackend, SchemaType, create_unique_id, logger
from .expirations import FileExpirationBackend, RedisExpirationBackend

if TYPE_CHECKING:
    from lzl.io.file import FileLike

# TODO: add caching support for lookups
_logged_backend: bool = False

def _display_backend(backend: str):
    """
    Displays the backend
    """
    global _logged_backend
    if _logged_backend: return
    logger.info(f'Using Object Storage Expiration Backend: `|g|{backend}|e|`', colored = True)
    _logged_backend = True


class ObjStorageStatefulBackend(BaseStatefulBackend):
    """
    Implements an Object Storage Stateful Backend

    Supports:
    - Local File System
    - S3
    - R2

    Implements either filebased expiration or redis expiration
    """
    name: Optional[str] = "objstore"
    expiration: Optional[int] = None
    file_ext: Optional[str] = None
    file_pre: Optional[str] = None
    auto_delete_invalid: Optional[bool] = False

    def __init__(
        self,
        base_key: Union[str, 'File'],
        name: Optional[str] = None,
        expiration: Optional[int] = None,
        async_enabled: Optional[bool] = False,
        file_ext: Optional[str] = None,
        file_pre: Optional[str] = None,
        auto_delete_invalid: Optional[bool] = None,
        serializer: Optional[str] = 'json',
        serializer_kwargs: Optional[Dict[str, Any]] = None,
        expiration_backend: Optional[Literal['auto', 'file', 'redis']] = 'auto', # ``
        **kwargs,
    ):
        """
        Initializes the backend

        Args:
            base_key (str, File): 
                The base key for the backend.
                Either a string or a file-io File object.

                Examples:
                - base_key = 's3://mybucket/mykey'
                - base_key = File('s3://mybucket/mykey')

            name (str, optional): The name of the backend. Defaults to None.
            expiration (int, optional): The expiration time in seconds. Defaults to None.
        """
        if isinstance(base_key, str): base_key = File(base_key)
        self.base_key: 'File' = base_key
        if name is not None: self.name = name
        if expiration is not None: 
            self.expiration = expiration
        self.async_enabled = async_enabled
        self.expiration_backend = expiration_backend

        if file_ext is not None: 
            file_ext = file_ext.lstrip('.')
            self.file_ext = file_ext
        if file_pre is not None: self.file_pre = file_pre
        if auto_delete_invalid is not None: self.auto_delete_invalid = auto_delete_invalid
        self._setup_exp_backend()

        # self.exp_file: 'File' = self.base_key.joinpath(f'.{self.name}.metadata.expires')
        
        from lzl.io.ser import get_serializer
        self.serializer = get_serializer(serializer = serializer, **(serializer_kwargs or {}))
        self._exp_ser = get_serializer(serializer = 'json')
        self._kwargs = kwargs
        self._kwargs['serializer'] = serializer
        self._kwargs['serializer_kwargs'] = serializer_kwargs
        self._kwargs['async_enabled'] = async_enabled
        self._kwargs['expiration'] = expiration
        self._kwargs['name'] = name
        self._kwargs['file_ext'] = file_ext
        self._kwargs['file_pre'] = file_pre
        self._kwargs['auto_delete_invalid'] = auto_delete_invalid
        self._kwargs['expiration_backend'] = self.expiration_backend
    
    def _setup_exp_backend(self):
        """
        Sets up the expiration backend
        """
        # Try to determine the expiration backend
        # Also handle automigration
        if self.expiration_backend == 'auto': 
            if RedisExpirationBackend.is_available(): self.expiration_backend = 'redis'
            else: self.expiration_backend = 'file'
            _display_backend(self.expiration_backend)
        if self.expiration_backend == 'file':
            self.exp_backend = FileExpirationBackend(backend = self)
        elif self.expiration_backend == 'redis':
            self.exp_backend = RedisExpirationBackend(backend = self)
        else:
            raise ValueError(f'Invalid Expiration Backend: {self.expiration_backend}')
        # logger.info(f'Using Expiration Backend: {self.exp_backend.name}')
        

    def get_writer(self, f: 'File', is_async: Optional[bool] = None) -> Callable[[Union[str, bytes]], Any]:
        """
        Returns a writer for the file
        """
        if is_async:
            return f.awrite_bytes if self.serializer.is_binary else f.awrite_text
        return f.write_bytes if self.serializer.is_binary else f.write_text

    def read_file(self, f: 'File', is_async: Optional[bool] = None):
        """
        Returns a reader for the file
        """
        if is_async:
            return f.aread_bytes() if self.serializer.is_binary else f.aread_text()
        return f.read_bytes() if self.serializer.is_binary else f.read_text()

    def write_file(self, f: 'File', data: Any, is_async: Optional[bool] = None):
        """
        Returns a writer for the file
        """
        if is_async:
            return f.awrite_bytes(data) if self.serializer.is_binary else f.awrite_text(data)
        return f.write_bytes(data) if self.serializer.is_binary else f.write_text(data)

    def _precheck(self, **kwargs):
        """
        Run a precheck operation
        """
        pass


    """
    Implemented Methods
    """

    def get_key(self, key: str) -> 'FileLike':
        """
        Gets a Key
        """
        if self.file_pre: key = self.file_pre + key
        if self.file_ext: key += f'.{self.file_ext}'
        return self.base_key.joinpath(key)
    
    def _fetch_one(
        self, 
        key: str, 
        default: Optional[Any] = None, 
        _raw: Optional[bool] = None, 
        _with_key: Optional[bool] = False,
        **kwargs
    ) -> Union[Optional[Any], Tuple[str, Any]]:
        """
        Fetches a Value from the Object Store
        """
        f_key = self.get_key(key)
        if not f_key.exists(): 
            return (key, default) if _with_key else default
        value = self.read_file(f_key)
        if value is None: 
            return (key, default) if _with_key else default
        if _raw: return (key, value) if _with_key else value
        try:
            decoded = self.decode_value(value, _raw = _raw, **kwargs)
            if decoded is None: 
                return (key, default) if _with_key else default
            return (key, decoded) if _with_key else decoded
        except Exception as e:
            logger.info(f'Error Decoding Value: |r|({type(value)}) {e}|e| {value}', colored = True, prefix = f_key.as_posix())
            if self.auto_delete_invalid: self.delete(key)
            return (key, default) if _with_key else default
    
    def _set_one(
        self, 
        key: str, 
        value: Any,
        _raw: Optional[bool] = None, 
        _with_key: Optional[bool] = False,
        **kwargs
    ) -> Union[Optional['File'], Tuple[str, 'File']]:
        """
        Fetches a Value from the Object Store
        """
        f_key = self.get_key(key)
        try:
            encoded = self.encode_value(value, _raw = _raw, **kwargs)
        except Exception as e:
            logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {value}', colored = True, prefix = f_key.as_posix())
            return (key, None) if _with_key else None
        try:
            self.write_file(f_key, encoded)
            return (key, f_key) if _with_key else f_key
        except Exception as e:
            logger.info(f'Error Writing Value: |r|({type(value)}) {e}|e| {value}', colored = True, prefix = f_key.as_posix())
            return (key, None) if _with_key else None


    def get(self, key: str, default: Optional[Any] = None, _raw: Optional[bool] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the Object Store
        """
        self.exp_backend._check(key)
        # self._run_expiration_check(key)
        return self._fetch_one(key, default, _raw = _raw, **kwargs)

    def get_values(self, keys: Iterable[str]) -> List[Any]:
        """
        Gets a Value from the Object Store
        """
        # self._run_expiration_check(*keys)
        self.exp_backend._check(*keys)
        results = []
        result_map = {key: None for key in keys}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self._fetch_one, key, _with_key = True) for key in keys]
            results.extend(
                future.result()
                for future in concurrent.futures.as_completed(futures)
            )
        # Map them to the original index
        for key, value in results:
            result_map[key] = value
        return list(result_map.values())
        

    def set(self, key: str, value: Any, ex: Optional[int] = None, _raw: Optional[bool] = None, **kwargs) -> Optional['File']:
        """
        Saves a Value to the Object Store
        """
        f_key = self._set_one(key, value, _raw = _raw, **kwargs)
        if f_key is None: return
        self.exp_backend._set(key, ex = ex)
        # self._set_expiration(key, ex = ex)
        return f_key

    def _set_batch(self, data: Dict[str, Any], ex: Optional[int] = None, _raw: Optional[bool] = None, **kwargs) -> Dict[str, Optional['File']]:
        """
        Saves a Value to the Object Store
        """
        results = []
        exp_keys = []
        result_map = {key: None for key in data}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self._set_one, key, value, _with_key = True, _raw = _raw, **kwargs) for key, value in data.items()]
            results.extend(
                future.result()
                for future in concurrent.futures.as_completed(futures)
            )
        # Map them to the original index
        for key, value in results:
            result_map[key] = value
            if value is not None: exp_keys.append(key)
        if exp_keys: self.exp_backend._set(*exp_keys, ex = ex)
        # if exp_keys: self._set_expiration(*exp_keys, ex = ex)
        return result_map

    def _set_batch_fallback(self, data: Dict[str, Any], ex: Optional[int] = None, _raw: Optional[bool] = None, **kwargs) -> Dict[str, Optional['File']]:
        """
        Saves a Value to the Object Store
        """
        exp_keys = []
        result_map = {key: None for key in data}
        for key, value in data.items():
            result_map[key] = self._set_one(key, value, _raw = _raw, **kwargs)
            if result_map[key] is not None: exp_keys.append(key)
        if exp_keys: self.exp_backend._set(*exp_keys, ex = ex)
        # if exp_keys: self._set_expiration(*exp_keys, ex = ex)
        return result_map

    def set_batch(self, data: Dict[str, Any], ex: Optional[int] = None, _raw: Optional[bool] = None, **kwargs) -> Dict[str, Optional['File']]:
        """
        Saves a Value to the Object Store
        """
        try:
            return self._set_batch(data, ex = ex, _raw = _raw, **kwargs)
        except RuntimeError as e:
            # logger.info(f'Unable to Set Batch: {e}', colored = True, prefix = self.base_key.as_posix())
            raise e
        except Exception as e:
            logger.info(f'[Fallback] Error Setting Batch: {e}', colored = True, prefix = self.base_key.as_posix())
            return self._set_batch_fallback(data, ex = ex, _raw = _raw, **kwargs)

    def _delete_one(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from the Object Store
        """
        f_key = self.get_key(key)
        f_key.rm(missing_ok=True)

    def delete(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from the Object Store
        """
        self.exp_backend._remove(key)
        self._delete_one(key, **kwargs)
        

    def _clear(self, *keys: str, **kwargs):
        """
        Clears the Keys from the Object Store
        """
        for _ in ThreadPool.iterate(
            self._delete_one,
            keys,
            return_ordered = False,
            **kwargs
        ):
            pass

        
    def clear(self, *keys: str, **kwargs):
        """
        Clears the Keys from the Object Store
        """
        # self._remove_expiration(*keys)
        self.exp_backend._remove(*keys)
        self._clear(*keys, **kwargs)

    async def _afetch_one(
        self, 
        key: str, 
        default: Optional[Any] = None, 
        _raw: Optional[bool] = None, 
        _with_key: Optional[bool] = False,
        **kwargs
    ) -> Union[Optional[Any], Tuple[str, Any]]:
        """
        Fetches a Value from the Object Store
        """
        f_key = self.get_key(key)
        if not await f_key.aexists(): 
            return (key, default) if _with_key else default
        value = await self.read_file(f_key, is_async = True)
        if value is None: 
            return (key, default) if _with_key else default
        if _raw: return (key, value) if _with_key else value
        try:
            decoded = await self.adecode_value(value, _raw = _raw, **kwargs)
            if decoded is None: 
                return (key, default) if _with_key else default
            return (key, decoded) if _with_key else decoded
        except Exception as e:
            logger.info(f'Error Decoding Value: |r|({type(value)}) {e}|e| {value}', colored = True, prefix = f_key.as_posix())
            if self.auto_delete_invalid: await self.adelete(key)
            return (key, default) if _with_key else default
    
    async def _aset_one(
        self, 
        key: str, 
        value: Any,
        _raw: Optional[bool] = None, 
        _with_key: Optional[bool] = False,
        **kwargs
    ) -> Union[Optional['File'], Tuple[str, 'File']]:
        """
        Fetches a Value from the Object Store
        """
        f_key = self.get_key(key)
        try:
            encoded = await self.aencode_value(value, _raw = _raw, **kwargs)
        except Exception as e:
            logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {value}', colored = True, prefix = f_key.as_posix())
            return (key, None) if _with_key else None
        try:
            await self.write_file(f_key, encoded, is_async = True)
            return (key, f_key) if _with_key else f_key
        except Exception as e:
            logger.info(f'Error Writing Value: |r|({type(value)}) {e}|e| {value}', colored = True, prefix = f_key.as_posix())
            return (key, None) if _with_key else None

    
    async def _aset_one_iter(
        self, 
        item: Tuple[str, Any],
        _raw: Optional[bool] = None, 
        _with_key: Optional[bool] = False,
        **kwargs
    ) -> Union[Optional['File'], Tuple[str, 'File']]:
        """
        Fetches a Value from the Object Store
        """
        key, value = item
        return await self._aset_one(key, value, _raw = _raw, _with_key = _with_key, **kwargs)

    async def _adelete_one(
        self,
        key: str,
        **kwargs,
    ):
        """
        Deletes a Value from the Object Store
        """
        f_key = self.get_key(key)
        await f_key.arm(missing_ok=True)

    async def aget(self, key: str, default: Optional[Any] = None, _raw: Optional[bool] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the Object Store
        """
        await self.exp_backend._acheck(key)
        return await self._afetch_one(key, default, _raw = _raw, **kwargs)

    async def aget_values(self, keys: Iterable[str], **kwargs) -> List[Any]:
        """
        Gets a Value from the DB
        """
        await self.exp_backend._acheck(*keys)
        results = []
        async for result in ThreadPool.aiterate(
            self._afetch_one,
            keys,
            return_ordered = True,
            **kwargs
        ):
            results.append(result)
        return results

    
    async def aset(self, key: str, value: Any, ex: Optional[int] = None, _raw: Optional[bool] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        f_key = await self._aset_one(key, value, _raw = _raw, **kwargs)
        if f_key is None: return
        await self.exp_backend._aset(key, ex = ex)
        return f_key
        

    async def aset_batch(self, data: Dict[str, Any], ex: Optional[int] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        results = []
        exp_keys = []
        items = list(data.items())
        async for (key, value) in ThreadPool.aiterate(
            self._aset_one_iter,
            items,
            return_ordered = True,
            _with_key = True,
            **kwargs
        ):
            results.append(value)
            if value is not None: exp_keys.append(key)
        if exp_keys: await self.exp_backend._aset(*exp_keys, ex = ex)
        # if exp_keys: await self._aset_expiration(*exp_keys, ex = ex)
        return results

    async def adelete(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from the DB
        """
        await self.exp_backend._aremove(key)
        # await self._aremove_expiration(key)
        await self._adelete_one(key, **kwargs)

    async def _aclear(self, *keys: str, **kwargs):
        """
        Clears the Cache
        """
        await ThreadPool.amap(
            self._adelete_one,
            keys,
            return_ordered = False,
            **kwargs
        )

    async def aclear(self, *keys: str, **kwargs):
        """
        Clears the Cache
        """
        await self.exp_backend._aremove(*keys)
        # await self._aremove_expiration(*keys)
        await self._aclear(*keys, **kwargs)

    def _fetch_objstr_f_keys(
        self, 
        pattern: Optional[str] = '*', 
        **kwargs
    ) -> List['File']:
        """
        Returns the Keys within the current object storage
        """
        self.exp_backend._check(validate = True)
        return [f_key for f_key in self.base_key.glob(pattern = pattern) if f_key.is_file() and 'metadata.expires' not in f_key.name]

    async def _afetch_objstr_f_keys(
        self,
        pattern: Optional[str] = '*', 
        **kwargs
    ) -> List['File']:
        """
        Returns the Keys within the current object storage
        """
        await self.exp_backend._acheck(validate = True)
        f_keys: List['File'] = list(await self.base_key.aglob(pattern=pattern))
        return [f_key for f_key in f_keys if f_key.is_file() and 'metadata.expires' not in f_key.name]

    def _parse_f_keys_to_str(
        self,
        f_keys: List['File'],
        exclude_base_key: Optional[bool] = None,
        **kwargs
    ) -> List[str]:
        """
        Returns the Keys within the current object storage
        """
        f_key_strs: List[str] = [f_key.as_posix() for f_key in f_keys]
        if exclude_base_key: 
            base_key_str = self.base_key.as_posix()
            f_key_strs = [f_key.replace(base_key_str, '') for f_key in f_key_strs]
        return f_key_strs

    def get_keys(
        self, 
        pattern: str, 
        exclude_base_key: Optional[bool] = None, 
        as_file: Optional[bool] = None,
        **kwargs
    ) -> Union[List[str], List['File']]:
        """
        Returns the Keys within the current object storage
        """
        # self._run_expiration_check()
        self.exp_backend._check(validate = True)
        f_keys = self._fetch_objstr_f_keys(pattern = pattern)
        if as_file: return f_keys
        return self._parse_f_keys_to_str(f_keys, exclude_base_key = exclude_base_key, **kwargs)

    def get_all_keys(
        self, 
        exclude_base_key: Optional[bool] = False, 
        as_file: Optional[bool] = None,
        **kwargs
    ) -> Union[List[str], List['File']]:
        """
        Returns all the Keys
        """
        self.exp_backend._check(validate = True)
        f_keys = self._fetch_objstr_f_keys()
        if as_file: return f_keys
        return self._parse_f_keys_to_str(f_keys, exclude_base_key = exclude_base_key, **kwargs)
    

    def length(self, **kwargs) -> int:
        """
        Returns the Length of the Cache
        """
        # self._run_expiration_check()
        self.exp_backend._check(validate = True)
        f_keys = self._fetch_objstr_f_keys()
        return len(f_keys)
    
    async def alength(self, **kwargs) -> int:
        """
        Returns the Length of the Cache
        """
        # await self._arun_expiration_check()
        await self.exp_backend._acheck(validate = True)
        f_keys = await self._afetch_objstr_f_keys()
        return len(f_keys)

    def __len__(self):
        """
        Returns the Length of the Cache
        """
        return self.length()

    def contains(self, key, **kwargs):
        """
        Returns True if the Cache contains the Key
        """
        self.exp_backend._check(key)
        f_key = self.get_key(key)
        return f_key.exists()
    
    async def acontains(self, key, **kwargs):
        """
        Returns True if the Cache contains the Key
        """
        await self.exp_backend._acheck(key)
        f_key = self.get_key(key)
        return await f_key.aexists()
    
    def expire(self, key: str, ex: int, **kwargs) -> None:
        """
        Expires a Key
        """
        self.exp_backend._set(key, ex = ex, validate = True)
    
    async def aexpire(self, key: str, ex: int, **kwargs) -> None:
        """
        Expires a Key
        """
        await self.exp_backend._aset(key, ex = ex, validate = True)

    def purge(self, **kwargs) -> None:
        """
        Purges the cache
        """
        logger.warning('Purging the Cache is not recommended. Use `clear` instead.')
        f_keys = list(self.base_key.glob(pattern = '*', as_path = False))
        logger.info(f'Purging {len(f_keys)} Keys')
        self.base_key.rm(recursive = True, missing_ok = True)
        # self.clear(*f_keys, **kwargs)

    async def apurge(self, **kwargs) -> None:
        """
        Purges the cache
        """
        logger.warning('Purging the Cache is not recommended. Use `clear` instead.')
        f_keys = list(await self.base_key.aglob(pattern = '*', as_path = False))
        logger.info(f'Purging {len(f_keys)} Keys')
        await self.base_key.arm(recursive = True, missing_ok = True)
        # await self.aclear(*f_keys, **kwargs)


    """
    Add methods that reflect the `PersistentDict` API
    so that it can be used as a standalone backend
    """

    def get_child(self, key: str, **kwargs) -> 'ObjStorageStatefulBackend':
        """
        Gets a Child Persistent Dictionary
        """
        base_key = self.base_key.joinpath(key)
        if 'async_enabled' not in kwargs:
            kwargs['async_enabled'] = self.async_enabled
        base_kwargs = self._kwargs.copy()
        base_kwargs.update(kwargs)
        return self.__class__(
            base_key = base_key, 
            **base_kwargs
        )


    def __repr__(self):
        """
        Returns the Representation of the Cache
        """
        return f"<{self.__class__.__name__} num_keys={len(self)}, base_key={self.base_key}, serializer={self.serializer.name}>"