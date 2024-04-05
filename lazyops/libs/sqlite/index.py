from __future__ import annotations

import abc
import atexit
import sqlite3
import pathlib
import filelock
import contextlib
from pydantic import BaseModel, Field, model_validator, model_serializer
from lazyops.imports._aiosqlite import resolve_aiosqlite
from lazyops.utils.lazy import lazy_import
from lazyops.utils import logger, Timer
from typing import Optional, List, Dict, Any, Union, Type, Tuple, TypeVar, AsyncGenerator, overload, TYPE_CHECKING

if TYPE_CHECKING:
    
    # import aiosqlite
    from lazyops.libs import aiosqlite
    from .mixins import SQLResultT, SQLiteModelMixin
    

    # SchemaT = Union[Type[SQLResultT], str]
    # SchemaListT = List[Union[Type[SQLResultT], str]]

    SchemaT = Union[Type[SQLiteModelMixin], str]
    SchemaListT = List[Union[Type[SQLiteModelMixin], str]]

    ModelT = TypeVar('ModelT', bound = SQLiteModelMixin)

    # SchemaTypeT = TypeVar('SchemaTypeT', bound = SQLiteModelMixin)

    # SchemaTypeT = SQLResultT



class SQLiteIndex(abc.ABC):
    """
    The SQLite Index

    This is a base class for all SQLite Indexes. It provides common functionality for indexes, such as creating and updating indexes, and searching for items.

    Attributes:
        sql_data_path (pathlib.Path): The path to the SQLite database file.
        tablename (str): The name of the table in the database.
        schema (str): The schema of the table.
        schemas (Dict[str, Union[str, List[str], Dict[str, str]]]): The schemas of the table.
        ephemeral (bool): Whether the index is ephemeral or not.
        force_reindex (bool): Whether to force reindexing the index.
        auto_set_schema (bool): Whether to automatically set the schema of the index.
        enable_internal_index (bool): Whether to enable the internal index.
    """

    sql_data_path: Optional[pathlib.Path] = None

    # Can define the schema to use as a single type or multiple types
    tablename: Optional[str] = None
    schema: Optional['SchemaT'] = None
    schemas: Optional[Dict[str, Union['SchemaT', 'SchemaListT']]] = None

    ephemeral: Optional[bool] = False
    force_reindex: Optional[bool] = False
    auto_set_schema: Optional[bool] = False
    enable_internal_index: Optional[bool] = False

    def __init__(
        self,
        sql_data_path: Optional[pathlib.Path] = None,
        tablename: Optional[str] = None,
        schema: Optional['SchemaT'] = None,
        schemas: Optional[Dict[str, Union['SchemaT', 'SchemaListT']]] = None,
        ephemeral: Optional[bool] = None,
        force_reindex: Optional[bool] = None,
        auto_set_schema: Optional[bool] = None,
        enable_internal_index: Optional[bool] = None,
        **kwargs,
    ):
        """
        Initializes the SQLite Index
        """
        self._initialized: bool = False
        super().__init__(**kwargs)
        self.cls_init(
            sql_data_path = sql_data_path, 
            tablename = tablename, 
            schema = schema, 
            schemas = schemas, 
            ephemeral = ephemeral, 
            force_reindex = force_reindex, 
            auto_set_schema = auto_set_schema,
            enable_internal_index = enable_internal_index,
            **kwargs
        )

    def cls_init(
        self, 
        sql_data_path: Optional[pathlib.Path] = None,
        tablename: Optional[str] = None,
        schema: Optional['SchemaT'] = None,
        schemas: Optional[Dict[str, Union['SchemaT', 'SchemaListT']]] = None,
        ephemeral: Optional[bool] = None,
        force_reindex: Optional[bool] = None,
        auto_set_schema: Optional[bool] = None,
        enable_internal_index: Optional[bool] = None,
        **kwargs
    ):  # sourcery skip: low-code-quality
        """
        For compatibility with `BaseGlobalClient`
        """
        if self._initialized: return
        if sql_data_path is not None: self.sql_data_path = sql_data_path
        if tablename is not None: self.tablename = tablename
        if schema is not None: self.schema = schema
        if schemas is not None: self.schemas = schemas
        if enable_internal_index is not None: self.enable_internal_index = enable_internal_index
        self.schemas = self.schemas or {}
        self.internal_index: Dict[str, Dict[str, 'SQLResultT']] = {}
        # self.schemas = schemas if schemas is not None else {}
        if self.tablename and self.schema:
            self.schemas[self.tablename] = self.schema
        
        if ephemeral is not None: self.ephemeral = ephemeral
        if force_reindex is not None: self.force_reindex = force_reindex
        if auto_set_schema is not None: self.auto_set_schema = auto_set_schema
        if self.schema is not None:
            if isinstance(self.schema, str): self.schema = lazy_import(self.schema)

        if self.schemas is not None:
            for key, value in self.schemas.items():
                if isinstance(value, list):
                    s_values = []
                    for v in value:
                        if isinstance(v, str): v = lazy_import(v)
                        s_values.append(v)
                    value = s_values
                    self.schemas[key] = s_values
                elif isinstance(value, str): self.schemas[key] = lazy_import(value)
        

        self.default_tablename = self.tablename or list(self.schemas.keys())[0]
        self._conn: Optional['sqlite3.Connection'] = None
        self._aconn: Optional['aiosqlite.Connection'] = None

        self._conn_initialized: Optional[bool] = None
        self._aconn_initialized: Optional[bool] = None

        self._schemas_initialized: Optional[bool] = None
        self._sql_lock: Optional[filelock.SoftFileLock] = None
        self.sql_lock_path: Optional[pathlib.Path] = None
        if self.sql_data_path: 
            if self.sql_data_path.is_dir() and self.tablename:
                self.sql_data_path.mkdir(parents = True, exist_ok = True)
                self.sql_data_path = self.sql_data_path.joinpath(f'{self.tablename}.db')
            self.sql_lock_path = self.sql_data_path.with_suffix('.lock')
        self._initialized = True
    
    @property
    def sql_lock(self) -> filelock.SoftFileLock:
        """
        Returns the SQL Lock
        """
        if self._sql_lock is None:
            self._sql_lock = filelock.SoftFileLock(
                self.sql_lock_path.as_posix(),
                timeout = 0,
                thread_local = False,
            )
            if self.ephemeral: atexit.register(self.cleanup_on_exit)
            atexit.register(self.save_on_exit)
        return self._sql_lock

    def save_on_exit(self):
        """
        Saves the index on exit
        """
        self.conn.close()
        # self.conn.backup()


    def cleanup_on_exit(self):
        """
        Cleans up the index on exit
        """
        if self.sql_lock_path.exists():
            logger.info(f'Removing SQLite Lock: {self.sql_lock_path}', prefix = '|g|DB|e|', colored = True)
            try:
                self.sql_lock.release()
                self.sql_lock_path.unlink()
            except Exception as e:
                logger.error(f'Error cleaning up SQLite Lock: {e}', prefix = '|g|DB|e|', colored = True)
        
        if self.sql_data_path.exists():
            logger.info(f'Removing SQLite Data: {self.sql_data_path}', prefix = '|g|DB|e|', colored = True)
            try:
                self.sql_data_path.unlink()
            except Exception as e:
                logger.error(f'Error cleaning up SQLite Data: {e}', prefix = '|g|DB|e|', colored = True)
        
    def get_index_schemas(self) -> Dict[str, Union[Type['SQLiteModelMixin'], List[Type['SQLiteModelMixin']]]]:
        """
        Gets the index schemas
        """
        return (
            self.schemas or 
            {
                self.tablename: self.schema,
            }
        )

    def conn_prehook(self, **kwargs):
        """
        This is called before the connection is created
        """
        pass


    def conn_posthook(self, **kwargs):
        """
        This is called after the connection is created
        """
        pass

    async def aconn_prehook(self, **kwargs):
        """
        This is called before the async connection is created
        """
        pass

    async def aconn_posthook(self, **kwargs):
        """
        This is called after the async connection is created
        """
        pass

    def init_schemas(self, conn: 'sqlite3.Connection', exists: Optional[bool] = None) -> None:
        """
        Initializes the schemas
        """
        if exists is None: exists = self.sql_data_path.exists()
        if not self.sql_lock.is_locked:
            with self.sql_lock.acquire(10.0):
                index_schemas = self.get_index_schemas()
                for tablename, schema in index_schemas.items():
                    if not isinstance(schema, list): schema = [schema]
                    for s in schema:
                        s.execute_sql_init(
                            conn, 
                            tablename = tablename, 
                            skip_index = (exists and not self.force_reindex), 
                            auto_set = self.auto_set_schema
                        )
        self._schemas_initialized = True


    def init_db_schemas(self) -> None:
        """
        Initializes the database schemas
        """
        if self._schemas_initialized: return
        self.conn_prehook()
        conn = sqlite3.connect(self.sql_data_path.as_posix(), check_same_thread = False)
        self.init_schemas(conn)
        self.conn_posthook()


    @property
    def conn(self) -> 'sqlite3.Connection':
        """
        Returns the connection
        """
        if self._conn is None:
            self.conn_prehook()
            exists = self.sql_data_path.exists()
            import sqlite3
            self._conn = sqlite3.connect(self.sql_data_path.as_posix(), check_same_thread = False)
            if not self._schemas_initialized:
                self.init_schemas(self._conn, exists = exists)
        return self._conn
    
    async def ainit_schemas(self, conn: 'aiosqlite.Connection') -> None:
        """
        Initializes the schemas
        """
        index_schemas = self.get_index_schemas()
        exists = self.sql_data_path.exists()
        with self.sql_lock.acquire(10.0):
            for tablename, schema in index_schemas.items():
                if not isinstance(schema, list): schema = [schema]
                for s in schema:
                    await s.aexecute_sql_init(
                        conn, 
                        tablename = tablename, 
                        skip_index = (exists and not self.force_reindex), 
                        auto_set = self.auto_set_schema
                    )
        # logger.info(f'Completed SQL initialization in {t.total_s}')
        self._schemas_initialized = True
    
    async def ainit_db_schemas(self):
        """
        Initializes the database schemas
        """
        if self._schemas_initialized: return
        from lazyops.libs import aiosqlite
        await self.aconn_prehook()
        conn = await aiosqlite.connect(self.sql_data_path.as_posix())
        await self.ainit_schemas(conn)


    @contextlib.asynccontextmanager
    async def aconn(self) -> AsyncGenerator['aiosqlite.Connection', None]:
        """
        Returns the async connection
        """
        if self._aconn is None:
            from lazyops.libs import aiosqlite
            await self.aconn_prehook()
            self._aconn = await aiosqlite.connect(self.sql_data_path.as_posix(), limit = 10)
            if not self._schemas_initialized:
                await self.ainit_schemas(self._aconn)
        try:
            yield self._aconn
        except Exception as e:
            logger.trace('Error in async connection', e)
            raise e
        finally:
            await self.aconn_posthook()

        # resolve_aiosqlite(True)
        # import aiosqlite
        # await self.aconn_prehook()
        # async with aiosqlite.connect(self.sql_data_path.as_posix()) as conn:
        #     if not self._aconn_initialized:
        #         await self.ainit_schemas(conn)
        #     try:
        #         yield conn
        #     except Exception as e:
        #         logger.trace('Error in async connection', e)
        #     finally:
        #         await self.aconn_posthook()
        # from lazyops.libs import aiosqlite
        # await self.aconn_prehook()
        # conn = await aiosqlite.connect(self.sql_data_path.as_posix())
        # if not self._aconn_initialized:
        #     await self.ainit_schemas(conn)
        # try:
        #     yield conn
        # except Exception as e:
        #     logger.trace('Error in async connection', e)
        # finally:
        #     await self.aconn_posthook()




    
    def get_schema(
        self,
        schema_name: Optional[str] = None,
        tablename: Optional[str] = None,
    ) -> 'SchemaT':
        """
        Gets the schema by name
        """
        if tablename is None: tablename = self.tablename
        schemas = self.schemas[tablename]
        if not isinstance(schemas, list): return schemas
        if schema_name is None: return schemas[0]
        for schema in schemas:
            if schema_name in schema.__name__:
                return schema
        raise ValueError(f'Schema {schema_name} not found in {tablename}')
    
    def format_query(
        self,
        query: Optional[str] = None,
        **kwargs,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Helper Function to Preformat the query
        """
        return query, kwargs

    @overload
    def search_one(
        self,
        query: Optional[str] = None,
        skip: Optional[int] = None,
        tablename: Optional[str] = None,
        schema_name: Optional[str] = None,
        **kwargs,
    ) -> 'SQLiteModelMixin':
        """
        Executes the sql search for one item
        """
        ...

    @overload
    def search_one(
        self,
        query: Optional[str] = None,
        skip: Optional[int] = None,
        return_id_only: Optional[bool] = True,
        tablename: Optional[str] = None,
        schema_name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Returns the id of the first item that matches the query
        """
        ...


    def search_one(
        self,
        query: Optional[str] = None,
        skip: Optional[int] = None,
        return_id_only: Optional[bool] = None,
        return_fields: Optional[List[str]] = None,
        tablename: Optional[str] = None,
        schema_name: Optional[str] = None,
        cast_to_object: Optional[bool] = None,
        **kwargs,
    ) -> Optional[Union['SQLResultT', str]]:
        """
        Executes the sql search for one item
        """
        tablename = tablename or self.default_tablename
        schema = self.get_schema(tablename = tablename, schema_name = schema_name)
        if self.enable_internal_index and (return_id_only is None and return_fields is None) and self.internal_index.get(tablename):
            return_id_only = True
            if cast_to_object is None: cast_to_object = True
        query, kwargs = self.format_query(query, **kwargs)
        result = schema.search_one(
            conn = self.conn,
            query = query, 
            skip = skip, 
            return_id_only = return_id_only, 
            return_fields = return_fields,
            tablename = tablename,
            **kwargs
        )
        if self.enable_internal_index and result and cast_to_object:
            return self.populate_item_from_index(tablename, result)
        return result

    async def asearch_one(
        self,
        query: Optional[str] = None,
        skip: Optional[int] = None,
        return_id_only: Optional[bool] = None,
        return_fields: Optional[List[str]] = None,
        tablename: Optional[str] = None,
        schema_name: Optional[str] = None,
        cast_to_object: Optional[bool] = None,
        **kwargs,
    ) -> Optional[Union['SQLiteModelMixin', str]]:
        """
        Executes the sql search for one item
        """
        tablename = tablename or self.default_tablename
        schema = self.get_schema(tablename = tablename, schema_name = schema_name)
        if self.enable_internal_index and (return_id_only is None and return_fields is None) and self.internal_index.get(tablename):
            return_id_only = True
            cast_to_object = True
        query, kwargs = self.format_query(query, **kwargs)
        async with self.aconn() as conn:
            result = await schema.asearch_one(
                conn = conn,
                query = query, 
                skip = skip, 
                return_id_only = return_id_only, 
                return_fields = return_fields,
                tablename = tablename,
                **kwargs
            )
        if self.enable_internal_index and result and cast_to_object:
            return self.populate_item_from_index(tablename, result)
        return result

    def search_many(
        self,
        query: Optional[str] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        return_id_only: Optional[bool] = None,
        return_fields: Optional[List[str]] = None,
        tablename: Optional[str] = None,
        schema_name: Optional[str] = None,
        cast_to_object: Optional[bool] = None,
        **kwargs,
    ) -> List[Union['SQLiteModelMixin', str]]:
        """
        Executes the sql search for many items
        """
        tablename = tablename or self.default_tablename
        schema = self.get_schema(tablename = tablename, schema_name = schema_name)
        if self.enable_internal_index and (return_id_only is None and return_fields is None) and self.internal_index.get(tablename):
            return_id_only = True
            cast_to_object = True
        query, kwargs = self.format_query(query, **kwargs)
        results = schema.search_many(
            conn = self.conn,
            query = query, 
            limit = limit, 
            skip = skip, 
            return_id_only = return_id_only, 
            return_fields = return_fields,
            tablename = tablename,
            **kwargs
        )
        if self.enable_internal_index and results and cast_to_object:
            return [self.populate_item_from_index(tablename, result) for result in results]
        return results

    async def asearch_many(
        self,
        query: Optional[str] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        return_id_only: Optional[bool] = None,
        return_fields: Optional[List[str]] = None,
        tablename: Optional[str] = None,
        schema_name: Optional[str] = None,
        cast_to_object: Optional[bool] = None,
        **kwargs,
    ) -> List[Union['SQLiteModelMixin', str]]:
        """
        Executes the sql search for many items
        """
        tablename = tablename or self.default_tablename
        schema = self.get_schema(tablename = tablename, schema_name = schema_name)
        if self.enable_internal_index and (return_id_only is None and return_fields is None) and self.internal_index.get(tablename):
            return_id_only = True
            cast_to_object = True
        query, kwargs = self.format_query(query, **kwargs)
        async with self.aconn() as conn:
            try:
                results = await schema.asearch_many(
                    conn = conn,
                    query = query, 
                    limit = limit, 
                    skip = skip, 
                    return_id_only = return_id_only, 
                    return_fields = return_fields,
                    tablename = tablename,
                    **kwargs
                )
            except Exception as e:
                logger.error(f'[{tablename}] Error Searching: {e}, {query}, {kwargs}')
                raise e
            
        if self.enable_internal_index and results and cast_to_object:
            return [self.populate_item_from_index(tablename, result) for result in results]
        return results
        

    def delete(
        self,
        item: 'SQLiteModelMixin',
        **kwargs,
    ) -> None:
        """
        Deletes the object from the database
        """
        item.sql_delete(self.conn)
        self.unindex_item(item)


    async def adelete(
        self,
        item: 'SQLiteModelMixin',
        **kwargs,
    ) -> None:
        """
        Deletes the object from the database
        """
        async with self.aconn() as conn:
            await item.asql_delete(conn)
        self.unindex_item(item)
    
    def unindex_item(
        self,
        item: 'SQLiteModelMixin',
        **kwargs,
    ) -> None:
        """
        Unindexes the item
        """
        if self.enable_internal_index:
            if item.sql_tablename in self.internal_index:
                del self.internal_index[item.sql_tablename][item.sql_pkey]

    def index_item(
        self,
        item: 'SQLiteModelMixin',
        **kwargs,
    ) -> None:
        """
        Indexes the item
        """
        if self.enable_internal_index:
            if item.sql_tablename not in self.internal_index:
                self.internal_index[item.sql_tablename] = {}
            self.internal_index[item.sql_tablename][item.sql_pkey] = item
    
    def populate_item_from_index(
        self,
        tablename: str,
        pkey: Union[str, int, Dict[str, Any], List[Union[str, int]]],
        **kwargs,
    ) -> Optional['SQLiteModelMixin']:
        """
        Populates the item from the index
        """
        if tablename not in self.internal_index: return None
        if isinstance(pkey, dict): pkey = list(pkey.values())
        if not isinstance(pkey, list): pkey = [pkey]
        return next(
            (
                self.internal_index[tablename][pk]
                for pk in pkey
                if pk is not None and pk in self.internal_index[tablename]
            ),
            None,
        )
        # if pkey not in self.internal_index[tablename]: return None
        # return self.internal_index[tablename][pkey]
    
    def index_items(
        self,
        items: List['SQLiteModelMixin'],
        **kwargs,
    ) -> None:
        """
        Indexes the items
        """
        if self.enable_internal_index:
            for item in items:
                self.index_item(item)
    
    def set(
        self,
        item: 'SQLiteModelMixin',
        skip_set: Optional[bool] = None,
        skip_index: Optional[bool] = None,
        **kwargs,
    ) -> None:
        """
        Saves the object to the database
        """
        if not skip_set: item.sql_set(self.conn)
        if not skip_index: self.index_item(item)
        # item.sql_set(self.conn)
        # self.index_item(item)
        
    async def aset(
        self,
        item: 'SQLiteModelMixin',
        skip_set: Optional[bool] = None,
        skip_index: Optional[bool] = None,
        **kwargs,
    ):
        """
        Saves the object to the database
        """
        async with self.aconn() as conn:
            if not skip_set: await item.asql_set(conn)
            if not skip_index: self.index_item(item)
            # await item.asql_set(conn)
            # self.index_item(item)

    def set_many(
        self,
        items: List['SQLiteModelMixin'],
        skip_index: Optional[bool] = None,
        **kwargs,
    ):
        """
        Saves the objects to the database
        """
        item_cls = items[0].__class__
        item_cls.sql_set_many(self.conn, items = items, **kwargs)
        if not skip_index: self.index_items(items)

    async def aset_many(
        self,
        items: List['SQLiteModelMixin'],
        skip_index: Optional[bool] = None,
        **kwargs,
    ):
        """
        Saves the objects to the database
        """
        item_cls = items[0].__class__
        async with self.aconn() as conn:
            await item_cls.asql_set_many(conn, items = items, **kwargs)
        if not skip_index: self.index_items(items)
        
    def reindex_from_internal_index(
        self,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        **kwargs,
    ) -> int:
        """
        Saves all items from the internal index to the DB
        """
        include = include or []
        exclude = exclude or []
        count = 0
        
        for tablename, index in self.internal_index.items():
            if (not include or tablename in include) and (not exclude or tablename not in exclude):
                items = list(index.values())
                if not items: continue
                self.set_many(items, skip_index = True, **kwargs)
                count += len(items)
        return count
    
    async def areindex_from_internal_index(
        self,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        **kwargs,
    ) -> int:
        """
        Saves all items from the internal index to the DB
        """
        include = include or []
        exclude = exclude or []
        count = 0
        t = Timer()
        for tablename, index in self.internal_index.items():
            if (not include or tablename in include) and (not exclude or tablename not in exclude):
                items = list(index.values())
                if not items: continue
                await self.aset_many(items, skip_index = True, **kwargs)
                count += len(items)
        logger.info(f'Completed Reindexing {count} items in {t.duration_s}')
        return count
        



    def __getitem__(self, name: str) -> Union['SQLiteModelMixin', Any]:
        """
        Gets the item from the db
        """
        if ':' in name: tablename, name = name.split(':', 1)
        else: tablename = self.default_tablename
        return self.search_one(tablename = tablename, query = name)
    

    def __add__(self, item: 'SQLiteModelMixin') -> 'SQLiteModelMixin':
        """
        Adds the item to the database
        """
        self.set(item)
        return item
    
    def __sub__(self, item: 'SQLiteModelMixin') -> 'SQLiteModelMixin':
        """
        Removes the item from the database
        """
        item.sql_delete(self.conn)
        return item
    
    def __iadd__(self, item: 'SQLiteModelMixin') -> 'SQLiteModelMixin':
        """
        Adds the item to the database
        """
        self.set(item)
        return item
    
    def __isub__(self, item: 'SQLiteModelMixin') -> 'SQLiteModelMixin':
        """
        Removes the item from the database
        """
        self.delete(item)
        return item
    

