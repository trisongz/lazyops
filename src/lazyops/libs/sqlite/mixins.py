from __future__ import annotations

import abc
import datetime
import contextlib
from pydantic import BaseModel, model_validator, Field, PrivateAttr, validator
from lazyops.utils.logs import logger
from .static import SqliteTemplates
from .registry import get_or_register_sqlite_schema, get_or_register_sqlite_connection, retrieve_sqlite_model_schema, get_sqlite_model_pkey, get_or_register_sqlite_tablename, SQLiteModelConfig, get_sqlite_model_config
from .utils import normalize_sql_text
from typing import Optional, List, Tuple, Dict, Union, TypeVar, Any, overload, TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    # import aiosqlite
    from lazyops.libs import aiosqlite

    from pydantic.main import IncEx

    SQLResultT = TypeVar('SQLResultT', bound = 'SQLiteModelMixin')


class SQLiteModelMixin(BaseModel, abc.ABC):
    """
    The SQLite Model Mixin

    This mixin is used to create a SQLite model that can be used with SQLite. 
    
    It uses certain `Field` parameters to define the schema of the model.
    - `sql_pkey`: The primary key field of the model
    - `exclude`: Will exclude the field from the model
    - `include_sql`: If any of the fields contain this, it will ONLY select the fields that contain `include_sql`
    - `exclude_sql`: Will exclude the field from the SQLite model
    - `sql_search_precision`: The search precision of the field
    """

    # sql_config: Optional[SQLiteModelConfig] = Field(None, exclude = True, exclude_sql = True)
    _sql_config: Optional[SQLiteModelConfig] = PrivateAttr(None)

    @property
    def sql_config(self) -> SQLiteModelConfig:
        """
        Returns the SQLite Model Config
        """
        if self._sql_config is None:
            self._sql_config = get_sqlite_model_config(self.__class__)
        return self._sql_config
    
    @property
    def sql_pkey_column(self) -> str:
        """
        Returns the SQLite Model PKey
        """
        return self.sql_config.sql_pkey

    @property
    def sql_pkey(self) -> str:
        """
        Returns the SQLite Model PKey
        """
        return getattr(self, self.sql_pkey_column)
    
    @property
    def sql_tablename(self) -> str:
        """
        Returns the SQLite Tablename
        """
        return self.sql_config.tablename
    
    @property
    def sql_autoset(self) -> bool:
        """
        Returns the SQLite Autoset
        """
        return self.sql_config.autoset
    
    @property
    def sql_fields(self) -> List[str]:
        """
        Returns the SQLite Fields
        """
        return self.sql_config.sql_fields
    
    @property
    def sql_schema(self) -> Dict[str, Union[str, List[str], Dict[str, str]]]:
        """
        Returns the SQLite Schemas
        """
        return self.sql_config.sql_schema
    

    @classmethod
    def _get_sql_field_schema(cls) -> Tuple[Dict[str, str], str, Dict[str, int]]:
        # sourcery skip: low-code-quality
        """
        Gets the sql field schema
        """
        results = {}
        if any(
            f.json_schema_extra and f.json_schema_extra.get('include_sql', False) for f in cls.model_fields.values()
        ):
            
            field_keys = [
                name for name, f in cls.model_fields.items()
                if name != 'tablename' and \
                    (
                        f.json_schema_extra and f.json_schema_extra.get('include_sql', False) and \
                        not f.json_schema_extra.get('exclude_sql', False)
                    )
            ]
            logger.info(f'Model {cls.__name__} has `include_sql` fields. Only selecting fields: {field_keys}', prefix = f'|g|DB: {cls.__name__}|e|', colored = True)
        else:
            field_keys = [
                name for name, f in cls.model_fields.items()
                if name != 'tablename' and not f.exclude and \
                    (not f.json_schema_extra or not f.json_schema_extra.get('exclude_sql', False))
            ]
        pkey = [
            name for name in field_keys if \
                cls.model_fields[name].json_schema_extra and \
                cls.model_fields[name].json_schema_extra.get('sql_pkey', False)
        ]
        pkey = pkey[0] if pkey else field_keys[0]
        for name, field in cls.model_fields.items():
            # if field.exclude: continue
            if name == 'tablename': continue
            if name not in field_keys: continue
            if field.annotation in [str, Optional[str]]:
                results[name] = 'TEXT'
            elif field.annotation in [int, Optional[int]]:
                results[name] = 'INTEGER'
            elif field.annotation in [float, Optional[float]]:
                results[name] = 'REAL'
            elif field.annotation in [bool, Optional[bool]]:
                results[name] = 'BOOLEAN'
            elif field.annotation in [
                datetime.datetime,
                Optional[datetime.datetime],
            ]:
                results[name] = 'DATETIME'
            else:
                logger.warning(f"Unsupported Field Type: {field.annotation}", prefix = '|g|DB|e|', colored = True)
                continue
            if name == pkey: results[name] += ' PRIMARY KEY'
            # if name == pkey: results[name] += ' UNIQUE'
        search_precisions: Dict[str, int] = {
            name: (
                cls.model_fields[name].json_schema_extra.get('sql_search_precision', 0)
                if cls.model_fields[name].json_schema_extra else 0
            ) for name in field_keys
        }
        return results, pkey, search_precisions

    @classmethod
    def _get_sql_index_items(cls, **kwargs) -> List[Tuple]:
        """
        Gets the index items
        """
        return []
    

    @classmethod
    def execute_sql_init(
        cls, 
        conn: 'sqlite3.Connection',
        tablename: Optional[str] = None,
        skip_index: Optional[bool] = None,
        auto_set: Optional[bool] = None,
    ):
        """
        Executes the sql init

        Parameters
        ----------
        conn : sqlite3.Connection
            The connection to the database
        tablename : Optional[str], optional
            The table name to use, by default None. This must be passed at least once during initialization.
        skip_index : Optional[bool], optional
            Whether to skip the index creation, by default None. This must be passed at least once during initialization.
        auto_set : Optional[bool], optional
            Whether to automatically update the table whenever model attributes are updated, by default None.
        """
        cur = conn.cursor()
        schemas = get_or_register_sqlite_schema(cls, tablename, auto_set, conn)
        tablename = tablename or schemas['tablename']
        script = SqliteTemplates['init'].render(**schemas)
        # logger.info(f"SQL Script: {script}", prefix = f'|g|DB: {tablename}|e|', colored = True) 
        try:
            cur.executescript(script)
            conn.commit()
        except Exception as e:
            logger.error(f'[{tablename}] Error in sql init: {script}: {e}')
            raise e
        if not skip_index and (index_items := cls._get_sql_index_items()):
            # logger.info(f'Loaded {len(index_items)} items: {index_items[0]}')
            index_script = SqliteTemplates['index'].render(**schemas)
            # logger.info(f"SQL Script: {index_script}, {index_items[0]}", prefix = f'|g|DB: {tablename}|e|', colored = True)
            try:
                cur.executemany(index_script, index_items)
                conn.commit()
            except Exception as e:
                logger.error(f'[{tablename}] Error in indexing: {index_script}: {index_items[0]}: {e}')
                raise e
        # logger.info(f"Completed SQL Init: {tablename}", prefix = f'|g|DB: {tablename}|e|', colored = True)

    @classmethod
    async def aexecute_sql_init(
        cls, 
        conn: 'aiosqlite.Connection',
        tablename: Optional[str] = None,
        skip_index: Optional[bool] = None,
        auto_set: Optional[bool] = None,
    ):
        """
        Executes the sql init

        Parameters
        ----------
        conn : aiosqlite.Connection
            The connection to the database
        tablename : Optional[str], optional
            The table name to use, by default None. This must be passed at least once during initialization.
        skip_index : Optional[bool], optional
            Whether to skip the index creation, by default None. This must be passed at least once during initialization.
        auto_set : Optional[bool], optional
            Whether to automatically update the table whenever model attributes are updated, by default None.
        """
        schemas = get_or_register_sqlite_schema(cls, tablename, auto_set, conn)
        cur = await conn.cursor()
        await cur.executescript(SqliteTemplates['init'].render(**schemas))
        # cur = await conn.executescript(SqliteTemplates['init'].render(**schemas))
        if not skip_index and (index_items := cls._get_sql_index_items()):
            # logger.info(f'Loaded {len(index_items)} items: {index_items[0]}')
            index_script = SqliteTemplates['index'].render(**schemas)
            # logger.info(f"SQL Script: {index_script}", prefix = f'|g|DB: {tablename}|e|', colored = True)
            await cur.executemany(index_script, index_items)
            await conn.commit()

    @classmethod
    def _create_sql_query_from_kwargs(
        cls,
        schemas: Dict[str, Union[str, List[str], Dict[str, str]]],
        query: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Creates the sql query from the kwargs

        precision: The search mode (0: loose, 1: field, 2: precise)
        """
        loose_matches: List[str] = []
        field_matches: List[str] = []
        exact_matches: List[str] = []
        search_precisions = schemas['search_precisions']
        for k, v in kwargs.items():
            if v is None: continue
            if isinstance(v, str) and not v.strip(): continue
            if k not in schemas['sql_fields']: continue
            precision = search_precisions.get(k, k)
            if precision == 0: loose_matches.append(normalize_sql_text(v))
            elif precision == 1: field_matches.append(f'({k} : {normalize_sql_text(v)})')
            elif precision == 2: exact_matches.append(f'{k} = "{v}"')
        
        query = query or ''
        tablename = schemas['tablename']

        if not loose_matches and not field_matches and not exact_matches and query:
            query = f'{tablename}_fts MATCH "{query}"'
            return query
        
        if exact_matches:
            query += f'({" OR ".join(exact_matches)}) AND '
        if loose_matches or field_matches:
            query += f'{tablename}_fts MATCH "'
            if field_matches: query += f'{" OR ".join(field_matches)} AND '
            if loose_matches: query += f'{" OR ".join(loose_matches)}'
            query = query.rstrip(' AND ')
            query += '"'
        query = query.replace('AND OR ', 'AND ')
        query = query.rstrip(' AND ')
        return query

    def _get_export_sql_data(
        self,
        schemas: Dict[str, Union[str, List[str], Dict[str, str]]],
        data: Optional[Dict[str, Any]] = None,
        include: 'IncEx' = None,
        exclude: 'IncEx' = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        **kwargs,
    ) -> Tuple[Union[str, int, float, Any], ...]:
        """
        Gets the export sql data
        """
        if data is None:
            data = self.model_dump(
                mode = 'json',
                include = include, 
                exclude = exclude, 
                by_alias = by_alias,
                exclude_unset = exclude_unset,
                exclude_defaults = exclude_defaults,
                exclude_none = exclude_none,
            )
        return tuple(data.get(k, None) for k in schemas['sql_keys'])

    def _get_export_sql_insert_fields(
        self,
        schemas: Dict[str, Union[str, List[str], Dict[str, str]]],
        data: Optional[Dict[str, Any]] = None,
        include: 'IncEx' = None,
        exclude: 'IncEx' = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        **kwargs,
    ) -> List[str]:
        """
        Gets the export sql index
        """
        if data is None:
            data = self.model_dump(
                mode = 'json',
                include = include, 
                exclude = exclude, 
                by_alias = by_alias,
                exclude_unset = exclude_unset,
                exclude_defaults = exclude_defaults,
                exclude_none = exclude_none,
            )
        return [k for k in schemas['sql_keys'] if k in data]


    def _get_export_sql_data_and_index(
        self,
        schemas: Dict[str, Union[str, List[str], Dict[str, str]]],
        include: 'IncEx' = None,
        exclude: 'IncEx' = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        **kwargs,
    ) -> Tuple[Dict[str, Union[str, List[str]]], Tuple[str, ...]]:
        """
        Gets the export sql data
        """
        data = self.model_dump(
            mode = 'json',
            include = include, 
            exclude = exclude, 
            by_alias = by_alias,
            exclude_unset = exclude_unset,
            exclude_defaults = exclude_defaults,
            exclude_none = exclude_none,
        )
        sql_insert_fields = [k for k in schemas['sql_keys'] if k in data]
        # sql_insert_values = tuple([data.get(k, None) for k in schemas['sql_keys']] + [None])
        sql_insert_values = tuple(data.get(k, None) for k in schemas['sql_keys'])
        results = {
            'sql_insert_query': ', '.join(sql_insert_fields),
            'sql_insert_fields': sql_insert_fields,
        }
        return (results, sql_insert_values)

    """
    Save Methods
    """

    @overload
    def sql_set(
        self,
        conn: 'sqlite3.Connection',
        tablename: Optional[str] = None,
        include: 'IncEx' = None,
        exclude: 'IncEx' = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        **kwargs,
    ) -> None:
        """
        Saves the data to the database
        """
        ...
    

    def sql_set(
        self,
        conn: 'sqlite3.Connection',
        tablename: Optional[str] = None,
        **kwargs,
    ):
        """
        Saves the data to the database
        """
        insert_dict, insert_data = self._get_export_sql_data_and_index(self.sql_schema, **kwargs)
        cur = conn.cursor()
        insert_script = SqliteTemplates['insert'].render(**self.sql_schema, **insert_dict)
        try:
            cur.execute(insert_script, insert_data)
            conn.commit()
            return cur.lastrowid
        except Exception as e:
            logger.error(f'[{self.sql_tablename}] Error in sql save: {insert_script}: {insert_data}: {e}')
            raise e


    @overload
    async def asql_set(
        self,
        conn: 'aiosqlite.Connection',
        tablename: Optional[str] = None,
        include: 'IncEx' = None,
        exclude: 'IncEx' = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        **kwargs,
    ) -> None:
        """
        Saves the data to the database
        """
        ...

    async def asql_set(
        self,
        conn: 'aiosqlite.Connection',
        tablename: Optional[str] = None,
        **kwargs,
    ):
        """
        Saves the data to the database
        """
        insert_dict, insert_data = self._get_export_sql_data_and_index(self.sql_schema, **kwargs)
        insert_script = SqliteTemplates['insert'].render(**self.sql_schema, **insert_dict)
        cur = await conn.cursor()
        try:
            await cur.execute(insert_script, insert_data)
            await conn.commit()
            return cur.lastrowid
        except Exception as e:
            logger.error(f'[{self.sql_tablename}] Error in sql save: {insert_script}: {insert_data}: {e}')
            raise e


    @classmethod
    def sql_set_many(
        cls: type['SQLResultT'],
        conn: 'sqlite3.Connection',
        items: List['SQLResultT'],
        tablename: Optional[str] = None,
        include: 'IncEx' = None,
        exclude: 'IncEx' = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        **kwargs,
    ):
        """
        Inserts many items to the database
        """
        schemas = get_or_register_sqlite_schema(cls, tablename)
        sql_insert_fields = items[0]._get_export_sql_insert_fields(schemas, include = include, exclude = exclude, by_alias = by_alias, exclude_unset = exclude_unset, exclude_defaults = exclude_defaults, exclude_none = exclude_none)
        sql_insert_values = [
            item._get_export_sql_data(schemas, include = include, exclude = exclude, by_alias = by_alias, exclude_unset = exclude_unset, exclude_defaults = exclude_defaults, exclude_none = exclude_none)
            for item in items
        ]
        insert_script = SqliteTemplates['insert'].render(**schemas, sql_insert_fields = sql_insert_fields)
        cur = conn.cursor()
        cur.executemany(insert_script, sql_insert_values)
        conn.commit()
        return cur.lastrowid
    
    @classmethod
    async def asql_set_many(
        cls: type['SQLResultT'],
        conn: 'aiosqlite.Connection',
        items: List['SQLResultT'],
        tablename: Optional[str] = None,
        include: 'IncEx' = None,
        exclude: 'IncEx' = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        **kwargs,
    ):
        """
        Inserts many items to the database
        """
        schemas = get_or_register_sqlite_schema(cls, tablename)
        sql_insert_fields = items[0]._get_export_sql_insert_fields(schemas, include = include, exclude = exclude, by_alias = by_alias, exclude_unset = exclude_unset, exclude_defaults = exclude_defaults, exclude_none = exclude_none)
        sql_insert_values = [
            item._get_export_sql_data(schemas, include = include, exclude = exclude, by_alias = by_alias, exclude_unset = exclude_unset, exclude_defaults = exclude_defaults, exclude_none = exclude_none)
            for item in items
        ]
        insert_script = SqliteTemplates['insert'].render(**schemas, sql_insert_fields = sql_insert_fields)
        cur = await conn.cursor()
        try:
            await cur.executemany(insert_script, sql_insert_values)
            await conn.commit()
            return cur.lastrowid
        except Exception as e:
            logger.error(f'[{tablename}] Error in sql save: {insert_script}: {sql_insert_values[:2]}: {e}')
            raise e
        # cur = await conn.executemany(insert_script, sql_insert_values)
        # await conn.commit()
        # return cur.lastrowid

    """
    Refresh Methods
    """

    def _set_sql_update_status(self, enabled: Optional[bool] = True):
        """
        Sets the sql update status
        """
        if enabled: 
            if not self.__pydantic_private__: self.__pydantic_private__ = {}
            self.__pydantic_private__['__in_sqlupdate__'] = True
        elif self.__pydantic_private__: _ = self.__pydantic_private__.pop('__in_sqlupdate__', None)

    def _is_in_sql_update(self) -> bool:
        """
        Checks if the object is in the sql update
        """
        if not self.__pydantic_private__: return False
        return '__in_sqlupdate__' in self.__pydantic_private__
        # return self.__pydantic_extra__.get('__in_sqlupdate__', False)

    @contextlib.contextmanager
    def _sql_update_context(self):
        """
        Context Manager for the sql update
        """
        self._set_sql_update_status(enabled = True)
        try:
            yield
        finally:
            self._set_sql_update_status(enabled = False)



    def sql_refresh(
        self: 'SQLResultT',
        conn: 'sqlite3.Connection',
        tablename: Optional[str] = None,
        **kwargs,
    )  -> 'SQLResultT':
        """
        Refreshes the data from the database
        """
        schemas = get_or_register_sqlite_schema(self.__class__, tablename)
        refresh_script = SqliteTemplates['refresh'].render(**schemas)
        cur = conn.cursor()
        cur.execute(refresh_script, (getattr(self, schemas['sql_pkey']),))
        result = cur.fetchone()
        if result is None: return None
        data = dict(zip(schemas['sql_keys'], result))
        with self._sql_update_context():
            for key, value in data.items():
                if value is None: continue
                if key in schemas['sql_keys']:
                    setattr(self, key, value)
        return self
        
    async def asql_refresh(
        self: 'SQLResultT',
        conn: 'aiosqlite.Connection',
        tablename: Optional[str] = None,
        **kwargs,
    )  -> 'SQLResultT':
        """
        Refreshes the data from the database
        """
        schemas = get_or_register_sqlite_schema(self.__class__, tablename)
        refresh_script = SqliteTemplates['refresh'].render(**schemas)
        cur = await conn.cursor()
        await cur.execute(refresh_script, (self.sql_pkey,))
        # await cur.execute(refresh_script, (getattr(self, schemas['sql_pkey']),))
        # cur = await conn.execute(refresh_script, (getattr(self, schemas['sql_pkey']),))
        result = await cur.fetchone()
        if result is None: return None
        data = dict(zip(schemas['sql_keys'], result))
        with self._sql_update_context():
            for key, value in data.items():
                if value is None: continue
                if key in schemas['sql_keys']:
                    setattr(self, key, value)
        return self

    """
    Search Methods
    """

    @overload
    @classmethod
    def search_one(
        cls: type[SQLResultT],
        conn: 'sqlite3.Connection',
        query: Optional[str] = None,
        skip: Optional[int] = None,
        **kwargs,
    ) -> 'SQLResultT':
        """
        Executes the sql search for one item
        """
        ...


    @overload
    @classmethod
    def search_one(
        cls: type[SQLResultT],
        conn: 'sqlite3.Connection',
        query: Optional[str] = None,
        skip: Optional[int] = None,
        return_fields: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Executes the sql search for one item
        """
        ...

    @overload
    @classmethod
    def search_one(
        cls: type[SQLResultT],
        conn: 'sqlite3.Connection',
        query: Optional[str] = None,
        skip: Optional[int] = None,
        return_id_only: Optional[bool] = True,
        **kwargs,
    ) -> str:
        """
        Executes the sql search for one item
        """
        ...


    @classmethod
    def search_one(
        cls: type[SQLResultT],
        conn: 'sqlite3.Connection',
        query: Optional[str] = None,
        skip: Optional[int] = None,
        return_id_only: Optional[bool] = None,
        return_fields: Optional[List[str]] = None,
        tablename: Optional[str] = None,
        verbose: Optional[bool] = None,
        **kwargs,
    ) -> Optional[Union['SQLResultT', str]]:
        """
        Executes the sql search for one item
        """

        cur = conn.cursor()
        sql_config = get_sqlite_model_config(cls, tablename)
        tablename = tablename or sql_config.tablename
        query = cls._create_sql_query_from_kwargs(sql_config.sql_schema, query, **kwargs)
        if not query.strip():
            if verbose: logger.warning(f'[{tablename}] No query provided. Returning null: {query}, {kwargs}')
            return None
        
        query_script = SqliteTemplates['search'].render(
            query = query, limit = 1, skip = skip, 
            return_id_only = return_id_only, 
            return_fields = return_fields,
            **sql_config.sql_schema
        )
        try:
            cur.execute(query_script)
        except Exception as e:
            logger.error(f'[{tablename}] Error Searching: {query_script} {e}')
            raise e
        result = cur.fetchone()
        if result is None: return None
        if return_fields: return dict(zip(return_fields, result))
        if return_id_only: return result[0]
        data = dict(zip(sql_config.sql_keys, result))
        return cls.model_validate(data)


    @overload
    @classmethod
    def search_many(
        cls: type[SQLResultT],
        conn: 'sqlite3.Connection',
        query: Optional[str] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        **kwargs,
    ) -> List['SQLResultT']:
        """
        Executes the sql search for many items
        """
        ...


    @classmethod
    def search_many(
        cls: type[SQLResultT],
        conn: 'sqlite3.Connection',
        query: Optional[str] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        return_id_only: Optional[bool] = None,
        return_fields: Optional[List[str]] = None,
        tablename: Optional[str] = None,
        verbose: Optional[bool] = None,
        **kwargs,
    ) -> List[Union['SQLResultT', str]]:
        """
        Executes the sql search for many items
        """
        sql_config = get_sqlite_model_config(cls, tablename)
        tablename = tablename or sql_config.tablename
        query = cls._create_sql_query_from_kwargs(sql_config.sql_schema, query, **kwargs)
        if not query.strip():
            if verbose: logger.warning(f'[{tablename}] No query provided. Returning empty list: {query}, {kwargs}')
            return []

        query_script = SqliteTemplates['search'].render(
            query = query, limit = limit, skip = skip,
            return_id_only = return_id_only, return_fields = return_fields, **sql_config.sql_schema
        )
        cur = conn.cursor()
        try:
            cur.execute(query_script)
            results: List[Union['SQLResultT', str]] = []
            for result in cur.fetchall():
                if result:
                    if return_fields: results.append(dict(zip(return_fields, result)))
                    elif return_id_only: results.append(result[0])
                    else: results.append(cls.model_validate(dict(zip(sql_config.sql_keys, result))))
                else: results.append(None)
            return results
        except Exception as e:
            logger.error(f'[{tablename}] Error Searching: {query_script} {e}')
            raise e


    @overload
    @classmethod
    async def asearch_one(
        cls: type[SQLResultT],
        conn: 'sqlite3.Connection',
        query: Optional[str] = None,
        skip: Optional[int] = None,
        **kwargs,
    ) -> 'SQLResultT':
        """
        Executes the sql search for one item
        """
        ...

    @classmethod
    async def asearch_one(
        cls: type[SQLResultT],
        conn: 'aiosqlite.Connection',
        # conn: 'SQLiteAIOConnection',
        query: Optional[str] = None,
        skip: Optional[int] = None,
        return_id_only: Optional[bool] = None,
        return_fields: Optional[List[str]] = None,
        tablename: Optional[str] = None,
        verbose: Optional[bool] = None,
        **kwargs,
    ) -> Optional[Union['SQLResultT', str]]:
        """
        Executes the sql search for one item
        """
        sql_config = get_sqlite_model_config(cls, tablename)
        tablename = tablename or sql_config.tablename
        query = cls._create_sql_query_from_kwargs(sql_config.sql_schema, query, **kwargs)
        if not query.strip():
            if verbose: logger.warning(f'[{tablename}] No query provided. Returning null: {query}, {kwargs}')
            return None
        query_script = SqliteTemplates['search'].render(
            query = query, limit = 1, skip = skip,
            return_id_only = return_id_only, return_fields = return_fields, **sql_config.sql_schema
        )
        cursor = await conn.cursor()
        try:
            await cursor.execute(query_script)
            result = await cursor.fetchone()
        except Exception as e:
            logger.error(f'[{tablename}] Error Searching: {query_script} {e}')
            raise e
        if result is None: return None
        if return_fields: return dict(zip(return_fields, result))
        if return_id_only: return result[0]
        data = dict(zip(sql_config.sql_keys, result))
        return cls.model_validate(data)
    

    @overload
    @classmethod
    async def asearch_many(
        cls: type[SQLResultT],
        conn: 'sqlite3.Connection',
        query: Optional[str] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        **kwargs,
    ) -> List['SQLResultT']:
        """
        Executes the sql search for many items
        """
        ...


    @classmethod
    async def asearch_many(
        cls: type[SQLResultT],
        conn: 'aiosqlite.Connection',
        # conn: 'SQLiteAIOConnection',
        query: Optional[str] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        return_id_only: Optional[bool] = None,
        return_fields: Optional[List[str]] = None,
        tablename: Optional[str] = None,
        verbose: Optional[bool] = None,
        **kwargs,
    ) -> List[Union['SQLResultT', str]]:
        """
        Executes the sql search for one item
        """
        sql_config = get_sqlite_model_config(cls, tablename)
        tablename = tablename or sql_config.tablename
        query = cls._create_sql_query_from_kwargs(sql_config.sql_schema, query, **kwargs)
        if not query.strip():
            if verbose: logger.warning(f'[{tablename}] No query provided. Returning empty list: {query}, {kwargs}')
            return []
        
        query_script = SqliteTemplates['search'].render(
            query = query, limit = limit, skip = skip,
            return_id_only = return_id_only, return_fields = return_fields, **sql_config.sql_schema
        )
        results: List[Union['SQLResultT', str]] = []
        try:
            cursor = await conn.cursor()
            await cursor.execute(query_script)
            for result in await cursor.fetchall():
                if result:
                    if return_fields: results.append(dict(zip(return_fields, result)))
                    elif return_id_only: results.append(result[0])
                    else: results.append(cls.model_validate(dict(zip(sql_config.sql_keys, result))))
                else: results.append(None)
            return results
        except Exception as e:
            logger.error(f'[{tablename}] Error Searching: {query_script} {e}')
            raise e

    


    def __setattr__(self, name: str, value: Any) -> None:
        """
        Sets the attribute
        """
        super().__setattr__(name, value)
        # Skip setting attributes that start with `sql_` or `_`
        if name.startswith('sql_') or name.startswith('_'): return
        if not self.sql_autoset: return
        if name not in self.sql_fields: return
        if self._is_in_sql_update(): return
        # conn = get_or_register_sqlite_connection(self.__class__)
        update_script = SqliteTemplates['update_field_attribute'].render(**self.sql_schema, name = name)
        try:
            cur = self.sql_config.conn.cursor()
            # cur.execute(update_script, (value, getattr(self, self.sql_pkey),))
            cur.execute(update_script, (value, self.sql_pkey,))
            self.sql_config.conn.commit()
        except Exception as e:
            logger.error(f'[{self.sql_tablename}] Error in auto setting: {name} {value}: {update_script}: {e}')
            raise e


        

    """
    Delete Methods
    """

    def sql_delete(
        self,
        conn: 'sqlite3.Connection',
        tablename: Optional[str] = None,
        **kwargs,
    ):
        """
        Deletes the object from the database
        """
        # schemas = get_or_register_sqlite_schema(self.__class__, tablename)
        delete_script = SqliteTemplates['delete'].render(**self.sql_schema)
        cur = conn.cursor()
        cur.execute(delete_script, (self.sql_pkey,))
        conn.commit()


        # schemas = get_or_register_sqlite_schema(self.__class__, tablename)
        # delete_script = SqliteTemplates['delete'].render(**schemas)
        # cur = conn.cursor()
        # cur.execute(delete_script, (getattr(self, schemas['sql_pkey']),))
        # conn.commit()

    async def asql_delete(
        self,
        conn: 'aiosqlite.Connection',
        tablename: Optional[str] = None,
        **kwargs,
    ):
        """
        Deletes the object from the database
        """
    
        delete_script = SqliteTemplates['delete'].render(**self.sql_schema)
        cur = await conn.cursor()
        await cur.execute(delete_script, (self.sql_pkey,))
        await conn.commit()        

        # schemas = get_or_register_sqlite_schema(self.__class__, tablename)
        # delete_script = SqliteTemplates['delete'].render(**schemas)
        # cur = await conn.execute(delete_script, (getattr(self, schemas['sql_pkey']),))
        # await conn.commit()