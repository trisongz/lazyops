from __future__ import annotations

"""
Base ORM Objects
"""

from lazyops.imports._sqlalchemy import require_sql
require_sql(required=True, require_asyncpg=True, require_psycopg2=True)


import datetime
from uuid import UUID
from pydantic import BaseModel
from pydantic.alias_generators import to_snake
from dataclasses import dataclass
# from pydantic.dataclasses import dataclass

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import as_declarative, declared_attr
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import MappedAsDataclass
from sqlalchemy.orm import Mapped, InstrumentedAttribute
from sqlalchemy.orm import mapped_column
from sqlalchemy import func as sql_func
from sqlalchemy import Text
from sqlalchemy.orm import defer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect
from sqlalchemy.sql.expression import text, select, Select, ColumnElement, and_, update, Update, delete, or_
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import registry
from lazyops.utils.lazy import lazy_import
from lazyops.utils.logs import logger

from typing import Optional, Type, TypeVar, Union, Set, Any, Tuple, Literal, List, Dict, cast, Generic, Generator, Callable, TYPE_CHECKING

from . import errors


mapper_registry = registry()


class BasePydantic(MappedAsDataclass, DeclarativeBase, dataclass_callable = dataclass):
    
    if TYPE_CHECKING:
        id: Mapped[Union[str, int, UUID]]

    def __init__(self, **kw):
        mapper = inspect(self).mapper
        for key in mapper.relationships:
            if key in kw:
                kw[key] = mapper.relationships[key].entity.class_(**kw[key])
        super().__init__(**kw)
        self.orm_class_primary_keys = [c.name for c in mapper.primary_key]
        self.orm_class_primary_key = self.orm_class_primary_keys[0]

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

SortOrder = Literal['ASC', 'DESC', 'asc', 'desc']
IDType = Union[str, int, UUID]
ModelTypeORM = TypeVar("ModelTypeORM", bound = BasePydantic)
SourceSchemaType = TypeVar("SourceSchemaType", bound = BaseModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound = BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound = BaseModel)
SourceSchemaORM = TypeVar("SourceSchemaORM", bound = BaseModel)
ObjectResult = TypeVar("ObjectResult", BaseModel, BasePydantic)

async def has_this_obj(
    db: AsyncSession, 
    obj: ModelTypeORM, 
    attr: str, 
    obj_id: Union[int, str],
    primary_key: Optional[str] = None
) -> bool:
    """
    Returns whether or not the object has this object
    """
    await db.refresh(obj, [attr])
    primary_key = primary_key or obj.orm_class_primary_key
    return any(getattr(item, primary_key) == obj_id for item in getattr(obj, attr))


async def append_obj(
    db: AsyncSession,
    *,
    parent_obj: ModelTypeORM,
    child_obj: ModelTypeORM,
    attr: str
) -> Tuple[ModelTypeORM, ModelTypeORM]:
    """
    Appends the object to the parent object
    """
    await db.refresh(parent_obj, [attr])
    items: List[ModelTypeORM] = getattr(parent_obj, attr)
    items.append(child_obj)
    setattr(parent_obj, attr, items)

    await db.commit()
    await db.refresh(parent_obj)
    await db.refresh(child_obj)
    return parent_obj, child_obj


async def remove_obj(
    db: AsyncSession,
    *,
    parent_obj: ModelTypeORM,
    child_obj: ModelTypeORM,
    attr: str
) -> Tuple[ModelTypeORM, ModelTypeORM]:
    """
    Removes the object from the parent object
    """
    await db.refresh(parent_obj, [attr])
    items: List[ModelTypeORM] = getattr(parent_obj, attr)
    items.remove(child_obj)
    setattr(parent_obj, attr, items)

    await db.commit()
    await db.refresh(parent_obj)
    await db.refresh(child_obj)
    return parent_obj, child_obj


def prepare_update_data(
    model: Type[ModelTypeORM], 
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



class CRUDBase(Generic[ModelTypeORM, SourceSchemaType]):

    def __init__(
        self, 
        model: Union[Type[ModelTypeORM], str], 
        defer_attrs: List[str] = None,
        auto_commit: Optional[bool] = True,
        primary_key: Optional[str] = None,
        model_dump_kwargs: Optional[Dict[str, Any]] = None,
        source_model: Optional[Type[SourceSchemaType]] = None,
        **kwargs
    ):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**

        * `model`: A SQLAlchemy model class
        * `schema`: A Pydantic model (schema) class
        * `defer_attrs`: A list of attributes to defer loading
        """
        if isinstance(model, str): model = lazy_import(model)
        self.model: Type[ModelTypeORM] = model
        self.defer_attrs = defer_attrs or []
        self.auto_commit = auto_commit
        self._kwargs = kwargs
        if not primary_key:
            primary_key = inspect(self.model).primary_key[0].name
        self.primary_key = primary_key
        self.object_primary_key_field: InstrumentedAttribute[Union[str, int, UUID]] = getattr(self.model, self.primary_key)
        self.model_dump_kwargs = model_dump_kwargs or {}
        if source_model:
            if isinstance(source_model, str): source_model = lazy_import(source_model)
        self.source_model: Optional[Type[SourceSchemaType]] = source_model

    @property
    def table_name(self) -> str:
        """
        Returns the table name
        """
        return self.model.__tablename__

    @property
    def object_class_name(self) -> str:
        """
        Returns the object class name
        """
        return self.model.__name__
    

    """
    Base Methods
    """

    async def all(
        self, 
        db: AsyncSession, 
        stmt: Select,
        **kwargs
    ) -> List[ObjectResult]:
        """
        Returns all objects of the query
        """
        res = (await db.scalars(stmt)).all()
        res = cast(List[ModelTypeORM], res)
        return res
    
    async def first(
        self, 
        db: AsyncSession, 
        stmt: Union[Select, Insert, Update], 
        raise_for_not_found: bool = False,
        **kwargs
    ) -> Optional[ObjectResult]:
        """
        Returns the first object of the query
        """
        stmt = stmt.limit(1) # Potential cause for memory leak
        res = (await db.scalars(stmt)).first()
        res = cast(self.model, res)
        self._raise_for_not_found(res, raise_for_not_found)
        return res

    """
    Get / Read Methods
    """

    async def get(
        self,
        db: AsyncSession,
        id: IDType,
        raise_for_not_found: bool = False,
        defer_attrs: List[str] = None,
        **kwargs
    ) -> Optional[ObjectResult]:
        """
        Returns the object with the given id
        """
        stmt = select(self.model).where(self.object_primary_key_field == id)
        stmt = self._defer_attrs(stmt, defer_attrs)
        return await self.first(db, stmt, raise_for_not_found)


    async def get_first_filtered(
        self, 
        db: AsyncSession, 
        raise_for_not_found: bool = False, 
        **filters
    ) -> Optional[ObjectResult]:
        """
        Gets the first object with the given filters
        """
        and_stmt = self._construct_and_statement(filters)
        stmt = select(self.model).where(and_stmt)
        stmt = self._defer_attrs(stmt, None)
        return await self.first(db, stmt, raise_for_not_found)

    async def get_multi(
        self, 
        db: AsyncSession, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        sort_field: Optional[str] = None,
        sort_order: Optional[SortOrder] = None,
        **filters
    ) -> List[ObjectResult]:
        """
        Gets multiple objects with pagination
        """
        and_stmt = self._construct_and_statement(filters)
        stmt = select(self.model)
        if and_stmt: stmt = stmt.where(and_stmt)
        if skip is not None: stmt = stmt.offset(skip)
        if limit is not None: stmt = stmt.limit(limit)
        if sort_field: stmt = self._construct_sort_statement(stmt, sort_field, sort_order)
        stmt = self._defer_attrs(stmt, None)
        return await self.all(db, stmt)

    
    async def get_multi_ids(
        self,
        db: AsyncSession,
        *,
        ids: List[IDType],
        skip: Optional[int] = None,
        limit: Optional[int] = None,
        sort_field: Optional[str] = None,
        sort_order: Optional[SortOrder] = None,
        load_children: List[str] = None,
        raise_for_not_found: bool = False,
        **kwargs
    ) -> List[ObjectResult]:
        """
        Gets multiple objects with pagination and filters by ids
        """
        ids_string = self._create_id_string(ids)
        stmt: Select = select(self.model).where(text(f'{self.primary_key} in ({ids_string})'))
        if skip is not None: stmt = stmt.offset(skip)
        if limit is not None: stmt = stmt.limit(limit)
        if sort_field: stmt = self._construct_sort_statement(stmt, sort_field, sort_order)
        if load_children: stmt = self._add_related_obj_loading(stmt, load_children)
        objs = await self.all(db, stmt)
        if raise_for_not_found and len(objs) < len(ids):
            raise errors.MissingItemsException(self.object_class_name)
        return objs
    

    async def get_random(
        self, 
        db: AsyncSession, 
        *, 
        limit: int = 100, 
        sort_field: Optional[str] = None,
        sort_order: Optional[SortOrder] = None,
        **filters
    ) -> List[ObjectResult]:
        """
        Gets multiple objects with pagination and filters
        """
        and_stmt = self._construct_and_statement(filters)
        stmt = select(self.model)
        if and_stmt: stmt = stmt.where(and_stmt)
        stmt = stmt.order_by(sql_func.random()).limit(limit)
        if sort_field: stmt = self._construct_sort_statement(stmt, sort_field, sort_order)
        stmt = self._defer_attrs(stmt, None)
        return await self.all(db, stmt)
    

    async def get_count(
        self, 
        db: AsyncSession, 
        **filters
    ) -> int:
        """
        Gets the count of objects with filters
        """
        and_stmt = self._construct_and_statement(filters)
        stmt = select(sql_func.count(self.object_primary_key_field)) # .where(and_stmt)
        if and_stmt: stmt = stmt.where(and_stmt)
        return await db.scalar(stmt)
    
    """
    Create Methods
    """

    async def create(
        self, 
        db: AsyncSession, 
        *, 
        obj_in: SourceSchemaType,
        model_dump_kwargs: Optional[Dict[str, Any]] = None,
        no_commit: Optional[bool] = None,
        **kwargs
    ) -> ModelTypeORM:
        """
        Creates an object
        """
        db_obj = self._convert_source_to_orm_model(obj_in, model_dump_kwargs = model_dump_kwargs)
        if hasattr(db_obj, 'created_at'):
            db_obj.created_at = datetime.datetime.now(datetime.timezone.utc)
        db.add(db_obj)
        do_commit = no_commit is False if no_commit is not None else self.auto_commit
        if do_commit:
            await db.commit()
            await db.refresh(db_obj)
        return db_obj
    

    async def create_if_not_exists(
        self, 
        db: AsyncSession, 
        *, 
        obj_in: SourceSchemaType, 
        index_elements: Optional[List[str]] = None,
        model_dump_kwargs: Optional[Dict[str, Any]] = None,
        exclude_attrs: Optional[List[str]] = None,
        no_commit: Optional[bool] = None,
        **kwargs
    ) -> None:
        """
        Creates an object if it does not exist
        """
        index_elements = index_elements or [self.primary_key]
        values = self._convert_source_to_dict(
            obj_in, 
            model_dump_kwargs = model_dump_kwargs,
            exclude = exclude_attrs,
            **kwargs
        )
        stmt = insert(self.model).values(
            **values
        ).on_conflict_do_nothing(
            index_elements = index_elements
        )
        await db.execute(stmt)
        do_commit = no_commit is False if no_commit is not None else self.auto_commit
        if do_commit:
            await db.commit()

    """
    Upsert Methods
    """

    async def upsert(
        self, 
        db: AsyncSession, 
        *, 
        obj_in: SourceSchemaType, 
        model_dump_kwargs: Optional[Dict[str, Any]] = None,
        no_commit: Optional[bool] = None,
        **kwargs
    ) -> None:
        """
        Upserts an object
        """
        values = self._convert_source_to_dict(
            obj_in, 
            model_dump_kwargs = model_dump_kwargs,
            **kwargs
        )
        stmt = insert(self.model).values(
            **values
        ).on_conflict_do_update(
            index_elements=[self.primary_key],
            set_=values
        )
        await db.execute(stmt)
        do_commit = no_commit is False if no_commit is not None else self.auto_commit
        if do_commit:
            await db.commit()


    async def upsert_multi(
        self,
        db: AsyncSession,
        *,
        objs_in: List['SourceSchemaType'],
        model_dump_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Upserts multiple objects
        """
        for obj_in in objs_in:
            await self.upsert(db, obj_in = obj_in, model_dump_kwargs = model_dump_kwargs, no_commit = True)
        await db.commit()


    async def upsert_bulk(
        self,
        db: AsyncSession,
        *,
        objs_in: List['SourceSchemaType'],
        model_dump_kwargs: Optional[Dict[str, Any]] = None,
        batch_size: Optional[int] = 200,
        **kwargs
    ) -> int:
        """
        Upserts multiple objects
        """
        for i in range(0, len(objs_in), batch_size):
            await self.upsert_multi(db, objs_in = objs_in[i:i+batch_size], model_dump_kwargs = model_dump_kwargs, **kwargs)

    async def upsert_multi_with_idx(
        self,
        db: AsyncSession,
        *,
        objs_in: List['SourceSchemaType'],
        start_idx: int,
        model_dump_kwargs: Optional[Dict[str, Any]] = None,
        raise_errors: Optional[bool] = None,
        **kwargs
    ) -> Tuple[List[int], List[int]]:
        """
        Upserts multiple objects with an index
        """
        completed_idx: List[int] = []
        failed_idx: List[int] = []
        for n, obj_in in enumerate(objs_in):
            try:
                await self.upsert(db, obj_in = obj_in, no_commit = True, model_dump_kwargs = model_dump_kwargs)
                completed_idx.append(start_idx + n)
            except Exception as e:
                logger.info(f'|r|Attempting to rollback on error|e|: {e}', colored = True, prefix = f'|r|[{getattr(obj_in, self.primary_key)} - {start_idx + n}] Error in upserting data|e|')
                await db.rollback()
                try:
                    await self.upsert(db, obj_in = obj_in, no_commit = True)
                    completed_idx.append(start_idx + n)
                except Exception as e:
                    logger.info(obj_in, colored = True, prefix = f'|r|[{getattr(obj_in, self.primary_key)} - {start_idx + n}] Error in upserting data|e|')
                    logger.trace('Error in upserting data', e)
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
        model_dump_kwargs: Optional[Dict[str, Any]] = None,
        raise_errors: Optional[bool] = None,
        **kwargs
    ) -> Tuple[List[int], List[int]]:
        """
        Upserts multiple objects
        """
        completed_idx: List[int] = []
        failed_idx: List[int] = []
        for i in range(0, len(objs_in), batch_size):
            idxs = await self.upsert_multi_with_idx(
                db, 
                objs_in = objs_in[i:i+batch_size], 
                start_idx = i, 
                raise_errors = raise_errors,
                model_dump_kwargs = model_dump_kwargs,
                **kwargs
            )
            completed, failed = idxs
            if completed: completed_idx += completed
            if failed: failed_idx += failed
        return (completed_idx, failed_idx)

    """
    Update Methods
    """
    
    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelTypeORM,
        obj_in: Union[SourceSchemaType, Dict[str, Any]],
        **kwargs
    ) -> ModelTypeORM:
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
    Deletion Methods
    """

    async def delete_obj(self, db: AsyncSession, *, db_obj: ModelTypeORM) -> ModelTypeORM:
        """
        Removes an object
        """
        await db.delete(db_obj)
        await db.commit()
        return db_obj

    async def delete(
        self, 
        db: AsyncSession, 
        *, 
        id: IDType
    ) -> ModelTypeORM:
        """
        Removes an object
        """
        obj = await self.get(db, id=id, raise_for_not_found=True)
        return await self.delete_obj(db, db_obj=obj)

    async def delete_all_filtered(self, db: AsyncSession, **filters) -> None:
        """
        Deletes all objects with the given filters
        """
        and_stmt = self._construct_and_statement(filters)
        stmt = delete(self.model).where(and_stmt)
        await db.execute(stmt)
        await db.commit()


    """
    Utility Methods
    """

    async def get_from_results(
        self,
        db: AsyncSession,
        *,
        results: List[Union[Tuple[str, Any], IDType]],
        cast_to_source: Optional[bool] = None,
        source_model: Optional[Type[SourceSchemaType]] = None,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
        sort_field: Optional[str] = None,
        sort_order: Optional[SortOrder] = None,
        **kwargs
    )  -> List[ObjectResult]:
        """
        Fetches the objects from the results and optionally casts them to a source model
        """
        id_list = []
        for result in results:
            if isinstance(result, tuple):
                id_list.append(result[0])
            else:
                id_list.append(result)
        objs = await self.get_multi_ids(db, ids = id_list, skip = skip, limit = limit, sort_field = sort_field, sort_order = sort_order, **kwargs)
        if cast_to_source:
            source_model = source_model or self.source_model
            objs = [self._convert_orm_model_to_source(obj, source_model) for obj in objs]
        return objs

    
    def _create_id_string(self, ids: List[IDType]) -> str:
        """
        Creates an id string
        """
        _ids = []
        for id in ids:
            if isinstance(id, str):
                _ids.append(f"'{id}'")
            elif isinstance(id, UUID):
                _ids.append(f"'{str(id)}'")
            else:
                _ids.append(str(id))
        return ', '.join(_ids)

    def _add_related_obj_loading(self, stmt: Select, load_children: List[str] = None) -> Select:
        """
        Constructs a select statement with the given related objects
        """
        if load_children:
            options = iter(getattr(self.model, attr) for attr in load_children)
            stmt = stmt.options(selectinload(*options))
        return stmt

    def _raise_for_not_found(self, obj: Optional[ModelTypeORM], raise_for_not_found: bool) -> None:
        """
        Raises an error if the object is not found
        """
        if not obj and raise_for_not_found:
            raise errors.NoItemFoundException(self.object_class_name)


    def _defer_attrs(self, stmt: Union[Select, Update, Insert], defer_attrs: Optional[List[str]]):
        """
        Returns the statement with the deferred attributes
        """
        defer_attrs = defer_attrs or []
        if self.defer_attrs: defer_attrs += self.defer_attrs
        if defer_attrs:
            stmt = stmt.options(*[defer(getattr(self.model, attr), raiseload=True) for attr in defer_attrs])
        return stmt

    def _construct_and_statement(self, filters: dict) -> ColumnElement:
        """
        Constructs an AND statement from the given filters
        """
        if not filters: return None
        _filters = ()
        for attr, value in filters.items():
            _filters += (getattr(self.model, attr) == value,)
        return and_(*_filters)

    def _construct_or_statement(self, filters: dict) -> ColumnElement:
        """
        Constructs an OR statement from the given filters
        """
        if not filters: return None
        _filters = ()
        for attr, value in filters.items():
            _filters += (getattr(self.model, attr) == value,)
        return or_(*_filters)

    def _construct_sort_statement(
        self, 
        stmt: Select, 
        sort_field: str, 
        sort_order: Optional[SortOrder] = None
    ) -> ColumnElement:
        """
        Constructs a sort statement from the given sort field and sort order
        """
        if not sort_order: sort_order = 'ASC'
        sort_order = sort_order.upper()
        return stmt.order_by(getattr(self.model, sort_field).asc() if sort_order == 'ASC' else getattr(self.model, sort_field).desc())
    
    def _convert_source_to_dict(
        self,
        source: SourceSchemaType,
        model_dump_kwargs: Optional[Dict[str, Any]] = None,
        use_encoder: Optional[bool] = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        [model_dump | jsonable_encoder] Converts the source to a dict
        """
        dump_kwargs = self.model_dump_kwargs.copy()
        if model_dump_kwargs: dump_kwargs.update(model_dump_kwargs)
        if kwargs:
            for k, v in kwargs.items():
                if v is None: continue
                if k not in dump_kwargs:
                    dump_kwargs[k] = v
                    continue
                if isinstance(dump_kwargs[k], set):
                    dump_kwargs[k].add(v)
                elif isinstance(dump_kwargs[k], list):
                    dump_kwargs[k].append(v)
                elif isinstance(dump_kwargs[k], dict):
                    dump_kwargs[k].update(v)
                else:
                    dump_kwargs[k] = v
        if use_encoder:
            return jsonable_encoder(source, **dump_kwargs)
        return source.model_dump(**dump_kwargs)
    
    def _convert_source_to_orm_model(
        self,
        source: SourceSchemaType,
        model_dump_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ModelTypeORM:
        """
        Converts the source to the ORM model
        """
        data = self._convert_source_to_dict(source, model_dump_kwargs = model_dump_kwargs, **kwargs)
        try:
            return self.model(**data)
        except Exception as e:
            logger.trace(f'Error converting {type(source)} -> {self.object_class_name}', e)
            raise e

    def _convert_orm_model_to_source(
        self,
        obj: ObjectResult,
        source_model: Type[SourceSchemaType],
        **kwargs
    ) -> SourceSchemaType:
        """
        Converts the ORM model to the source model
        """
        values: Dict[str, Union[Dict[str, Any], Any]] = obj.model_dump(**kwargs)
        field_names, field_aliases = [], {}
        for name, field in source_model.model_fields.items():
            field_names.append(name)
            if field.alias: field_aliases[field.alias] = name
        if not isinstance(values, dict): 
            values = values.__dict__
            _ = values.pop('_sa_instance_state', None)
        
        # Handle Incoming Metadata
        if 'metadata_' in values and 'metadata' not in values:
            values['metadata'] = values.pop('metadata_')
        
        value_keys = set(values.keys())
        metadata = {
            key: values.pop(key)
            for key in value_keys
            if key not in field_names and key not in field_aliases
        }
        _ = metadata.pop('_sa_instance_state', None)
        if not values.get('metadata'):
            values['metadata'] = metadata
        else:
            metadata = {k: v for k, v in metadata.items() if v is not None}
            values['metadata'].update(metadata)
        for key, value in values['metadata'].items():
            if value is None: continue
            if key in field_names:
                values[key] = value
                continue
            if key in field_aliases:
                values[field_aliases[key]] = value
                continue
        return source_model.model_validate(values)

    def _usable_attributes(self) -> Generator[str, None, None]:
        """
        Returns the usable attributes
        """
        for attr in inspect(self.model).c.keys():
            if not self.defer_attrs or attr not in self.defer_attrs:
                yield attr
