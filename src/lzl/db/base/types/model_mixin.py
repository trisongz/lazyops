from __future__ import annotations

"""
A Model Mixin for SQL / Pydantic Models Designed for Improving Read Performance
by levearging `psqlpy`.

https://psqlpy-python.github.io/benchmarks.html
"""

import abc
import datetime
from lzl.types import BaseModel, Field, eproperty, rproperty
from lzl.logging import logger, null_logger
from pydantic.alias_generators import to_snake
import typing as t

if t.TYPE_CHECKING:
    from lzl.io import SerT
    from psqlpy import QueryResult
    from sqlalchemy.ext.asyncio import AsyncResult


SchemaT = t.TypeVar('SchemaT', bound = BaseModel)

class DBSchemaHandler(abc.ABC):
    """
    The Database Schema Handler

    It takes an existing BaseModel to handle Retrieval of Objects from the DB
    """

    table: t.Optional[str] = None
    schema_name: t.Optional[str] = None
    ref: t.Type[SchemaT] = None
    _extra: t.Dict[str, t.Any] = {}

    def __init__(
        self,
        model: t.Type[SchemaT],
        table: t.Optional[str] = None,
        schema_name: t.Optional[str] = None,
        debug_enabled: t.Optional[bool] = None,
        include_auto_types: t.Optional[bool] = False,
        autocast_to_schema: t.Optional[bool] = True,
        default_engine: t.Optional[t.Literal['psqlpy', 'sqlalchemy']] = 'psqlpy',
        **kwargs,
    ):
        """
        Initializes the PostgreSQL Schema Handler
        """
        self.ref = model
        self.table = table or to_snake(model.__name__)
        if schema_name: self.schema_name = schema_name
        self.logger = logger
        self.autologger = logger if debug_enabled is None else null_logger
        self.include_auto_types = include_auto_types
        self.autocast_to_schema = autocast_to_schema
        self.default_engine = default_engine
        self.postinit(**kwargs)

    def postinit(self, **kwargs):
        """
        Post Initialization
        """
        pass

    """
    Properties
    """

    @eproperty
    def table_name(self) -> str:
        """
        Returns the Table Name
        """
        return f'{self.schema_name}.{self.table}' if \
            self.schema_name else self.table

    @eproperty
    def columns(self) -> t.List[str]:
        """
        Returns the Columns
        """
        return [
            name for name, field in self.ref.model_fields.items()
            if not field.exclude and (
                not field.json_schema_extra or 
                not field.json_schema_extra.get('exclude_column', field.json_schema_extra.get('excluded_column'))
            )
        ]

    @eproperty
    def columns_as_string(self) -> str:
        """
        Returns the columns string
        """
        return ', '.join(self.columns)
    
    @eproperty
    def ser_columns(self) -> t.List[str]:
        """
        Returns the columns that are serialized
        """
        return [
            name for name, field in self.ref.model_fields.items()
            if field.annotation not in [
                str, t.Optional[str],
                int, t.Optional[int],
                float, t.Optional[float],
                bool, t.Optional[bool],
                datetime, t.Optional[datetime.datetime],
                list, t.Optional[t.List],
                dict, t.Optional[t.Dict],
            ]
            and name in self.columns
        ]

    @eproperty
    def _ser_columns_config(self) -> t.Dict[str, t.Dict[str, t.Union[str, int]]]:
        # sourcery skip: dict-comprehension, inline-immediately-returned-variable
        """
        Returns the Columns that are Serialized
        """
        # These are the columns that are serialized
        ser_columns = [name for name, field in self.ref.model_fields.items() if field.json_schema_extra and field.json_schema_extra.get('ser')]
        ser_dict = {}
        for name in ser_columns:
            ser_dict[name] = {
                'serializer': self.ref.model_fields[name].json_schema_extra.get('ser'),
                'compression': self.ref.model_fields[name].json_schema_extra.get('ser_comp'),
                'compression_level': self.ref.model_fields[name].json_schema_extra.get('ser_comp_level'),
            }
        # Use default serializers for the rest
        if self.include_auto_types:
            for name in self.ser_columns:
                if name in ser_dict: continue
                ser_dict[name] = {
                    'serializer': 'json',
                }
        return ser_dict

    @eproperty
    def _column_serializers(self) -> t.Dict[str, 'SerT']:
        """
        Returns the Serializers that are used for the schema
        """
        from lzl.io.ser import get_serializer
        return {
            name: get_serializer(**ser_config) for name, ser_config in self._ser_columns_config.items()
        }

    @eproperty
    def custom_decoders(self) -> t.Dict[str, t.Callable[..., t.Any]]:
        """
        Returns the Custom Decoders
        """
        return {
            name: ser.loads for name, ser in self._column_serializers.items()
        }


    """
    Helper Functions
    """

    @classmethod
    def normalize_ids_to_str(cls, ids: t.List[str]) -> str:
        """
        Normalizes the ids to a string
        """
        return ', '.join([f"'{id}'" for id in ids])

    def get_column_names(
        self,
        columns: t.Optional[t.List[str]] = None,
        **kwargs,
    ) -> t.List[str]:
        """
        Returns the Column Names
        """
        # This can be subclassed to handle additional filtering
        return self.columns if columns is None else columns
    
    def get_excluded_column_names(
        self,
        excluded_columns: t.Optional[t.List[str]] = None,
        **kwargs,
    ) -> t.List[str]:
        """
        Returns the Excluded Column Names
        """
        # This can be subclassed to handle additional filtering
        return [] if excluded_columns is None else excluded_columns


    def build_sql_filter(
        self,
        conditional: t.Optional[str] = 'AND',
        table_name: t.Optional[str] = None,
        include_table_name: t.Optional[bool] = None,
        **filters: t.Dict[str, t.Union[int, float, datetime.datetime, t.Dict, t.List, t.Any]]
    ) -> t.Dict[str, t.Union[t.List[str], str]]:
        """
        Returns 
        {
            "conditional": "AND",
            "statements": [
                "statement1",
                "statement2",
                "statement3",
            ]
        }
        which is properly formatted for the template
        """
        raise NotImplementedError
        return {
            "conditional": conditional,
            "statements": build_sql_filter_query_list(table_name = table_name, include_table_name = include_table_name, **filters),
        }

    def build_sql_filters(
        self,
        and_filters: t.Optional[t.Dict[str, t.Union[int, float, datetime.datetime, t.Dict, t.List, t.Any]]] = None,
        or_filters: t.Optional[t.Dict[str, t.Union[int, float, datetime.datetime, t.Dict, t.List, t.Any]]] = None,
        table_name: t.Optional[str] = None,
        include_table_name: t.Optional[bool] = None,
    ) -> t.List[t.Dict[str, t.Union[t.List[str], str]]]:
        """
        Creates the proper SQL filters
        [
            {
                "conditional": "AND",
                "statements": [
                    "statement1",
                    "statement2",
                    "statement3",
                ]
            },
            {
                "conditional": "OR",
                "statements": [
                    "statement4",
                    "statement5",
                    "statement6",
                ]
            }
        ]
        which is properly formatted for the template
        """
        table_name = table_name or self.table_name
        filters = []
        if and_filters: filters.append(self.build_sql_filter(conditional = "AND", table_name = table_name, include_table_name = include_table_name, **and_filters))
        if or_filters: filters.append(self.build_sql_filter(conditional = 'OR', table_name = table_name, include_table_name = include_table_name, **or_filters))
        return filters

    def build_filter_query(
        self,
        query: str,
        filters: t.Dict[str, t.Union[int, float, datetime.datetime, t.Dict, t.List, t.Any]],
    ) -> str:
        """
        Creates the filter query
        """
        query += '\nWHERE ' if 'WHERE' not in query else ' AND '
        filters = self.build_sql_filters(and_filters = filters)
        for fn, f in enumerate(filters):
            for sn, statement in enumerate(f['statements']):
                query += f'{statement} '
                if sn < len(f['statements']) - 1: query += f['conditional']
            if fn < len(filters) - 1: query += ' AND '
        return query
    

    def construct_select_query(
        self,
        columns: t.Optional[t.List[str]] = None,
        **kwargs,
    ) -> str:
        """
        Constructs the Select Query
        """
        # Can be subclassed to add additional columns
        columns = self.get_column_names(columns = columns, **kwargs)
        column_str = ', '.join(columns)
        return f'SELECT {column_str} FROM {self.table_name}'


    def build_select_query(
        self,
        ids: t.Optional[t.List[str]] = None,
        filters: t.Optional[t.Dict[str, t.Union[int, float, datetime.datetime, t.Dict, t.List, t.Any]]] = None,
        limit: t.Optional[int] = None,
        offset: t.Optional[int] = None,
        order_by: t.Optional[str] = None,
        order_direction: t.Optional[str] = 'ASC',
        columns: t.Optional[t.List[str]] = None,
        **kwargs,
    ) -> str:
        """
        Builds the get query
        """
        query = self.construct_select_query(columns = columns, **kwargs)
        if ids: 
            id_str = self.normalize_ids_to_str(ids)
            query += f'\nWHERE id IN ({id_str})'
        if filters: query = self.build_filter_query(query, filters)
        if order_by: query += f"\nORDER BY {order_by} {order_direction}"
        if limit: query += f'\nLIMIT {limit}'
        if offset: query += f'\nOFFSET {offset}'
        return query

    """
    The Iterators
    """

    def finalize_row(
        self,
        row: t.Tuple[t.Any, ...],
        new_row: t.Dict[str, t.Any],
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        """
        Finalizes the row
        """
        return new_row

    def map_row_sa(
        self,
        row: t.Tuple[t.Any, ...],
        columns: t.Optional[t.List[str]] = None,
        excluded_columns: t.Optional[t.List[str]] = None,
        cast_to_schema: t.Optional[bool] = None,
        **kwargs,
    ) -> t.Union[SchemaT, t.Dict[str, t.Any]]:
        """
        Maps the row to the schema model (sqlalchemy)
        """
        columns = self.get_column_names(columns = columns, **kwargs)
        excluded_columns = self.get_excluded_column_names(excluded_columns = excluded_columns, **kwargs)
        new_row = {}
        for col, row in zip(columns, row):
            if col in excluded_columns: continue
            if col in self._column_serializers and row is not None:
                row = self._column_serializers[col].loads(row)
            new_row[col] = row
        new_row = self.finalize_row(row = row, new_row = new_row, **kwargs)
        if cast_to_schema is None: cast_to_schema = self.autocast_to_schema
        return self.ref.model_validate(new_row) if cast_to_schema else new_row

    async def aiterate_sa(
        self,
        stream: t.AsyncGenerator['AsyncResult', None],
        columns: t.Optional[t.List[str]] = None,
        excluded_columns: t.Optional[t.List[str]] = None,
        extra_data: t.Optional[t.Dict[str, t.List[t.Any]]] = None,
        cast_to_schema: t.Optional[bool] = None,
        **kwargs
    ) -> t.AsyncGenerator[t.Union[SchemaT, t.Dict[str, t.Any]], None]:
        """
        Iterates the results (sqlalchemy)
        """
        if extra_data: extra_data = {k: iter(v) for k, v in extra_data.items()}
        async for row in stream:
            iter_data = {}
            if extra_data:
                iter_data = {k: next(v) for k, v in extra_data.items()}
            yield self.map_row_sa(
                row, 
                columns = columns, 
                excluded_columns = excluded_columns, 
                cast_to_schema = cast_to_schema,
                **iter_data,
                **kwargs
            )
    

    def map_row_pgp(
        self,
        row: t.Dict[str, t.Any],
        columns: t.Optional[t.List[str]] = None,
        excluded_columns: t.Optional[t.List[str]] = None,
        cast_to_schema: t.Optional[bool] = None,
        **kwargs,
    ) -> t.Union[SchemaT, t.Dict[str, t.Any]]:
        """
        Maps the row to the schema model (psqlpy)
        """
        columns = self.get_column_names(columns = columns, **kwargs)
        excluded_columns = self.get_excluded_column_names(excluded_columns = excluded_columns, **kwargs)
        new_row = {
            k: v for k, v in row.items() if k not in excluded_columns and
            k in columns
        }
        new_row = self.finalize_row(row = row, new_row = new_row, **kwargs)
        if cast_to_schema is None: cast_to_schema = self.autocast_to_schema
        return self.ref.model_validate(new_row) if cast_to_schema else new_row
    
    async def aiterate_pgp(
        self,
        stream: t.AsyncGenerator['QueryResult', None],
        columns: t.Optional[t.List[str]] = None,
        excluded_columns: t.Optional[t.List[str]] = None,
        extra_data: t.Optional[t.Dict[str, t.List[t.Any]]] = None,
        cast_to_schema: t.Optional[bool] = None,
        **kwargs
    ) -> t.AsyncGenerator[t.Union[SchemaT, t.Dict[str, t.Any]], None]:
        """
        Iterates the results (psqlpy)
        """
        if extra_data: extra_data = {k: iter(v) for k, v in extra_data.items()}
        async for result in stream:
            rows: t.List[t.Dict[str, t.Any]] = result.result(
                custom_decoders = self.custom_decoders,
            )
            for row in rows:
                iter_data = {k: next(v) for k, v in extra_data.items()} if extra_data else {}
                yield self.map_row_pgp(
                    row, 
                    columns = columns, 
                    excluded_columns = excluded_columns, 
                    cast_to_schema = cast_to_schema,
                    **iter_data,
                    **kwargs
                )



    def aiterate(
        self,
        stream: t.AsyncGenerator[t.Union['QueryResult', 'AsyncResult'], None],
        columns: t.Optional[t.List[str]] = None,
        excluded_columns: t.Optional[t.List[str]] = None,
        extra_data: t.Optional[t.Dict[str, t.List[t.Any]]] = None,
        cast_to_schema: t.Optional[bool] = None,
        engine: t.Optional[t.Literal['psqlpy', 'sqlalchemy']] = None,
        **kwargs
    ) -> t.AsyncGenerator[t.Union[SchemaT, t.Dict[str, t.Any]], None]:
        """
        Iterates the results and maps it to the proper 
        """
        if engine is None: engine = self.default_engine
        if engine == 'psqlpy':
            return self.aiterate_pgp(
                stream = stream,
                columns = columns,
                excluded_columns = excluded_columns,
                extra_data = extra_data,
                cast_to_schema = cast_to_schema,
                **kwargs
            )
        return self.aiterate_sa(
            stream = stream,
            columns = columns,
            excluded_columns = excluded_columns,
            extra_data = extra_data,
            cast_to_schema = cast_to_schema,
            **kwargs
        )
