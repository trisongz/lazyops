from __future__ import annotations

"""
Base ORM Object Types
"""

# Note - The original errors for the dataclass implementation
# was due to pydantic's dataclass implementation not being
# compatible with sqlalchemy's mapped dataclass implementation

# https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession
# https://github.com/sqlalchemy/sqlalchemy/discussions/7336

import datetime

from pydantic import BaseModel
from pydantic.alias_generators import to_snake
from dataclasses import dataclass
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import as_declarative, declared_attr
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import MappedAsDataclass
from sqlalchemy.orm import Mapped
from sqlalchemy import MetaData
from sqlalchemy.orm import mapped_column
from sqlalchemy import Text, Table
from sqlalchemy import func as sql_func
# from sqlalchemy.orm import Mapped, Relationship, relationship
from sqlalchemy.orm import defer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect
from sqlalchemy.sql.expression import text, select, Select, ColumnElement, and_, update, Update, delete, or_
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import registry

from ...types import errors
from typing import Optional, Type, TypeVar, Union, Set, Any, Tuple, List, Dict, cast, Generic, Generator, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from lazyops.utils.logs import Logger
    from lazyops.libs.pooler import ThreadPool

mapper_registry = registry()


class Base(AsyncAttrs, DeclarativeBase):
    """
    A Base ORM Object
    """

    if TYPE_CHECKING:
        id: Mapped[Any]
        created_at: Mapped[datetime.datetime]
        updated_at: Mapped[datetime.datetime]


class BasePydantic(MappedAsDataclass, DeclarativeBase, dataclass_callable = dataclass):
    """
    Base Pydantic ORM Object
    """

    if TYPE_CHECKING:
        id: Mapped[Any]
        created_at: Mapped[datetime.datetime]
        updated_at: Mapped[datetime.datetime]

    
    def __init__(self, **kw):
        mapper = inspect(self).mapper
        for key in mapper.relationships:
            if key in kw:
                kw[key] = mapper.relationships[key].entity.class_(**kw[key])
        super().__init__(**kw)

    @property
    def orm_class_name(self) -> str:
        """
        Returns the ORM class name
        """
        return self.__class__.__name__
    
    @property
    def orm_parent_class_name(self) -> str:
        """
        Returns the ORM parent class name
        """
        return self.__class__.__qualname__.split('.')[3]

    def get_non_relationship_fields(
        self,
        include: Optional[Set[str]] = None,
        exclude: Optional[Set[str]] = None,
        **kwargs
    ) -> List[str]:
        """
        Returns the non relationship fields
        """
        include = include or set()
        exclude = exclude or set()
        return [
            k for k in self.__dict__ if (
                k not in self.__mapper__.relationships or \
                k in include or \
                k not in exclude
            )
        ]
    
    def get_relationship_fields(
        self,
        include: Optional[Set[str]] = None,
        exclude: Optional[Set[str]] = None,
        **kwargs
    ) -> List[str]:
        """
        Returns the relationship fields
        """
        include = include or set()
        exclude = exclude or set()
        return [
            k for k in self.__mapper__.relationships if (
                k not in include or \
                k in exclude
            )
        ]

    def get_exportable_kwargs(
        self,
        include: Any = None,
        exclude: Any = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Returns the exportable kwargs
        """
        data = {
            k: v for k, v in self.__dict__.items() if k in self.get_non_relationship_fields(
                include = include,
                exclude = exclude,
                **kwargs,
            )
        }
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
        if exclude_unset or exclude_defaults:
            data = {k: v for k, v in data.items() if v != self.__mapper__.columns[k].default.arg}
        return data

class BaseORMModel(BaseModel):
    """
    Generic Base ORM Model for Pydantic
    using this to allow for type checking
    """
    if TYPE_CHECKING:
        id: int
        created_at: datetime.datetime
        updated_at: datetime.datetime
    

@as_declarative()
class BaseORM:
    """
    Base ORM Object
    """
    if TYPE_CHECKING:
        id: Mapped[Any]
        created_at: Mapped[datetime.datetime]
        updated_at: Mapped[datetime.datetime]


    __name__: str


ModelTypeBaseORM = TypeVar("ModelTypeBaseORM", bound = BaseORM)
ModelTypeBasePydantic = TypeVar("ModelTypeBasePydantic", bound = BasePydantic)
ModelType = Union[ModelTypeBasePydantic, ModelTypeBaseORM]

SourceSchemaType = TypeVar("SourceSchemaType", bound = BaseORMModel)
ResultObject = TypeVar("ResultObject", BaseORMModel, BasePydantic)

async def has_this_obj(db: AsyncSession, obj: ModelType, attr: str, obj_id: Union[int, str]) -> bool:
    """
    Returns whether or not the object has this object
    """
    await db.refresh(obj, [attr])
    return any(item.id == obj_id for item in getattr(obj, attr))


async def append_obj(
    db: AsyncSession,
    *,
    parent_obj: ModelType,
    child_obj: ModelType,
    attr: str
) -> Tuple[ModelType, ModelType]:
    """
    Appends the object to the parent object
    """
    await db.refresh(parent_obj, [attr])
    items: List[ModelType] = getattr(parent_obj, attr)
    items.append(child_obj)
    setattr(parent_obj, attr, items)

    await db.commit()
    await db.refresh(parent_obj)
    await db.refresh(child_obj)
    return parent_obj, child_obj


async def remove_obj(
    db: AsyncSession,
    *,
    parent_obj: ModelType,
    child_obj: ModelType,
    attr: str
) -> Tuple[ModelType, ModelType]:
    """
    Removes the object from the parent object
    """
    await db.refresh(parent_obj, [attr])
    items: List[ModelType] = getattr(parent_obj, attr)
    items.remove(child_obj)
    setattr(parent_obj, attr, items)

    await db.commit()
    await db.refresh(parent_obj)
    await db.refresh(child_obj)
    return parent_obj, child_obj


def prepare_update_data(
    model: Type[ModelType], 
    update_data: Union[SourceSchemaType, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Prepares the update data
    """
    if isinstance(update_data, BaseModel):
        update_data = update_data.model_dump(exclude_unset=True)
    update_data = {k: v for k, v in update_data.items() if hasattr(model, k)}
    if hasattr(model, 'updated_at'):
        update_data['updated_at'] = datetime.datetime.now(datetime.timezone.utc)
    return update_data


"""
Credits to https://github.com/dmitrybabanovforreal
"""

class ObjectCRUD(Generic[ModelTypeBasePydantic, SourceSchemaType]):

    def __init__(
        self, 
        model: Type[Union[BaseORMModel, BasePydantic]], 
        schema: Optional[Type[BaseORMModel]] = None,
        defer_attrs: List[str] = None,
        auto_commit: Optional[bool] = True,
        **kwargs,
    ):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**

        * `model`: A SQLAlchemy model class
        * `schema`: A Pydantic schema class
        * `defer_attrs`: A list of attributes to defer loading
        * `auto_commit`: Whether or not to auto commit (True by default. Use False to allow for batch operations)
        """
        self.model = model
        
        self.defer_attrs = defer_attrs or []
        self.auto_commit = auto_commit
        self._schema = schema
        self._logger: Optional['Logger'] = None
        self._pooler: Optional['ThreadPool'] = None
        self._kwargs = kwargs
        self._lazyattrs: Dict[str, Any] = {}
        self._post_init(**kwargs)

    def _post_init(self, **kwargs):
        """
        Post-Init
        """
        pass


    @property
    def table_name(self) -> str:
        """
        Returns the table name
        """
        if 'table_name' not in self._lazyattrs:
            self._lazyattrs['table_name'] = self.model.__tablename__
        return self._lazyattrs['table_name']
    
    @property
    def table_schema_name(self) -> str:
        """
        Returns the table schema name
        """
        if 'table_schema_name' not in self._lazyattrs:
            self._lazyattrs['table_schema_name'] = self.model.metadata.schema
        return self._lazyattrs['table_schema_name']
    
    @property
    def table_with_schema_name(self) -> str:
        """
        Returns the table with schema name

        {table_schema_name}.{table_name}
        """
        if 'table_with_schema_name' not in self._lazyattrs:
            if self.table_schema_name:
                self._lazyattrs['table_with_schema_name'] = f'{self.table_schema_name}.{self.table_name}'
            else:
                self._lazyattrs['table_with_schema_name'] = self.table_name
        return self._lazyattrs['table_with_schema_name']
    
    @property
    def table_columns(self) -> List[str]:
        """
        Returns the table columns
        """
        if 'table_columns' not in self._lazyattrs:
            self._lazyattrs['table_columns'] = [c.name for c in self.table.columns]
        return self._lazyattrs['table_columns']
    
    @property
    def pooler(self) -> 'ThreadPool':
        """
        Returns the pooler
        """
        if self._pooler is None:
            from lazyops.libs.pooler import ThreadPooler
            self._pooler = ThreadPooler
        return self._pooler
    
    @property
    def table(self) -> Table:
        """
        Returns the table
        """
        return self.model.__table__
    

    @property
    def object_class_name(self) -> str:
        """
        Returns the object class name
        """
        if 'object_class_name' not in self._lazyattrs:
            self._lazyattrs['object_class_name'] = self.model.__name__
        return self._lazyattrs['object_class_name']

    @property
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        if not self._logger:
            from lazyops.utils.logs import logger
            self._logger = logger
        return self._logger
    
    """
    Getters
    """
    
    async def all(self, db: AsyncSession, stmt: Select) -> List[ResultObject]:
        """
        Returns all objects of the query
        """
        res = (await db.scalars(stmt)).all()
        res = cast(List[ModelType], res)
        return res
    
    async def first(
        self, 
        db: AsyncSession, 
        stmt: Union[Select, Insert, Update], 
        raise_for_not_found: bool = False
    ) -> ResultObject:
        """
        Returns the first object of the query
        """
        stmt = stmt.limit(1) # Potential cause for memory leak
        res = (await db.scalars(stmt)).first()
        res = cast(self.model, res)
        self._raise_for_not_found(res, raise_for_not_found)
        return res


    async def get(
        self,
        db: AsyncSession,
        id: Any,
        raise_for_not_found: bool = False,
        defer_attrs: List[str] = None,
    ) -> Optional[ResultObject]:
        """
        Returns the object with the given id
        """
        stmt = select(self.model).where(self.model.id == id)
        if defer_attrs: stmt = self._defer_attrs(stmt, defer_attrs)
        return await self.first(db, stmt, raise_for_not_found)

    async def get_first(
        self, 
        db: AsyncSession, 
        raise_for_not_found: bool = False, 
        **filters
    ) -> Optional[ResultObject]:
        """
        Gets the first object with the given filters
        """
        and_stmt = self._construct_and_statement(filters)
        stmt = select(self.model).where(and_stmt)
        stmt = self._defer_attrs(stmt, None)
        return await self.first(db, stmt, raise_for_not_found)


    async def get_many(
        self, 
        db: AsyncSession, *, 
        skip: Optional[int] = None,
        limit: Optional[int] = None,
        defer_attrs: List[str] = None,
    ) -> List[ResultObject]:
        """
        Gets multiple objects with pagination
        """
        stmt = select(self.model)
        if skip is not None: stmt = stmt.offset(skip)
        if limit is not None: stmt = stmt.limit(limit)
        stmt = self._defer_attrs(stmt, defer_attrs)
        return await self.all(db, stmt)

    async def get_many_filtered(
        self, 
        db: AsyncSession, 
        *, 
        skip: Optional[int] = None,
        limit: Optional[int] = None,
        **filters
    ) -> List[ResultObject]:
        """
        Gets multiple objects with pagination and filters
        """
        and_stmt = self._construct_and_statement(filters)
        stmt = select(self.model).where(and_stmt)
        if skip is not None: stmt = stmt.offset(skip)
        if limit is not None: stmt = stmt.limit(limit)
        stmt = self._defer_attrs(stmt, None)
        return await self.all(db, stmt)
    
    async def get_many_by_ids(
        self,
        db: AsyncSession,
        *,
        ids: List,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
        load_children: List[str] = None,
        raise_for_not_found: bool = False
    ) -> List[SourceSchemaType]:
        """
        Gets multiple objects with pagination and filters by ids
        """
        ids_string = ', '.join([f"'{i}'" for i in ids])
        stmt = select(self.model).where(text(f'id in ({ids_string})'))
        if skip is not None: stmt = stmt.offset(skip)
        if limit is not None: stmt = stmt.limit(limit)
        if load_children: stmt = self._add_related_obj_loading(stmt, load_children)
        objs = await self.all(db, stmt)
        if raise_for_not_found and len(objs) < len(ids):
            self._raise_for_not_found(None, raise_for_not_found=True)
        return objs
    

    async def get_random(
        self, 
        db: AsyncSession, 
        *, 
        limit: int = 100, 
        **filters
    ) -> List[ResultObject]:
        """
        Gets multiple objects with pagination and filters
        """
        and_stmt = self._construct_and_statement(filters)
        stmt = select(self.model).where(and_stmt).order_by(sql_func.random()).limit(limit)
        stmt = self._defer_attrs(stmt, None)
        return await self.all(db, stmt)
    
    """
    Count Operations
    """

    async def get_count(
        self, 
        db: AsyncSession, 
        **filters
    ) -> int:
        """
        Gets the count of objects with filters
        """
        and_stmt = self._construct_and_statement(filters)
        stmt = select(sql_func.count(self.model.id)).where(and_stmt)
        return await db.scalar(stmt)



    """
    Create Operations
    """

    def prepare_encoded_object(
        self,
        obj_in: SourceSchemaType,
        method: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Encodes the object
        """
        return jsonable_encoder(obj_in, **kwargs)
    
    async def prepare_encoded_object_one(
        self,
        obj_in: SourceSchemaType,
        method: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Encodes the object
        """
        values = await self.pooler.arun(self.prepare_encoded_object, obj_in, method, **kwargs)
        if method:
            if method == 'upsert' and hasattr(self.model, 'updated_at'):
                values['updated_at'] = datetime.datetime.now(datetime.timezone.utc)
            elif method == 'create' and hasattr(self.model, 'created_at'):
                values['created_at'] = datetime.datetime.now(datetime.timezone.utc)
        return values


    async def batch_prepare_encoded_objects(
        self,
        objs_in: List[SourceSchemaType],
        method: str,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Encodes the object
        """
        return await self.pooler.async_map(
            self.prepare_encoded_object_one,
            objs_in,
            method = method,
            **kwargs
        )

    async def create(
        self, 
        db: AsyncSession, 
        *, 
        obj_in: SourceSchemaType
    ) -> ModelType:
        """
        Creates an object
        """
        obj_in_data = self.prepare_encoded_object(obj_in, method = 'create')
        db_obj = self.model(**obj_in_data)  # type: ignore
        if hasattr(db_obj, 'created_at'):
            db_obj.created_at = datetime.datetime.now(datetime.timezone.utc)
        db.add(db_obj)
        if self.auto_commit:
            await db.commit()
            await db.refresh(db_obj)
        return db_obj
    
    async def create_if_not_exists(
        self, 
        db: AsyncSession, 
        *, 
        obj_in: SourceSchemaType, 
        index_elements: Optional[List[str]] = None,
        exclude_attrs: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        """
        Creates an object if it does not exist
        """
        values = self.prepare_encoded_object(obj_in, method = 'create_if_not_exists', exclude = exclude_attrs, **kwargs)
        stmt = insert(self.model).values(
            **values
        ).on_conflict_do_nothing(
            index_elements=index_elements
        )
        await db.execute(stmt)
        if self.auto_commit:
            await db.commit()
    
    async def exists(
        self,
        db: AsyncSession,
        id: Any,
        key: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Checks if the object exists
        """
        key = key or self.table.primary_key.columns[0].name
        stmt = select(self.model).where(getattr(self.model, key) == id)
        return await db.scalar(stmt) is not None

    """
    Upsert Operations
    """

    async def upsert(
        self, 
        db: AsyncSession, 
        *, 
        obj_in: SourceSchemaType, 
        index_elements: Optional[List[str]] = None,
        exclude_attrs: Optional[List[str]] = None,
        no_commit: Optional[bool] = None,
        **kwargs,
    ) -> None:
        """
        Upserts an object
        """
        index_elements = index_elements or ['id']
        values = self.prepare_encoded_object(obj_in, method = 'upsert', exclude = exclude_attrs, **kwargs)
        if hasattr(self.model, 'updated_at'):
            values['updated_at'] = datetime.datetime.now(datetime.timezone.utc)
        # from lazyops.utils.logs import logger
        # logger.info(f'Upserting: {values}', prefix = f'|g|{self.model.__name__}|e|', colored = True)
        stmt = insert(self.model).values(
            **values
        ).on_conflict_do_update(
            index_elements=index_elements,
            set_=values
        )
        await db.execute(stmt)
        if self.auto_commit and not no_commit:
            await db.commit()
    
    async def upsert_many(
        self,
        db: AsyncSession,
        *,
        objs_in: List['SourceSchemaType'],
    ):
        """
        Upserts multiple objects
        """
        for obj_in in objs_in:
            await self.upsert(db, obj_in = obj_in, no_commit = True)
        await db.commit()

    async def upsert_bulk(
        self,
        db: AsyncSession,
        *,
        objs_in: List['SourceSchemaType'],
        batch_size: Optional[int] = 200,
    ) -> int:
        """
        Upserts multiple objects
        """
        for i in range(0, len(objs_in), batch_size):
            await self.upsert_many(db, objs_in = objs_in[i:i+batch_size])

    
    async def upsert_many_with_idx(
        self,
        db: AsyncSession,
        *,
        objs_in: List['SourceSchemaType'],
        start_idx: int,
        raise_errors: Optional[bool] = None,
    ) -> Tuple[List[int], List[int]]:
        """
        Upserts multiple objects with an index
        """
        completed_idx: List[int] = []
        failed_idx: List[int] = []
        for n, obj_in in enumerate(objs_in):
            try:
                await self.upsert(db, obj_in = obj_in, no_commit = True)
                completed_idx.append(start_idx + n)
            
            except Exception as e:
                self.logger.info(f'|r|Attempting to rollback on error|e|: {e}', colored = True, prefix = f'|r|[{start_idx + n}] Error in upserting data|e|')
                await db.rollback()
                try:
                    await self.upsert(db, obj_in = obj_in, no_commit = True)
                    completed_idx.append(start_idx + n)
                except Exception as e:
                    self.logger.info(obj_in, colored = True, prefix = f'|r|[{start_idx + n}] Error in upserting data|e|', max_length = 1000)
                    self.logger.trace('Error in upserting data', e)
                    if raise_errors: raise e
                    failed_idx.append(start_idx + n)

        await db.commit()
        return (completed_idx, failed_idx)
    

    async def upsert_bulk_with_index(
        self,
        db: AsyncSession,
        *,
        objs_in: List['SourceSchemaType'],
        batch_size: Optional[int] = 200,
        raise_errors: Optional[bool] = None,
    ) -> Tuple[List[int], List[int]]:
        """
        Upserts multiple objects
        """
        completed_idx: List[int] = []
        failed_idx: List[int] = []
        for i in range(0, len(objs_in), batch_size):
            idxs = await self.upsert_many_with_idx(db, objs_in = objs_in[i:i+batch_size], start_idx = i, raise_errors = raise_errors)
            completed, failed = idxs
            if completed: completed_idx += completed
            if failed: failed_idx += failed
        return (completed_idx, failed_idx)
    
    """
    [v2] Upsert Operations
    """

    def get_update_columns(
        self,
        exclude_attrs: Optional[List[str]] = None,
        **kwargs,
    ) -> List[str]:
        """
        Returns the update columns
        """
        exclude_attrs = exclude_attrs or []
        if hasattr(self.model, 'created_at'): exclude_attrs.append('created_at')
        return [
            c.name for c in self.table.c
            if c not in list(self.table.primary_key.columns)
            and c.name not in exclude_attrs
        ]

    async def _upsert(
        self, 
        db: AsyncSession, 
        *, 
        obj_in: SourceSchemaType, 
        index_elements: Optional[List[str]] = None,
        exclude_attrs: Optional[List[str]] = None,
        no_commit: Optional[bool] = None,
        **kwargs,
    ) -> None:
        """
        [V2 Logic] Upserts an object
        """
        
        index_elements = index_elements or self.table.primary_key.columns
        update_cols = self.get_update_columns(exclude_attrs = exclude_attrs, **kwargs)
        values = await self.prepare_encoded_object_one(obj_in, method = 'upsert', exclude = exclude_attrs, **kwargs)
        stmt = insert(self.model).values(values)
        on_conflict_stmt = stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_ = {k: getattr(stmt.excluded, k) for k in update_cols},
        )
        await db.execute(on_conflict_stmt)
        if self.auto_commit and not no_commit:
            await db.commit()

    async def _upsert_batch(
        self, 
        db: AsyncSession, 
        *, 
        objs_in: List[SourceSchemaType], 
        index_elements: Optional[List[str]] = None,
        exclude_attrs: Optional[List[str]] = None,
        no_commit: Optional[bool] = None,
        **kwargs,
    ) -> None:
        """
        [V2 Logic] Upserts an object
        """
        index_elements = index_elements or self.table.primary_key.columns
        update_cols = self.get_update_columns(exclude_attrs=exclude_attrs, **kwargs)
        values = await self.batch_prepare_encoded_objects(objs_in, method = 'upsert', exclude = exclude_attrs, **kwargs)
        stmt = insert(self.model).values(values)
        on_conflict_stmt = stmt.on_conflict_do_update(
            index_elements = index_elements,
            set_ = {k: getattr(stmt.excluded, k) for k in update_cols},
        )
        await db.execute(on_conflict_stmt)
        if self.auto_commit and not no_commit:
            await db.commit()
    

    """
    Update Operations
    """

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[SourceSchemaType, Dict[str, Any]],
    ) -> ModelType:
        """
        Updates an object
        """
        update_data = prepare_update_data(self.model, obj_in)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        if self.auto_commit:
            await db.commit()
            await db.refresh(db_obj)
        return db_obj


    async def update_by_filter(
        self, 
        db: AsyncSession, 
        obj_in: Union[SourceSchemaType, Dict], 
        **filters
    ) -> Dict:
        """
        Updates an object by filter
        """
        update_data = prepare_update_data(self.model, obj_in)
        and_stmt = self._construct_and_statement(filters)
        returning_stmt = [getattr(self.model, attr) for attr in self._usable_attributes()]
        stmt = update(self.model).where(and_stmt).values(update_data).returning(*returning_stmt)
        res = (await db.execute(stmt)).first()
        self._raise_for_not_found(res, raise_for_not_found=True)
        if self.auto_commit: await db.commit()
        return dict(zip(self._usable_attributes(), res))
    
    """
    Delete Operations
    """

    async def remove(self, db: AsyncSession, *, id: Union[int, str]) -> ModelType:
        """
        Removes an object
        """
        obj = await self.get(db, id=id, raise_for_not_found=True)
        await db.delete(obj)
        await db.commit()
        return obj

    async def remove_obj(self, db: AsyncSession, *, db_obj: ModelType) -> ModelType:
        """
        Removes an object
        """
        await db.delete(db_obj)
        await db.commit()
        return db_obj

    async def delete_all_filtered(self, db: AsyncSession, **filters) -> None:
        """
        Deletes all objects with the given filters
        """
        and_stmt = self._construct_and_statement(filters)
        stmt = delete(self.model).where(and_stmt)
        await db.execute(stmt)
        await db.commit()

    """
    Misc Operations
    """

    def _add_related_obj_loading(self, stmt: Select, load_children: List[str] = None) -> Select:
        """
        Constructs a select statement with the given related objects
        """
        if load_children:
            options = iter(getattr(self.model, attr) for attr in load_children)
            stmt = stmt.options(selectinload(*options))
        return stmt

    def _raise_for_not_found(self, obj: Optional[ModelType], raise_for_not_found: bool) -> None:
        """
        Raises an error if the object is not found
        """
        if not obj and raise_for_not_found:
            raise errors.DatabaseItemNotFoundException(self.object_class_name)

    def _construct_and_statement(self, filters: dict) -> ColumnElement:
        """
        Constructs an AND statement from the given filters
        """
        _filters = ()
        for attr, value in filters.items():
            _filters += (getattr(self.model, attr) == value,)
        return and_(*_filters)
    

    def _defer_attrs(self, stmt: Union[Select, Update, Insert], defer_attrs: Optional[List[str]]):
        """
        Returns the statement with the deferred attributes
        """
        defer_attrs = defer_attrs or []
        defer_attrs += self.defer_attrs
        if defer_attrs:
            stmt = stmt.options(*[defer(getattr(self.model, attr), raiseload=True) for attr in defer_attrs])
        return stmt

    def _usable_attributes(self) -> Generator[str, None, None]:
        """
        Returns the usable attributes
        """
        for attr in inspect(self.model).c.keys():
            if attr not in self.defer_attrs:
                yield attr


    async def _cast_results_to_objects(
        self,
        db: AsyncSession,
        *,
        results: List[Tuple[str, Any]],
        cast_to_source: Optional[bool] = None,
        **kwargs,
    ) -> List['ResultObject']:
        """
        Casts the search results to objects
        """
        object_ids = [result[0] for result in results]
        objects: List['SourceSchemaType'] = await self.get_many_by_ids(db, ids = object_ids, **kwargs)
        if cast_to_source:
            objects = [obj.model_dump(mode = 'object') for obj in objects]
        return objects