from __future__ import annotations

"""
SQLite Backend Dict-Like Persistence
"""
import copy
import typing as t
from typing import TypeVar, Generic, Any, Dict, Optional, Union, Tuple, Iterable, List, Type, Callable, Generator, AsyncGenerator, TYPE_CHECKING
from ..base import BaseStatefulBackend, SchemaType, create_unique_id, logger
from .db import SqliteDB, SqliteDsn, Optimization, ENOVAL


class SqliteStatefulBackend(BaseStatefulBackend):
    """
    Implements an Sqlite Stateful Backend
    """

    name: Optional[str] = "sqlite"
    table: Optional[str] = "cache"
    expiration: Optional[int] = None
    auto_delete_invalid: Optional[bool] = False
    optimization: Optional[Optimization] = 'cache'

    def __init__(
        self,
        base_key: Optional[Union[str, SqliteDsn]] = None,
        name: Optional[str] = None,
        table: Optional[str] = None,
        expiration: Optional[int] = None,
        async_enabled: Optional[bool] = False,
        auto_delete_invalid: Optional[bool] = None,
        serializer: Optional[str] = 'json',
        serializer_kwargs: Optional[Dict[str, Any]] = None,
        optimization: Optional[str] = None,
        db_settings: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initializes the backend

        Args:
            base_key (str, SqliteDsn): 
                The base key for the backend.
                Either a string or a SQLite DSN.

                Examples:
                - base_key = 'sqlite://local/path/to/sqlite.db' - Will use the default table
                - base_key = 'sqlite://local/path/to/sqlite.db?table=mytable' - Will use the specified table
                - base_key = 'sqlite://host:1234?table=mytable' - Will use the specified table

            name (str, optional): The name of the backend. Defaults to None.
            table (str, optional): The table to use. Defaults to None.
            expiration (int, optional): The expiration time in seconds. Defaults to None.
        """
        # If it exists and is passed, then use it
        conn_uri: t.Optional[str] = kwargs.pop('conn_uri', None)
        is_remote: t.Optional[bool] = kwargs.pop('is_remote', None)
        _db: t.Optional[SqliteDB] = kwargs.pop('_db', None)

        configured = conn_uri is not None or _db is not None
        
        # We ignore the base key since each base key is a different table
        if not conn_uri:
            base_key_uri = SqliteDsn(base_key) if isinstance(base_key, str) else base_key
        
            # This is a local file
            if base_key_uri.path.endswith('.db'):
                conn_uri = str(base_key).split('?', 1)[0]
                conn_uri = conn_uri.replace('sqlite://', '')
                is_remote = False
            else:
                host = base_key_uri.hosts()[0]
                conn_uri = 'sqlite://'
                if host['username'] and host['password']:
                    conn_uri += f'{host["username"]}:{host["password"]}@'
                elif host['password']:
                    conn_uri += f'{host["password"]}@'
                conn_uri += f'{host["host"]}'
                if host['port']:
                    conn_uri += f':{host["port"]}'
                is_remote = True
            for k, v in base_key_uri.query_params():
                # If the arguments are passed, then prioritize them over the query params
                if k == 'table' and not table: table = v
                if k == 'expiration' and not expiration: expiration = int(v)
                if k == 'serializer': serializer = v
                if k == 'async_enabled': async_enabled = v in {'true', '1', 't', 'y', 'yes'}
                if k == 'auto_delete_invalid': auto_delete_invalid = v in {'true', '1', 't', 'y', 'yes'}
        
        # Now we'll configure the rest
        if name is not None: self.name = name
        if table is not None: self.table = table
        if expiration is not None:  self.expiration = expiration
        if optimization is not None: self.optimization = optimization
        self.async_enabled = async_enabled
        if auto_delete_invalid is not None: self.auto_delete_invalid = auto_delete_invalid
        from lzl.io.ser import get_serializer
        serializer_kwargs = serializer_kwargs or {}
        if 'verbosity' not in serializer_kwargs:
            serializer_kwargs['verbosity'] = 0
        self.serializer = get_serializer(serializer = serializer, **serializer_kwargs)
        self.db = SqliteDB(conn_uri = conn_uri, table = self.table, optimization = self.optimization, configured = configured, is_remote = is_remote, **(db_settings or {})) if \
            _db is None else _db
    
        self._kwargs = kwargs
        self._kwargs['serializer'] = serializer
        self._kwargs['serializer_kwargs'] = serializer_kwargs
        self._kwargs['async_enabled'] = async_enabled
        self._kwargs['expiration'] = expiration
        self._kwargs['name'] = name
        self._kwargs['optimization'] = optimization
        self._kwargs['conn_uri'] = conn_uri
        self._kwargs['db_settings'] = db_settings
        self._kwargs['is_remote'] = is_remote
        self._kwargs['auto_delete_invalid'] = auto_delete_invalid


    def getter(self, key: str, default: Optional[Any] = None, is_async: Optional[bool] = None) -> t.Union[Callable[[Union[str, bytes]], Any], Callable[..., t.Awaitable[Union[str, bytes]]]]:
        """
        Returns a getter function
        """
        return self.db.aget(key, default = default) if is_async else self.db.get(key, default = default)

    def setter(self, key: str, value: t.Union[str, bytes], ex: Optional[int] = None, tag: t.Optional[str] = None, is_async: Optional[bool] = None) -> t.Union[Callable[[Union[str, bytes], Any], Any], Callable[..., t.Awaitable[Any]]]:
        """
        Returns a setter function
        """
        ex = ex or self.expiration
        return self.db.aset(key, value, expire = ex, tag = tag) if is_async else self.db.set(key, value, expire = ex, tag = tag)

    def deleter(self, key: str, is_async: Optional[bool] = None):
        """
        Returns a deleter function
        """
        return self.db.adelete(key) if is_async else self.db.delete(key)
    
    def deleters(self, *keys: str, is_async: Optional[bool] = None) -> int:
        """
        Returns a deleter function
        """
        return self.db._delete_keys_(*keys) if is_async else self.db._adelete_keys_(*keys)
    
    def _contains(self, key: str, is_async: Optional[bool] = None) -> bool:
        """
        Returns whether the key is in the cache
        """
        return self.db.acontains(key) if is_async else self.db.contains(key)

    def _precheck(self, **kwargs):
        """
        Run a precheck operation
        """
        pass

    def get_child(self, key: str, **kwargs) -> 'SqliteStatefulBackend':
        """
        Gets a Child Persistent Dictionary
        """
        base_kwargs = copy.deepcopy(self._kwargs)
        base_kwargs.update(kwargs)
        # base_kwargs['db_settings'] = base_kwargs.get('db_settings', {}) or {}
        # logger.info(base_kwargs)
        db = self.db.get_child(key, timeout = base_kwargs.get('timeout'), **(base_kwargs.get('db_settings') or {}))
        return self.__class__(
            _db = db, 
            **base_kwargs
        )


    """
    Helper Methods
    """

    def _get_one(
        self, 
        key: str, 
        default: Optional[Any] = None, 
        _raw: Optional[bool] = None, 
        **kwargs
    ) -> Optional[Any]:
        """
        Fetches a Value from the DB
        """
        value = self.getter(key, default = ENOVAL, is_async = False)
        if value is ENOVAL: return default
        if _raw: return value
        try:
            decoded = self.decode_value(value, _raw = _raw, **kwargs)
            return default if decoded is None else decoded
        except Exception as e:
            logger.info(f'Error Decoding Value: |r|({type(value)}) {e}|e| {value}', colored = True)
            if self.auto_delete_invalid: self.deleter(key)
            return default

    async def _aget_one(
        self, 
        key: str, 
        default: Optional[Any] = None, 
        _raw: Optional[bool] = None, 
        **kwargs
    ) -> Optional[Any]:
        """
        [Async] Fetches a Value from the DB
        """
        value = await self.getter(key, default = ENOVAL, is_async = True)
        if value is ENOVAL: return default
        if _raw: return value
        try:
            decoded = await self.adecode_value(value, _raw = _raw, **kwargs)
            return default if decoded is None else decoded
        except Exception as e:
            logger.info(f'Error Decoding Value: |r|({type(value)}) {e}|e| {value}', colored = True)
            if self.auto_delete_invalid: await self.deleter(key)
            return default
        
    def _set_one(
        self, 
        key: str, 
        value: Any, 
        ex: Optional[int] = None, 
        tag: Optional[str] = None, 
        _raw: Optional[bool] = None, 
        **kwargs
    ):
        """
        Saves a Value to the DB
        """
        try:
            value = self.encode_value(value, _raw = _raw, **kwargs)
        except Exception as e:
            logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {value}', colored = True)
            return None
        try:
            return self.setter(key, value, ex = ex, tag = tag, is_async = False)
        except Exception as e:
            logger.info(f'Error Saving Value: |r|({type(value)}) {e}|e| {value}', colored = True)
            return None
        
    async def _aset_one(
        self, 
        key: str, 
        value: Any, 
        ex: Optional[int] = None, 
        tag: Optional[str] = None, 
        _raw: Optional[bool] = None, 
        **kwargs
    ):
        """
        [Async] Saves a Value to the DB
        """
        try:
            value = await self.aencode_value(value, _raw = _raw, **kwargs)
        except Exception as e:
            logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {value}', colored = True)
            return None
        try:
            return await self.setter(key, value, ex = ex, tag = tag, is_async = True)
        except Exception as e:
            logger.info(f'Error Saving Value: |r|({type(value)}) {e}|e| {value}', colored = True)
            return None


    """
    Encoding and Decoding Methods
    """

    # def encode_value(self, value: t.Union[t.Any, SchemaType], _raw: t.Optional[bool] = None, **kwargs) -> t.Union[str, bytes]:
    #     """
    #     Encodes a Value
    #     """
    #     return value if _raw else self.serializer.encode(value, **kwargs)
    
    # async def aencode_value(self, value: t.Union[t.Any, SchemaType], _raw: Optional[bool] = None,  **kwargs) -> t.Union[str, bytes]:
    #     """
    #     Encodes a Value
    #     """
    #     return value if _raw else await self.serializer.aencode(value, **kwargs)

    # def decode_value(self, value: t.Union[str, bytes], _raw: t.Optional[bool] = None, **kwargs) -> t.Any:
    #     """
    #     Decodes a Value
    #     """
    #     return value if _raw else self.serializer.decode(value, **kwargs)
    
    # async def adecode_value(self, value: t.Union[str, bytes], _raw: t.Optional[bool] = None, **kwargs) -> t.Any:
    #     """
    #     Decodes a Value
    #     """
    #     return value if _raw else await self.serializer.adecode(value, **kwargs)
    

    def _decode_kv_data(self, data: t.Dict[str, t.Any], _raw: Optional[bool] = None, skip_on_errors: Optional[bool] = True, **kwargs) -> t.Dict[str, t.Any]:
        """
        Decodes the data
        """
        data_keys = list(data.keys())
        for key in data_keys:
            try:
                data[key] = self.decode_value(data[key], _raw = _raw, **kwargs)
            except Exception as e:
                if skip_on_errors: 
                    data.pop(key)
                    continue
                logger.info(f'Error Decoding Key {key} : |r|({type(data[key])}) {e}|e| {data[key]}', colored = True)
                raise e
        return data

    async def _adecode_kv_data(self, data: t.Dict[str, t.Any], _raw: Optional[bool] = None, skip_on_errors: Optional[bool] = True, **kwargs) -> t.Dict[str, t.Any]:
        """
        [Async] Decodes the data
        """
        data_keys = list(data.keys())
        for key in data_keys:
            try:
                data[key] = await self.adecode_value(data[key], _raw = _raw, **kwargs)
            except Exception as e:
                if skip_on_errors: 
                    data.pop(key)
                    continue
                logger.info(f'Error Decoding Key {key} : |r|({type(data[key])}) {e}|e| {data[key]}', colored = True)
                raise e
        return data
    
    def _decode_values(self, values: t.List[t.Any], _raw: Optional[bool] = None, skip_on_errors: Optional[bool] = True, **kwargs) -> t.List[t.Any]:
        """
        Decodes the values
        """
        invalid_idx = []
        for n, value in enumerate(values):
            try:
                values[n] = self.decode_value(value, _raw = _raw, **kwargs)
            except Exception as e:
                if skip_on_errors: 
                    invalid_idx.append(n)
                    # values.pop(n)
                    continue
                logger.info(f'Error Decoding Value {n} : |r|({type(value)}) {e}|e| {value}', colored = True)
                raise e
        if invalid_idx:
            values = [values[i] for i in range(len(values)) if i not in invalid_idx]
        return values

    async def _adecode_values(self, values: t.List[t.Any], _raw: Optional[bool] = None, skip_on_errors: Optional[bool] = True, **kwargs) -> t.List[t.Any]:
        """
        [Async] Decodes the values
        """
        invalid_idx = []
        for n, value in enumerate(values):
            try:
                values[n] = await self.adecode_value(value, _raw = _raw, **kwargs)
            except Exception as e:
                if skip_on_errors: 
                    invalid_idx.append(n)
                    # values.pop(n)
                    continue
                logger.info(f'Error Decoding Value {n} : |r|({type(value)}) {e}|e| {value}', colored = True)
                raise e
        if invalid_idx:
            values = [values[i] for i in range(len(values)) if i not in invalid_idx]
        return values

    """
    Implemented Methods
    """

    def get_key(self, key: str) -> str:
        """
        Gets a Key
        """
        # Since we use a table, we just return the key
        return key
    
    def get(self, key: str, default: Optional[Any] = None, _raw: Optional[bool] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from SQLite
        """
        return self._get_one(key, default = default, _raw = _raw, **kwargs)
    
    async def aget(self, key: str, default: Optional[Any] = None, _raw: Optional[bool] = None, **kwargs) -> Optional[Any]:
        """
        [Async] Gets a Value from SQLite
        """
        return await self._aget_one(key, default = default, _raw = _raw, **kwargs)
    
    def set(self, key: str, value: Any, ex: Optional[int] = None, tag: Optional[str] = None, _raw: Optional[bool] = None, **kwargs) -> None:
        """
        Sets a Value in SQLite
        """
        return self._set_one(key, value, ex = ex, tag = tag, _raw = _raw, **kwargs)
    
    async def aset(self, key: str, value: Any, ex: Optional[int] = None, tag: Optional[str] = None, _raw: Optional[bool] = None, **kwargs) -> None:
        """
        [Async] Sets a Value in SQLite
        """
        return await self._aset_one(key, value, ex = ex, tag = tag, _raw = _raw, **kwargs)
    

    def set_batch(self, data: Dict[str, Any], ex: Optional[int] = None, tag: t.Optional[str] = None, _raw: Optional[bool] = None, skip_on_errors: t.Optional[bool] = True, **kwargs) -> int:
        """
        Saves a Value to the Object Store
        """
        data_keys = list(data.keys())
        for key in data_keys:
            try:
                data[key] = self.encode_value(data[key], _raw = _raw, **kwargs)
            except Exception as e:
                value = data.pop(key)
                logger.info(f'Error Encoding Key {key} : |r|({type(value)}) {e}|e| {value}', colored = True)
                if skip_on_errors: continue
                raise e
        ex = ex or self.expiration
        self.db.batch_set(data, expire = ex, tag = tag, **kwargs)
        return len(data)

    async def aset_batch(self, data: Dict[str, Any], ex: Optional[int] = None, tag: t.Optional[str] = None, _raw: Optional[bool] = None, skip_on_errors: t.Optional[bool] = True, **kwargs) -> int:
        """
        [Async] Saves a Value to the Object Store
        """
        data_keys = list(data.keys())
        for key in data_keys:
            try:
                data[key] = await self.aencode_value(data[key], _raw = _raw, **kwargs)
            except Exception as e:
                value = data.pop(key)
                logger.info(f'Error Encoding Key {key} : |r|({type(value)}) {e}|e| {value}', colored = True)
                if skip_on_errors: continue
                raise e
        ex = ex or self.expiration
        await self.db.abatch_set(data, expire = ex, tag = tag, **kwargs)
        return len(data)


        
    def delete(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from SQLite
        """
        return self.deleter(key, **kwargs)
    
    async def adelete(self, key: str, **kwargs) -> None:
        """
        [Async] Deletes a Value from SQLite
        """
        return await self.deleters(key, is_async = True, **kwargs)

    def get_keys(
        self, 
        pattern: str, 
        exclude_base_key: Optional[bool] = None, 
        order: Optional[str] = 'ASC',
        limit: Optional[int] = None,
        **kwargs
    ) -> List[str]:
        """
        Returns the Keys within the DB
        """
        if '*' in pattern: pattern = pattern.replace('*', '%')
        return self.db.fetch_keys(pattern = pattern, include_rowid = False, order = order, limit = limit, **kwargs)
    
    async def aget_keys(
        self, 
        pattern: str, 
        exclude_base_key: Optional[bool] = None, 
        order: Optional[str] = 'ASC',
        limit: Optional[int] = None,
        **kwargs
    ) -> List[str]:
        """
        [Async] Returns the Keys within the DB
        """
        if '*' in pattern: pattern = pattern.replace('*', '%')
        return await self.db.afetch_keys(pattern = pattern, include_rowid = False, order = order, limit = limit, **kwargs)
    
    def get_all_keys(
        self, 
        *args,
        **kwargs
    ) -> List[str]:
        """
        Returns all the Keys in the DB
        """
        return self.db.fetch_keys(pattern = None, **kwargs)

    async def aget_all_keys(
        self, 
        *args,
        **kwargs
    ) -> List[str]:
        """
        [Async] Returns all the Keys in the DB
        """
        return await self.db.afetch_keys(pattern = None, **kwargs)

    def get_all_data(self, exclude_base_key: Optional[bool] = False, limit: t.Optional[int] = None, _raw: Optional[bool] = None, skip_on_errors: t.Optional[bool] = True, **kwargs) -> Dict[str, t.Any]:
        """
        Loads all the Data
        """
        
        data = self.db.fetch_kv_data(limit = limit, **kwargs)
        return self._decode_kv_data(data, _raw = _raw, skip_on_errors = skip_on_errors, **kwargs)
        

    async def aget_all_data(self, exclude_base_key: Optional[bool] = False, limit: t.Optional[int] = None, _raw: Optional[bool] = None, skip_on_errors: t.Optional[bool] = True, **kwargs) -> Dict[str, t.Any]:
        """
        [Async] Loads all the Data
        """
        data = await self.db.afetch_kv_data(limit = limit, **kwargs)
        return await self._adecode_kv_data(data, _raw = _raw, skip_on_errors = skip_on_errors, **kwargs)


    def get_all_values(self, limit: t.Optional[int] = None, _raw: Optional[bool] = None, skip_on_errors: t.Optional[bool] = True, **kwargs) -> List[t.Any]:
        """
        Returns all the Values in the DB
        """
        values = self.db.fetch_values(limit = limit, **kwargs)
        return self._decode_values(values, _raw = _raw, skip_on_errors = skip_on_errors, **kwargs)
        
    async def aget_all_values(self, limit: t.Optional[int] = None, _raw: Optional[bool] = None, skip_on_errors: t.Optional[bool] = True, **kwargs) -> List[t.Any]:
        """
        [Async] Returns all the Values in the DB
        """
        values = await self.db.afetch_values(limit = limit, **kwargs)
        return await self._adecode_values(values, _raw = _raw, skip_on_errors = skip_on_errors, **kwargs)


    def length(self, **kwargs) -> int:
        """
        Returns the Length of the DB
        """
        return self.db.length(**kwargs)
    
    async def alength(self, **kwargs) -> int:
        """
        [Async] Returns the Length of the DB
        """
        return await self.db.alength(**kwargs)
    

    def __len__(self):
        """
        Returns the Length of the Cache
        """
        return self.length()
    
    def clear(self, **kwargs) -> None:
        """
        Clears the DB
        """
        return self.db.clear(**kwargs)
    
    async def aclear(self, **kwargs) -> None:
        """
        [Async] Clears the DB
        """
        return await self.db.aclear(**kwargs)

    # def iterate(self, **kwargs) -> t.Iterable[t.Any]:
    #     """
    #     Iterates over the Cache
    #     """
    #     return self.db.iterate(**kwargs) 
    
    def contains(self, key: str, **kwargs) -> bool:
        """
        Returns whether the Key is in the DB
        """
        return self.db.contains(key, **kwargs)
    
    async def acontains(self, key: str, **kwargs) -> bool:
        """
        [Async] Returns whether the Key is in the DB
        """
        return await self.db.acontains(key, **kwargs)
    
    def expire(self, key: str, ex: int, **kwargs) -> None:
        """
        Expires a Key
        """
        return self.db._set_key_expiration_(key, ex, **kwargs)
    
    async def aexpire(self, key: str, ex: int, **kwargs) -> None:
        """
        [Async] Expires a Key
        """
        return await self.db._aset_key_expiration_(key, ex, **kwargs)

    def update(self, data: t.Dict[str, t.Any], ex: t.Optional[int] = None, tag: t.Optional[str] = None, retry: t.Optional[bool] = None, **kwargs):
        """
        Updates the Cache
        """
        return self.set_batch(data, ex = ex, tag = tag, retry = retry)

    async def aupdate(self, data: t.Dict[str, t.Any], ex: t.Optional[int] = None, tag: t.Optional[str] = None, retry: t.Optional[bool] = None, **kwargs):
        """
        [Async] Updates the Cache
        """
        return await self.aset_batch(data, ex = ex, tag = tag, retry = retry)

    def select(
        self, 
        *tags: str, 
        limit: t.Optional[int] = None, 
        order: t.Optional[t.Literal['ASC', 'DESC']] = 'ASC',
        order_by: t.Optional[str] = 'rowid',
        include_meta: bool = False, 
        _raw: t.Optional[bool] = None,
        skip_on_errors: t.Optional[bool] = True,
        **kwargs
    ) -> t.Union[t.Dict[str, t.Any], t.Tuple[t.Dict[str, t.Any], t.Dict[str, t.Any]]]:
        """
        Select all items with the given tags

        :param tags: tags to select
        :param limit: limit the number of items to return
            (default None, no limit)
        :param order: order to return the items
            (default 'ASC', ascending)
        :param include_meta: if True, return a dict of metadata
            (default False)
        :return: dict of key/value pairs or tuple of (key, value) pairs if include_meta is True
        """
        data = self.db.select_tags(*tags, limit = limit, order = order, order_by = order_by, include_meta = include_meta, **kwargs)
        if include_meta: 
            data, meta = data
        data = self._decode_kv_data(data, _raw = _raw, skip_on_errors = skip_on_errors, **kwargs)
        return (data, meta) if include_meta else data
    
    
    async def aselect(
        self, 
        *tags: str, 
        limit: t.Optional[int] = None, 
        order: t.Optional[t.Literal['ASC', 'DESC']] = 'ASC',
        order_by: t.Optional[str] = 'rowid',
        include_meta: bool = False, 
        _raw: t.Optional[bool] = None,
        skip_on_errors: t.Optional[bool] = True,
        **kwargs
    ) -> t.Union[t.Dict[str, t.Any], t.Tuple[t.Dict[str, t.Any], t.Dict[str, t.Any]]]:
        """
        [Async] Select all items with the given tags

        :param tags: tags to select
        :param limit: limit the number of items to return
            (default None, no limit)
        :param order: order to return the items
            (default 'ASC', ascending)
        :param include_meta: if True, return a dict of metadata
            (default False)
        :return: dict of key/value pairs or tuple of (key, value) pairs if include_meta is True
        """
        data = await self.db.aselect_tags(*tags, limit = limit, order = order, order_by = order_by, include_meta = include_meta, **kwargs)
        if include_meta: 
            data, meta = data
        data = await self._adecode_kv_data(data, _raw = _raw, skip_on_errors = skip_on_errors, **kwargs)
        return (data, meta) if include_meta else data

    def __repr__(self):
        """
        Returns the Representation of the Cache
        """
        return f"<{self.__class__.__name__} num_keys={len(self)}, table={self.db.table}, serializer={self.serializer.name}>"