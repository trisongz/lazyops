"""
The SQLite Model Registry
"""

import functools
from pydantic import BaseModel, computed_field
from typing import Any, Dict, List, Optional, Type, Union, TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    # import aiosqlite
    from lazyops.libs import aiosqlite
    from .mixins import SQLiteModelMixin


class SQLiteModelConfig(BaseModel):
    """
    The SQLite Model Schema
    """
    tablename: str
    sql_fields: Dict[str, Union[str, List[str], Dict[str, str]]]
    sql_pkey: str
    sql_keys: List[str]
    sql_insert: str
    sql_insert_q: str
    search_precisions: Dict[str, int]
    autoset: Optional[bool] = None
    sql_model_name: Optional[str] = None
    
    db_conn: Optional[Any] = None
    
    if TYPE_CHECKING:
        db_conn: Union['sqlite3.Connection', 'aiosqlite.Connection'] = None
    

    @property
    def conn(self) -> Union['sqlite3.Connection', 'aiosqlite.Connection']:
        """
        Returns the connection
        """
        if self.db_conn is None:
            if self.sql_model_name in _sqlite_model_name_to_connection:
                self.db_conn = _sqlite_model_name_to_connection[self.sql_model_name]
            else:
                raise ValueError(f'Model {self.sql_model_name} not registered and no connection provided')
        return self.db_conn

    def __getitem__(self, key: str) -> Any:
        """
        Gets the item
        """
        return getattr(self, key)
    
    @computed_field
    @property
    def sql_schema(self) -> Dict[str, Union[str, List[str], Dict[str, str]]]:
        """
        Returns the SQLite Schema
        """
        return {
            'tablename': self.tablename,
            'sql_fields': self.sql_fields,
            'sql_pkey': self.sql_pkey,
            'sql_keys': self.sql_keys,
            'sql_insert': self.sql_insert,
            'sql_insert_q': self.sql_insert_q,
            'search_precisions': self.search_precisions,
            'autoset': self.autoset,
        }
    

_sqlite_model_schema_registry: Dict[str, Dict[str, Union[str, List[str], Dict[str, str]]]] = {}
_sqlite_model_name_to_tablename: Dict[str, str] = {}
_sqlite_model_name_to_connection: Dict[str, Union['sqlite3.Connection', 'aiosqlite.Connection']] = {}
_sqlite_model_config_registry: Dict[str, SQLiteModelConfig] = {}


def get_or_register_sqlite_tablename(
    model: 'SQLiteModelMixin',
    tablename: Optional[str] = None,
) -> str:
    """
    Registers the SQLite Tablename
    """
    global _sqlite_model_name_to_tablename
    model_name = f'{model.__module__}.{model.__name__}'
    if not tablename and model_name not in _sqlite_model_name_to_tablename:
        if hasattr(model, 'tablename') and model.model_fields['tablename'].default is not None:
            tablename = model.model_fields['tablename'].default
        else:
            raise ValueError(f'Model {model_name} not registered and no tablename provided')
    if tablename and model_name not in _sqlite_model_name_to_tablename:
        _sqlite_model_name_to_tablename[model_name] = tablename
    
    if model_name not in _sqlite_model_name_to_tablename:
        raise ValueError(f'Model {model_name} not registered and no tablename provided')
    return _sqlite_model_name_to_tablename[model_name]

def get_or_register_sqlite_connection(
    model: 'SQLiteModelMixin',
    conn: Optional[Union['sqlite3.Connection', 'aiosqlite.Connection']] = None,
) -> Union['sqlite3.Connection', 'aiosqlite.Connection']:
    """
    Registers the SQLite Connection
    """
    global _sqlite_model_name_to_connection
    model_name = f'{model.__module__}.{model.__name__}'
    if conn and model_name not in _sqlite_model_name_to_connection:
        _sqlite_model_name_to_connection[model_name] = conn
    
    if model_name not in _sqlite_model_name_to_connection:
        raise ValueError(f'Model {model_name} not registered and no connection provided')
    return _sqlite_model_name_to_connection[model_name]

def get_or_register_sqlite_schema(
    model: 'SQLiteModelMixin',
    tablename: Optional[str] = None,
    auto_set: Optional[bool] = None,
    conn: Optional[Union['sqlite3.Connection', 'aiosqlite.Connection']] = None,
) -> Dict[str, Union[str, List[str], Dict[str, Union[str, int]]]]:
    # sourcery skip: extract-method
    """
    Registers the SQLite Schema
    """
    global _sqlite_model_schema_registry
    tablename = get_or_register_sqlite_tablename(model, tablename)
    if tablename not in _sqlite_model_schema_registry:
        sql_fields, sql_pkey, search_precisions = model._get_sql_field_schema()
        sql_keys = list(sql_fields.keys())
        sql_insert_q = ('?, ' * len(sql_keys)).rstrip(', ')
        sql_insert = ', '.join(sql_keys)
        _sqlite_model_schema_registry[tablename] = {
            'tablename': tablename,
            'sql_fields': sql_fields,
            'sql_pkey': sql_pkey,
            'sql_keys': sql_keys,
            'sql_insert': sql_insert,
            'sql_insert_q': sql_insert_q,
            'search_precisions': search_precisions,
        }
        if conn is not None: get_or_register_sqlite_connection(model, conn)
    if auto_set is not None: _sqlite_model_schema_registry[tablename]['auto_set'] = auto_set
    return _sqlite_model_schema_registry[tablename]


def get_sqlite_model_pkey(
    model: 'SQLiteModelMixin',
    tablename: Optional[str] = None,
) -> str:
    """
    Returns the SQLite Model PKey
    """
    tablename = get_or_register_sqlite_tablename(model, tablename)
    return _sqlite_model_schema_registry[tablename]['sql_pkey']
    


def has_auto_set_in_schema(
    model: 'SQLiteModelMixin',
) -> bool:
    """
    Checks if the model has auto set in the schema
    """
    return 'auto_set' in get_or_register_sqlite_schema(model)

@functools.lru_cache()
def retrieve_sqlite_model_schema(
    model_name: str
) -> Dict[str, Union[str, List[str], Dict[str, Union[str, int]]]]:
    """
    Retrieves the SQLite Model Schema
    """
    if model_name not in _sqlite_model_name_to_tablename:
        raise ValueError(f'Model {model_name} not registered')
    tablename = _sqlite_model_name_to_tablename[model_name]
    if tablename not in _sqlite_model_schema_registry:
        raise ValueError(f'Model {model_name} not registered')
    return _sqlite_model_schema_registry[tablename]


def get_sqlite_model_config(
    model: 'SQLiteModelMixin',
    tablename: Optional[str] = None,
) -> SQLiteModelConfig:
    """
    Returns the SQLite Model Config
    """
    model_name = f'{model.__module__}.{model.__name__}'
    if model_name not in _sqlite_model_config_registry:
        if tablename and tablename in _sqlite_model_schema_registry:
            schema = _sqlite_model_schema_registry[tablename]
        else:
            schema = retrieve_sqlite_model_schema(model_name)
        config = SQLiteModelConfig.model_validate(schema)
        config.sql_model_name = model_name
        if model_name in _sqlite_model_name_to_connection:
            config.db_conn = _sqlite_model_name_to_connection[model_name]
        _sqlite_model_config_registry[model_name] = config
    return _sqlite_model_config_registry[model_name]