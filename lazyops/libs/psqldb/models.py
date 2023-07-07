import contextlib
from sqlalchemy import func, text
from sqlalchemy import delete as sqlalchemy_delete
from sqlalchemy import update as sqlalchemy_update
from sqlalchemy import exists as sqlalchemy_exists
from sqlalchemy.future import select
from sqlalchemy.sql.expression import Select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload, joinedload, immediateload
from sqlalchemy import Column, Integer, DateTime, String, Text, ForeignKey, Boolean, Identity, Enum

from typing import Any, Generator, AsyncGenerator, Iterable, Optional, Union, Type, Dict, cast, TYPE_CHECKING, List, Tuple, TypeVar, Callable
from lazyops.utils import create_unique_id, create_timestamp
from lazyops.utils.logs import logger
from lazyops.types import lazyproperty
from lazyops.libs.psqldb.base import Base, PostgresDB, AsyncSession, Session
from lazyops.libs.psqldb.utils import SQLJson, get_pydantic_model, object_serializer, get_sqlmodel_dict
from fastapi.exceptions import HTTPException
from pydantic import BaseModel

ModelType = TypeVar("ModelType", bound = Base)
ORMModelT = TypeVar("ORMModelT", bound = 'ORMType')

_attr_func_map = {
    "selectinload": selectinload,
    "joinedload": joinedload,
    "immediateload": immediateload,
}

def get_attr_func(
    attr: Union[str, Callable] = None,
):
    if attr and isinstance(attr, str):
        return _attr_func_map.get(attr, selectinload)
    return attr or selectinload


class ORMType(object):

    id: Any = None

    @classmethod
    def _filter(cls, query: Optional[Select] = None, **kwargs) -> Select:
        """
        Build a filter query
        """
        query = query if query is not None else select(cls)
        return query.where(*[getattr(cls, key) == value for key, value in kwargs.items()])

    def _filter_update_data(self, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Filter update data
        """
        data = {}
        for field, value in kwargs.items():
            if not hasattr(self, field):
                continue
            if getattr(self, field) == value:
                continue
            data[field] = value
        return data or None

    @classmethod
    def _handle_exception(cls, msg: Optional[str] = None, e: Optional[Exception] = None):
        """
        Handle exception
        """
        msg = msg or f"{cls.__class__.__name__} not found"
        logger.trace(msg, error = e)
        raise HTTPException(status_code = 404, detail = msg)
    

    @classmethod
    def create(cls, **kwargs) -> ORMModelT:
        """
        Create a new instance of the model
        """
        new_cls = cls(**kwargs)
        with PostgresDB.session() as db_sess:
            db_sess.add(new_cls)
            db_sess.commit()
            db_sess.refresh(new_cls)
        return new_cls
    
    @classmethod
    async def acreate(cls, **kwargs) -> 'ORMType':
        """
        Create a new instance of the model
        """
        async with PostgresDB.async_session() as db_sess:
            new_cls = cls(**kwargs)
            db_sess.add(new_cls)
            await db_sess.commit()
            await db_sess.refresh(new_cls)
        return new_cls
    
    # @classmethod
    # def update(cls, id: Any, **kwargs):
    #     with PostgresDB.session() as db_sess:
    #         query = (
    #             sqlalchemy_update(cls)
    #             .where(cls.id == id)
    #             .values(**kwargs)
    #             .execution_options(synchronize_session="fetch")
    #         )
    #         db_sess.execute(query)
    #         db_sess.commit()
    
    # @classmethod
    # async def aupdate(cls, id: Any, **kwargs):
    #     async with PostgresDB.async_session() as db_sess:


    #         query = (
    #             sqlalchemy_update(cls)
    #             .where(cls.id == id)
    #             .values(**kwargs)
    #             .execution_options(synchronize_session="fetch")
    #         )
    #         await db_sess.execute(query)
    #         await db_sess.commit()

    def update(self, **kwargs) -> 'ORMType':
        """
        Update a record
        """
        filtered_update = self._filter_update_data(**kwargs)
        if not filtered_update:
            return self
        with PostgresDB.session() as db_sess:
            for field, value in filtered_update.items():
                setattr(self, field, value)
                db_sess.add(self)
                db_sess.commit()
                db_sess.refresh(self)
        return self

    async def aupdate(self, **kwargs) -> 'ORMType':
        """
        Update a record
        """
        filtered_update = self._filter_update_data(**kwargs)
        if not filtered_update:
            return self
        async with PostgresDB.async_session() as db_sess:
            for field, value in filtered_update.items():
                setattr(self, field, value)
                db_sess.add(self)
                await db_sess.commit()
                await db_sess.refresh(self)
        return self



    @classmethod
    def get(
        cls, 
        # value: Any, 
        # key: str = "id", 
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
        raise_exceptions: Optional[bool] = True,
        **kwargs,
    ) -> 'ORMType':
        """
        Get a record
        """
        with PostgresDB.session(ro=readonly) as db_sess:
            # query = select(cls).where(getattr(cls, key) == value)
            query = cls._filter(**kwargs)
            if load_attrs:
                load_attr_method = get_attr_func(load_attr_method)
                for attr in load_attrs:
                    query = query.options(load_attr_method(getattr(cls, attr)))
            results = db_sess.execute(query)
            (result,) = results.one()
            if not result and raise_exceptions:
                cls._handle_exception()
            return result

    @classmethod
    async def aget(
        cls, 
        # value: Any, 
        # key: str = "id",
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
        raise_exceptions: Optional[bool] = True,
        **kwargs,
    ) -> Type['ORMType']:
        """
        Get a record
        """
        async with PostgresDB.async_session(ro=readonly) as db_sess:
            # query = select(cls).where(*[getattr(cls, key) == value for key, value in kwargs.items()])
            query = cls._filter(**kwargs)
            if load_attrs:
                load_attr_method = get_attr_func(load_attr_method)
                for attr in load_attrs:
                    query = query.options(load_attr_method(getattr(cls, attr)))
            results = await db_sess.execute(query)
            (result,) = results.one()
            if not result and raise_exceptions:
                cls._handle_exception()
            return result

    @classmethod
    def get_all(
        cls,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
        **kwargs,
    ) -> List['ORMType']:
        """
        Get all records
        """
        with PostgresDB.session(ro=readonly) as db_sess:
            # query = select(cls)
            query = cls._filter(**kwargs)
            if load_attrs:
                load_attr_method = get_attr_func(load_attr_method)
                for attr in load_attrs:
                    query = query.options(load_attr_method(getattr(cls, attr)))
            results = db_sess.execute(query)
            return results.scalars().all()
    
    @classmethod
    async def aget_all(
        cls,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
        **kwargs,
    ) -> List['ORMType']:
        """
        Get all records
        """
        async with PostgresDB.async_session(ro=readonly) as db_sess:
            # query = select(cls)
            # if kwargs:
            #     query = query.where(*[getattr(cls, key) == value for key, value in kwargs.items()])
            query = cls._filter(**kwargs)
            if load_attrs:
                load_attr_method = get_attr_func(load_attr_method)
                for attr in load_attrs:
                    query = query.options(load_attr_method(getattr(cls, attr)))
            results = await db_sess.execute(query)
            return results.scalars().all()
    
    @classmethod
    def delete(cls, id: Any):
        with PostgresDB.session() as db_sess:
            query = sqlalchemy_delete(cls).where(cls.id == id)
            db_sess.execute(query)
            db_sess.commit()
    
    @classmethod
    async def async_delete(cls, **kwargs) -> ModelType:
        """
        Delete a record
        """
        obj = await cls.aget(**kwargs, raise_exceptions = True)
        async with PostgresDB.async_session() as db_sess:
            db_sess.delete(obj)
            await db_sess.commit()
        return obj
    
    @classmethod
    def delete_all(cls):
        with PostgresDB.session() as db_sess:
            query = sqlalchemy_delete(cls)
            db_sess.execute(query)
            db_sess.commit()
    
    @classmethod
    async def adelete_all(cls):
        async with PostgresDB.async_session() as db_sess:
            query = sqlalchemy_delete(cls)
            await db_sess.execute(query)
            await db_sess.commit()
    
    @classmethod
    async def aexists(cls, **kwargs) -> bool:
        """
        Return True if a record exists
        """
        async with PostgresDB.async_session(ro=True) as db_sess:
            query = cls._filter(sqlalchemy_exists(), **kwargs).select()
            # result = await db_sess.execute(query)
            # return bool(result.scalar())
            return bool(await db_sess.scalar(query))


    @classmethod
    def count(
        cls, 
        # owner_id: Optional[Any] = None,
        # owner_key: Optional[str] = "owner_id",
        readonly: Optional[bool] = True,
        **kwargs
    ) -> int:
        """
        Count the number of records in the table.
        """
        query = select(func.count(cls.id)).filter(*[getattr(cls, key) == value for key, value in kwargs.items()]) \
            if kwargs else select(func.count(cls.id))

        try:
            with PostgresDB.session(ro=readonly) as db_sess:
                return db_sess.scalar(query)
        except Exception as e:
            logger.error(e)
            return 0
        
    @classmethod
    async def acount(
        cls, 
        # owner_id: Optional[Any] = None,
        # owner_key: Optional[str] = "owner_id",
        readonly: Optional[bool] = True,
        **kwargs
    ) -> int:
        """
        Count the number of records in the table.
        """
        query = cls._filter(**kwargs) \
            if kwargs else select(func.count(cls.id))
        # query = select(func.count(cls.id)).filter(getattr(cls, owner_key) == owner_id) \
        #     if kwargs else select(func.count(cls.id))
        try:
            async with PostgresDB.async_session(ro=readonly) as db_sess:
                return await db_sess.scalar(query)
        except Exception as e:
            logger.error(e)
            return 0

    
    def dict(
        self,
        exclude: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
        safe_encode: Optional[bool] = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Return a dictionary representation of the model.
        """
        data = self.pydantic_model.dict(
            exclude=exclude,
            include=include,
            **kwargs
        )
        if safe_encode: data = {key: object_serializer(value) for key, value in data.items()}
        return data
    
    def json(
        self,
        exclude: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
        exclude_none: Optional[bool] = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Return a dictionary representation of the model.
        """
        return self.pydantic_model.json(
            exclude=exclude,
            include=include,
            exclude_none=exclude_none,
            **kwargs
        )

    def diff(
        self,
        other: Union[Any, 'ORMType']
    ) -> Dict[str, Any]:
        """
        Return a dictionary of the differences between this model and another.
        """
        return {
            key: value
            for key, value in self.dict().items()
            if key in other.dict() and self.dict()[key] != other.dict()[key]
        }
    
    @lazyproperty
    def pydantic_model(self) -> Type[BaseModel]:
        """
        Return the Pydantic model for this ORM model.
        """
        return get_pydantic_model(self)

    @classmethod
    def filter_first(
        cls, 
        attr: str, 
        value: Any,
        model_type: Optional[ModelType] = None,
        readonly: Optional[bool] = False,
    ) -> Optional[ModelType]:
        model_type = model_type or cls
        attr_obj = getattr(model_type, attr)
        stmt = select(model_type).where(attr_obj == value)
        with PostgresDB.session(ro=readonly) as db_sess:
            return cls.first(db_sess, stmt, model_type)

    @classmethod
    async def afilter_first(
        cls, 
        attr: str, 
        value: Any,
        model_type: Optional[ModelType] = None,
        readonly: Optional[bool] = False,
    ) -> Optional[ModelType]:
        """
        Return the first result of a query.
        """
        model_type = model_type or cls
        attr_obj = getattr(model_type, attr)
        stmt = select(model_type).where(attr_obj == value)
        async with PostgresDB.async_session(ro=readonly) as db_sess:
            return await cls.afirst(db_sess, stmt, model_type)

    @classmethod
    def first(
        cls, 
        db: Session, 
        stmt: Select,
        model_type: ModelType,
    ) -> Optional[ModelType]:
        """
        Return the first result of a query.
        """
        res = (db.scalars(stmt)).first()
        res = cast(model_type, res)
        return res
    
    @classmethod
    async def afirst(
        cls, 
        db: AsyncSession, 
        stmt: Select,
        model_type: ModelType,
    ) -> Optional[ModelType]:
        """
        Return the first result of a query.
        """
        res = (await db.scalars(stmt)).first()
        res = cast(model_type, res)
        return res
    
    @classmethod
    async def aget_or_create(cls, _defaults: Dict[str, Any] = None, **kwargs) -> Tuple[ModelType, bool]:
        """
        Create a new instance of the model, or return the existing one.
        """
        try:
            return await cls.aget(**kwargs), False
        except NoResultFound:
            _defaults = _defaults or {}
            return await cls.acreate(**{**kwargs, **_defaults}), True
            
    @classmethod
    async def aget_or_none(cls, **kwargs) -> Optional[ModelType]:
        """
        Return an instance of the model, or None.
        """
        try:
            return await cls.get(cls, **kwargs)
        except NoResultFound:
            return None
    
    @classmethod
    async def aget_or_create_or_update(cls, _defaults: Dict[str, Any] = None, **kwargs) -> Tuple[ModelType, bool]:
        """
        Create a new instance of the model, 
        or return the existing one after updating it.

        Returns a tuple of (instance, created | updated), where created is a boolean
        """
        try:
            res = await cls.aget(**kwargs)
            return (await res.aupdate(**_defaults), True) \
                if _defaults else (res, False)
        except NoResultFound:
            _defaults = _defaults or {}
            return await cls.acreate(**{**kwargs, **_defaults}), False

    @classmethod
    def get_by_owner(
        cls,
        owner_id: int,
        owner_key: str = "owner_id",
        name: Optional[str] = None,
        name_key: Optional[str] = "name",
        skip: int = 0, 
        limit: int = 100,
        order_by: Optional[Any] = None,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
    ):
        """
        Fetch all records by owner_id
        """
        with PostgresDB.session(ro=readonly) as db_sess:
            query = select(cls).where(getattr(cls, owner_key) == owner_id)
            if name:
                query = query.where(getattr(cls, name_key) == name)
            if load_attrs:
                load_attr_method = get_attr_func(load_attr_method)
                for attr in load_attrs:
                    query = query.options(load_attr_method(getattr(cls, attr)))
            if skip is not None:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)
            if order_by is not None:
                query = query.order_by(order_by)
            results = db_sess.execute(query)
            return results.scalars().all()
    
    @classmethod
    async def aget_by_owner(
        cls,
        owner_id: int,
        owner_key: str = "owner_id",
        name: Optional[str] = None,
        name_key: Optional[str] = "name",
        skip: int = 0, 
        limit: int = 100,
        order_by: Optional[Any] = None,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly: Optional[bool] = False,
    ):
        """
        Fetch all records by owner_id
        """
        async with PostgresDB.async_session(ro=readonly) as db_sess:
            query = select(cls).where(getattr(cls, owner_key) == owner_id)
            if name:
                query = query.where(getattr(cls, name_key) == name)
            if load_attrs:
                load_attr_method = get_attr_func(load_attr_method)
                for attr in load_attrs:
                    query = query.options(load_attr_method(getattr(cls, attr)))
            if skip is not None:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)
            if order_by is not None:
                query = query.order_by(order_by)
            results = await db_sess.execute(query)
            return results.scalars().all()


    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.dict()})>"

"""
Async ORM Type
"""

# AsyncORMTypeT = TypeVar("AsyncORMTypeT", "AsyncORMType", Base)


# class AsyncORMType(object):

class AsyncORMType(object):
    """
    Only contains async methods
    """

    id: str = Column(Text, default = create_unique_id, primary_key = True, index = True)
    created_at = Column(DateTime(timezone=True), default = create_timestamp, server_default = func.now())
    updated_at = Column(DateTime(timezone=True), default = create_timestamp, server_default = func.now(), onupdate = create_timestamp)


    @classmethod
    def _filter(
        cls, 
        query: Optional[Select] = None, 
        **kwargs
    ) -> Select:
        """
        Build a filter query
        """
        query = query if query is not None else select(cls)
        return query.where(*[getattr(cls, key) == value for key, value in kwargs.items()])

    @classmethod
    def _build_query(
        cls,
        query: Optional[Select] = None,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        **kwargs
    ) -> Select:
        """
        Build a query
        """
        query = query if query is not None else select(cls)
        query = query.where(*[getattr(cls, key) == value for key, value in kwargs.items()])
        if load_attrs:
            load_attr_method = get_attr_func(load_attr_method)
            for attr in load_attrs:
                query = query.options(load_attr_method(getattr(cls, attr)))
        return query

    def _filter_update_data(self, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Filter update data
        """
        data = {}
        for field, value in kwargs.items():
            if not hasattr(self, field): continue
            if getattr(self, field) == value: 
                # logger.warning(f"Skipping {field}={getattr(self, field)} as value is the same: {value}")
                continue
            data[field] = value
        return data or None

    @classmethod
    def _handle_exception(cls, msg: Optional[str] = None, e: Optional[Exception] = None, verbose: Optional[bool] = False):
        """
        Handle exception
        """
        msg = msg or f"{cls.__name__} not found"
        if verbose: logger.trace(msg, error = e)
        raise e or HTTPException(status_code = 404, detail = msg)
        # raise HTTPException(status_code = 404, detail = msg)

    
    @classmethod
    async def create(cls, **kwargs) -> Type['AsyncORMType']:
        """
        Create a new instance of the model
        """
        async with PostgresDB.async_session() as db_sess:
            new_cls = cls(**kwargs)
            db_sess.add(new_cls)
            await db_sess.flush()
            await db_sess.commit()
            # await db_sess.flush(new_cls)
            await db_sess.refresh(new_cls)
        return new_cls


    @classmethod
    def _create(cls, **kwargs) -> Type['AsyncORMType']:
        """
        Create a new instance of the model
        """
        with PostgresDB.session() as db_sess:
            new_cls = cls(**kwargs)
            db_sess.add(new_cls)
            db_sess.flush()
            db_sess.commit()
            db_sess.refresh(new_cls)
            
        return new_cls

    async def refresh(self, session: Optional[AsyncSession] = None, **kwargs):
        """
        Refresh a record
        """
        # async with PostgresDB.async_session(session = session) as db_sess:
        #     query = sqlalchemy_update(self.__class__).where(
        #         self.__class__.id == self.id)
        #     self = (await db_sess.execute(query)).scalar_one_or_none()
            # await db_sess.expire(self)
            # local_object = await db_sess.merge(self)
            # db_sess.add(local_object)
            # await db_sess.commit()
            # await db_sess.refresh(local_object)

        # self = local_object
        # return local_object
    
        async with PostgresDB.async_session() as db_sess:
            # await db_sess.expire(self)
            local_object = await db_sess.merge(self)
            db_sess.add(local_object)
            await db_sess.commit()
            await db_sess.refresh(local_object)

            self = local_object
        # return local_object
    
    async def _update(self, **kwargs):
        """
        Update a record
        """
        async with PostgresDB.async_session() as db_sess:
            query = sqlalchemy_update(self.__class__).where(
                self.__class__.id == self.id).values(
                **kwargs
            )
            await db_sess.execute(query)
            await db_sess.commit()

            # refresh attributes
        self = await self.get(id = self.id)
        # return self
        # await db_sess.refresh(self)

    
    async def update_inplace(self, **kwargs):
        """
        Update a record inplace
        """
        async with PostgresDB.async_session() as db_sess:
            local_object = await db_sess.merge(self)
            db_sess.add(local_object)
            await db_sess.refresh(local_object)
            await db_sess.commit()
            await db_sess.flush()
            self = local_object
        return self
    
    async def save(self, **kwargs):
        """
        Save a record
        """
        async with PostgresDB.async_session() as db_sess:
            local_object = await db_sess.merge(self)
            db_sess.add(local_object)
            await db_sess.refresh(local_object)
            await db_sess.commit()
        
        self = local_object
        return self

    async def update(self, **kwargs) -> Type['AsyncORMType']:
        """
        Update a record
        """
        filtered_update = self._filter_update_data(**kwargs)
        if not filtered_update: return self
        async with PostgresDB.async_session() as db_sess:
            for field, value in filtered_update.items():
                setattr(self, field, value)

            local_object = await db_sess.merge(self)
            db_sess.add(local_object)
            await db_sess.refresh(local_object)
            await db_sess.commit()
        
        self = local_object
        return self


    @classmethod
    async def get(
        cls, 
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
        raise_exceptions: Optional[bool] = True,
        _model_type: Optional[ModelType] = None,
        _verbose: Optional[bool] = False,
        **kwargs,
    ) -> Type['AsyncORMType']:
        """
        Get a record
        """
        async with PostgresDB.async_session(ro=readonly) as db_sess:
            query = cls._build_query(load_attrs = load_attrs, load_attr_method = load_attr_method, **kwargs)
            result = (await db_sess.execute(query)).scalar_one_or_none()
            if not result and raise_exceptions:
                cls._handle_exception(e = NoResultFound(), verbose = _verbose)
            if result is not None and _model_type is not None: result = cast(_model_type, result)
        return result
    
    @classmethod
    def _get(
        cls, 
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
        raise_exceptions: Optional[bool] = True,
        _model_type: Optional[ModelType] = None,
        _verbose: Optional[bool] = False,
        **kwargs,
    ) -> Type['AsyncORMType']:
        """
        Get a record
        """
        with PostgresDB.session(ro=readonly) as db_sess:
            query = cls._build_query(load_attrs = load_attrs, load_attr_method = load_attr_method, **kwargs)
            result = (db_sess.execute(query)).scalar_one_or_none()
            if not result and raise_exceptions:
                cls._handle_exception(e = NoResultFound(), verbose = _verbose)
            if result is not None and _model_type is not None: result = cast(_model_type, result)
        return result

    @classmethod
    async def get_all(
        cls,
        skip: Optional[int] = None, 
        limit: Optional[int] = None,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
        raise_exceptions: Optional[bool] = True,
        _model_type: Optional[ModelType] = None,
        **kwargs,
    ) -> List[Type['AsyncORMType']]:
        """
        Get all records
        """
        async with PostgresDB.async_session(ro=readonly) as db_sess:
            query = cls._build_query(load_attrs = load_attrs, load_attr_method = load_attr_method, **kwargs)
            if skip is not None: query = query.offset(skip)
            if limit is not None: query = query.limit(limit)
            results = (await db_sess.scalars(query)).all()
            if not results and raise_exceptions:
                cls._handle_exception(e = NoResultFound())
            if results is not None and _model_type is not None: results = cast(List[_model_type], results)
        return results


    @classmethod
    async def first(
        cls, 
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly: Optional[bool] = False,
        raise_exceptions: Optional[bool] = True,
        _model_type: Optional[ModelType] = None,
        **kwargs
    ) -> Optional[Union[Type['AsyncORMType'], ModelType]]:
        """
        Return the first result of a query.
        """
        async with PostgresDB.async_session(ro=readonly) as db_sess:
            query = cls._build_query(load_attrs = load_attrs, load_attr_method = load_attr_method, **kwargs)
            result = (await db_sess.scalars(query)).first()
            if not result and raise_exceptions:
                cls._handle_exception(e = NoResultFound())
            if result is not None and _model_type is not None: result = cast(_model_type, result)
        return result
    
    
    @classmethod
    async def delete(cls, **kwargs) -> Type['AsyncORMType']:
        """
        Delete a record
        """
        obj = await cls.get(**kwargs, raise_exceptions = True)
        async with PostgresDB.async_session() as db_sess:
            db_sess.delete(obj)
            await db_sess.commit()
        return obj
    
    @classmethod
    async def delete_all(cls):
        async with PostgresDB.async_session() as db_sess:
            query = sqlalchemy_delete(cls)
            await db_sess.execute(query)
            await db_sess.commit()
    
    @classmethod
    async def exists(cls, **kwargs) -> bool:
        """
        Return True if a record exists
        """
        async with PostgresDB.async_session(ro=True) as db_sess:
            query = cls._filter(sqlalchemy_exists(), **kwargs).select()
            res = await db_sess.scalar(query)
            # logger.info(f"{cls.__name__} Exists: {res} | {kwargs}")
        return res
        # return bool(await db_sess.scalar(query))

        
    @classmethod
    async def count(
        cls, 
        readonly: Optional[bool] = True,
        **kwargs
    ) -> int:
        """
        Count the number of records in the table.
        """
        query = cls._filter(**kwargs) \
            if kwargs else select(func.count(cls.id))
        try:
            async with PostgresDB.async_session(ro=readonly) as db_sess:
                return await db_sess.scalar(query)
        except Exception as e:
            logger.error(e)
            return 0

    
    def dict(
        self,
        exclude: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
        safe_encode: Optional[bool] = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Return a dictionary representation of the model.
        """
        data = self.pydantic_model.dict(
            exclude=exclude,
            include=include,
            **kwargs
        )
        if safe_encode: data = {key: object_serializer(value) for key, value in data.items()}
        return data
    
    def json(
        self,
        exclude: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
        exclude_none: Optional[bool] = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Return a dictionary representation of the model.
        """
        return self.pydantic_model.json(
            exclude=exclude,
            include=include,
            exclude_none=exclude_none,
            **kwargs
        )

    def diff(
        self,
        other: Union[Any, 'AsyncORMType']
    ) -> Dict[str, Any]:
        """
        Return a dictionary of the differences between this model and another.
        """
        return {
            key: value
            for key, value in self.dict().items()
            if key in other.dict() and self.dict()[key] != other.dict()[key]
        }
    
    @lazyproperty
    def pydantic_model(self) -> Type[BaseModel]:
        """
        Return the Pydantic model for this ORM model.
        """
        return get_pydantic_model(self)

    
    @classmethod
    async def get_or_create(
        cls, 
        filterby: Optional[Iterable[str]] = None,
        **kwargs
    ) -> Tuple[Type['AsyncORMType'], bool]:
        """
        Create a new instance of the model, or return the existing one.
        """
        filterby = [list(kwargs.keys())[0]] if filterby is None else filterby
        _filterby = {key: kwargs.get(key) for key in filterby}
        result = await cls.get(**_filterby, raise_exceptions = False, _verbose = False)
        if result is not None: return result, False
        return await cls.create(**kwargs), True
        # try:
        #     return await cls.get(**kwargs), False
        # except NoResultFound:
        #     _defaults = _defaults or {}
        #     return await cls.create(**{**kwargs, **_defaults}), True

    @classmethod
    def register(
        cls, 
        filterby: Optional[Iterable[str]] = None,
        **kwargs
    ) -> Tuple[Type['AsyncORMType'], bool]:
        """
        Create a new instance of the model, or return the existing one.

        Non-async version of `get_or_create` for use in synchronous code.
        """
        filterby = [list(kwargs.keys())[0]] if filterby is None else filterby
        _filterby = {key: kwargs.get(key) for key in filterby}
        result = cls._get(**_filterby, raise_exceptions = False, _verbose = False)
        return (result, False) if result is not None else (cls._create(**kwargs), True)
            
    @classmethod
    async def get_or_none(cls, **kwargs) -> Optional[Type['AsyncORMType']]:
        """
        Return an instance of the model, or None.
        """
        return await cls.get(**kwargs, raise_exceptions = False, _verbose = False)
        # try:
        #     return await cls.get(cls, **kwargs)
        # except NoResultFound:
        #     return None
    
    @classmethod
    async def get_or_create_or_update(
        cls, 
        filterby: Optional[Iterable[str]] = None,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        **kwargs: Dict
    ) -> Tuple[Type['AsyncORMType'], bool]:
        """
        Create a new instance of the model, 
        or return the existing one after updating it.

        filterby: A list of fields to filter by when checking for an existing record.

        Returns a tuple of (instance, created | updated), where created is a boolean
        """
        filterby = [list(kwargs.keys())[0]] if filterby is None else filterby
        _filterby = {key: kwargs.get(key) for key in filterby}
        result = await cls.get(**_filterby, raise_exceptions = False, _verbose = False, load_attrs = load_attrs, load_attr_method = load_attr_method)
        if result is None: 
            new_cls = await cls.create(**kwargs)

            return new_cls, True
        if update_data := result._filter_update_data(**kwargs):
            return (await result.update(**update_data), True)
        return (result, False)
    
        
    @classmethod
    async def create_or_update(
        cls, 
        filterby: Optional[Iterable[str]] = None,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        **kwargs
    ) -> Tuple[Type['AsyncORMType'], bool]:
        """
        Create a new instance of the model, 
        or return the existing one after updating it.

        Returns a tuple of (instance, (true: created or updated, false: not updated), where created is a boolean
        """
        filterby = [list(kwargs.keys())[0]] if filterby is None else filterby
        _filterby = {key: kwargs.get(key) for key in filterby}
        # if await cls.exists(**_filterby):
        result = await cls.get(**_filterby, raise_exceptions = False, _verbose = False, load_attrs = load_attrs, load_attr_method = load_attr_method)
        if result is None: 
            return await cls.create(**kwargs), True
        if update_data := result._filter_update_data(**kwargs):
            logger.info(f"Updating {result} with {update_data}")
            return (await result.update(**update_data), True)
        return (result, False)
    

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.dict()})>"
    


    
# SQLModelT = Type['SQLModel']
SQLModelT = TypeVar('SQLModelT', bound = 'SQLModel')

class SQLModel(Base):
    """
    Abstract base class for all SQL models.
    """
    __abstract__ = True
    __allow_unmapped__ = True
    
    
    id: str = Column(Text, default = create_unique_id, primary_key = True, index = True, unique = True)
    created_at = Column(DateTime(timezone=True), default = create_timestamp, server_default = func.now())
    updated_at = Column(DateTime(timezone=True), default = create_timestamp, server_default = func.now(), onupdate = create_timestamp)

    """
    Core Methods
    """

    @classmethod
    async def create(
        cls, 
        session: Optional[AsyncSession] = None,
        **kwargs
    ) -> SQLModelT:
        """
        Create a new instance of the model
        """
        async with PostgresDB.async_session(session = session) as db_sess:
            new_cls = cls(**kwargs)
            db_sess.add(new_cls)
            await db_sess.flush()
            await db_sess.commit()
            await db_sess.refresh(new_cls)
        return new_cls

    @classmethod
    def _create(
        cls: SQLModelT, 
        session: Optional[Session] = None,
        **kwargs
    ) -> SQLModelT:
        """
        Create a new instance of the model
        """
        with PostgresDB.session(session = session) as db_sess:
            new_cls = cls(**kwargs)
            db_sess.add(new_cls)
            db_sess.flush()
            db_sess.commit()
            db_sess.refresh(new_cls)
            
        return new_cls
    

    async def refresh(
        self, 
        session: Optional[AsyncSession] = None,
        **kwargs
    ):
        """
        Refresh a record
        """
        async with PostgresDB.async_session(session = session) as db_sess:
            # await db_sess.expire(self)
            local_object = await db_sess.merge(self)
            db_sess.add(local_object)
            await db_sess.commit()
            await db_sess.refresh(local_object)

        self = local_object
        return local_object
    
    async def _update(
        self, 
        session: Optional[AsyncSession] = None,
        **kwargs
    ):
        """
        Update a record
        """
        async with PostgresDB.async_session(session = session) as db_sess:
            query = sqlalchemy_update(self.__class__).where(
                self.__class__.id == self.id).values(
                **kwargs
            )
            await db_sess.execute(query)
            await db_sess.commit()

            # refresh attributes
        self = await self.get(id = self.id)
        # return self
        # await db_sess.refresh(self)

    
    async def update_inplace(
        self, 
        session: Optional[AsyncSession] = None,
        **kwargs
    ):
        """
        Update a record inplace
        """
        async with PostgresDB.async_session(session = session) as db_sess:
            local_object = await db_sess.merge(self)
            db_sess.add(local_object)
            # await db_sess.refresh(local_object)
            await db_sess.commit()
            await db_sess.flush()
            self = local_object
        return self
    
    async def save(self, **kwargs):
        """
        Save a record
        """
        async with PostgresDB.async_session() as db_sess:
            local_object = await db_sess.merge(self)
            db_sess.add(local_object)
            # logger.info(f"Saving {local_object}")
            # await db_sess.refresh(local_object)
            await db_sess.commit()
            self = local_object
        return self

    async def update(self, session: Optional[AsyncSession] = None, **kwargs) -> Type['AsyncORMType']:
        """
        Update a record
        """
        filtered_update = self._filter_update_data(**kwargs)
        if not filtered_update: return self
        async with PostgresDB.async_session(session = session) as db_sess:
            for field, value in filtered_update.items():
                setattr(self, field, value)

            local_object = await db_sess.merge(self)
            db_sess.add(local_object)
            await db_sess.refresh(local_object)
            # if session is None: 
            await db_sess.commit()
        
            self = local_object
        return self


    @classmethod
    async def get(
        cls: SQLModelT, 
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
        raise_exceptions: Optional[bool] = True,
        session: Optional[AsyncSession] = None,
        _model_type: Optional[ModelType] = None,
        _verbose: Optional[bool] = False,
        **kwargs,
    ) -> SQLModelT:
        """
        Get a record
        """
        async with PostgresDB.async_session(ro=readonly, session = session) as db_sess:
            query = cls._build_query(load_attrs = load_attrs, load_attr_method = load_attr_method, **kwargs)
            result = (await db_sess.execute(query)).scalar_one_or_none()
            if not result and raise_exceptions:
                cls._handle_exception(e = NoResultFound(), verbose = _verbose)
            if result is not None and _model_type is not None: result = cast(_model_type, result)
        return result
    

    @classmethod
    async def get_only_one(
        cls: SQLModelT, 
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
        raise_exceptions: Optional[bool] = True,
        session: Optional[AsyncSession] = None,
        _model_type: Optional[ModelType] = None,
        _verbose: Optional[bool] = False,
        **kwargs,
    ) -> SQLModelT:
        """
        Get a record
        """
        async with PostgresDB.async_session(ro=readonly, session = session) as db_sess:
            query = cls._build_query(load_attrs = load_attrs, load_attr_method = load_attr_method, **kwargs)
            query = query.order_by(cls.created_at.desc())
            # result = (await db_sess.execute(query)).scalar_one_or_none()
            result = (await db_sess.scalars(query)).all()
            # logger.warning(f"Found {len(result)} results for {cls.__name__} with {kwargs}: {result}")
            if not result and raise_exceptions:
                cls._handle_exception(e = NoResultFound(), verbose = _verbose)
            if len(result) > 1:
                # Keep the latest one
                kept_result = result[0]
                if _verbose: logger.warning(f"Found {len(result)} results for {cls.__name__} with {kwargs}. Keeping {kept_result.id}")
                # Delete the rest
                for res in result[1:]:
                    await db_sess.delete(res)
                # await db_sess.flush()
                await db_sess.commit()
                result = kept_result
            elif result:
                result = result[0]
            else:
                result = None
            if result is not None and _model_type is not None: result = cast(_model_type, result)
        return result
    
    @classmethod
    def _get(
        cls: SQLModelT, 
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
        raise_exceptions: Optional[bool] = True,
        session: Optional[Session] = None,
        _model_type: Optional[ModelType] = None,
        _verbose: Optional[bool] = False,
        **kwargs,
    ) -> SQLModelT:
        """
        Get a record
        """
        with PostgresDB.session(ro=readonly, session = session) as db_sess:
            query = cls._build_query(load_attrs = load_attrs, load_attr_method = load_attr_method, **kwargs)
            result = (db_sess.execute(query)).scalar_one_or_none()
            if not result and raise_exceptions:
                cls._handle_exception(e = NoResultFound(), verbose = _verbose)
            if result is not None and _model_type is not None: result = cast(_model_type, result)
        return result

    @classmethod
    async def get_all(
        cls: SQLModelT,
        skip: Optional[int] = None, 
        limit: Optional[int] = None,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
        raise_exceptions: Optional[bool] = True,
        _model_type: Optional[ModelType] = None,
        **kwargs,
    ) -> List[SQLModelT]:
        """
        Get all records
        """
        async with PostgresDB.async_session(ro=readonly) as db_sess:
            query = cls._build_query(load_attrs = load_attrs, load_attr_method = load_attr_method, **kwargs)
            if skip is not None: query = query.offset(skip)
            if limit is not None: query = query.limit(limit)
            results = (await db_sess.scalars(query)).all()
            if not results and raise_exceptions:
                cls._handle_exception(e = NoResultFound())
            if results is not None and _model_type is not None: results = cast(List[_model_type], results)
        return results


    @classmethod
    async def first(
        cls, 
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly: Optional[bool] = False,
        raise_exceptions: Optional[bool] = True,
        _model_type: Optional[ModelType] = None,
        **kwargs
    ) -> Optional[Union[SQLModelT, ModelType]]:
        """
        Return the first result of a query.
        """
        async with PostgresDB.async_session(ro=readonly) as db_sess:
            query = cls._build_query(load_attrs = load_attrs, load_attr_method = load_attr_method, **kwargs)
            result = (await db_sess.scalars(query)).first()
            if not result and raise_exceptions:
                cls._handle_exception(e = NoResultFound())
            if result is not None and _model_type is not None: result = cast(_model_type, result)
        return result
    
    
    @classmethod
    async def delete(cls, **kwargs) -> SQLModelT:
        """
        Delete a record
        """
        obj = await cls.get(**kwargs, raise_exceptions = True)
        async with PostgresDB.async_session() as db_sess:
            await db_sess.delete(obj)
            await db_sess.commit()
        return obj
    
    @classmethod
    async def delete_all(cls):
        async with PostgresDB.async_session() as db_sess:
            query = sqlalchemy_delete(cls)
            await db_sess.execute(query)
            await db_sess.commit()
    
    @classmethod
    async def exists(cls, session: Optional[AsyncSession] = None, **kwargs) -> bool:
        """
        Return True if a record exists
        """
        async with PostgresDB.async_session(ro=True, session = session) as db_sess:
            query = cls._filter(sqlalchemy_exists(), **kwargs).select()
            res = await db_sess.scalar(query)
            # logger.info(f"{cls.__name__} Exists: {res} | {kwargs}")
        return res
        # return bool(await db_sess.scalar(query))

        
    @classmethod
    async def count(
        cls, 
        readonly: Optional[bool] = True,
        **kwargs
    ) -> int:
        """
        Count the number of records in the table.
        """
        query = cls._filter(**kwargs) \
            if kwargs else select(func.count(cls.id))
        try:
            async with PostgresDB.async_session(ro=readonly) as db_sess:
                return await db_sess.scalar(query)
        except Exception as e:
            logger.error(e)
            return 0

    
    def dict(
        self,
        exclude: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
        safe_encode: Optional[bool] = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Return a dictionary representation of the model.
        """
        data = self.pydantic_model.dict(
            exclude=exclude,
            include=include,
            **kwargs
        )
        if safe_encode: data = {key: object_serializer(value) for key, value in data.items()}
        return data
    
    def json(
        self,
        exclude: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
        exclude_none: Optional[bool] = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Return a dictionary representation of the model.
        """
        return self.pydantic_model.json(
            exclude=exclude,
            include=include,
            exclude_none=exclude_none,
            **kwargs
        )

    def diff(
        self,
        other: Union[Any, 'SQLModel'],
    ) -> Dict[str, Any]:
        """
        Return a dictionary of the differences between this model and another.
        """
        return {
            key: value
            for key, value in self.dict().items()
            if key in other.dict() and self.dict()[key] != other.dict()[key]
        }
    
    def sqlmodel_dict(
        self, 
        exclude: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
        exclude_none: Optional[bool] = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Return a dictionary representation of the model.
        """
        model_dict = get_sqlmodel_dict(self)
        if exclude is not None: model_dict = {key: value for key, value in model_dict.items() if key not in exclude}
        if include is not None: model_dict = {key: value for key, value in model_dict.items() if key in include}
        if exclude_none: model_dict = {key: value for key, value in model_dict.items() if value is not None}
        return model_dict

    @lazyproperty
    def pydantic_model(self) -> Type[BaseModel]:
        """
        Return the Pydantic model for this ORM model.
        """
        return get_pydantic_model(self)

    
    @classmethod
    async def get_or_create(
        cls, 
        filterby: Optional[Iterable[str]] = None,
        session: Optional[AsyncSession] = None,
        **kwargs
    ) -> Tuple[SQLModelT, bool]:
        """
        Create a new instance of the model, or return the existing one.
        """
        filterby = [list(kwargs.keys())[0]] if filterby is None else filterby
        _filterby = {key: kwargs.get(key) for key in filterby}
        # async with PostgresDB.async_session(session = session) as db_sess:
        result = await cls.get(
            raise_exceptions = False, 
            _verbose = False, 
            session = session,
            **_filterby, 
        )
        if result is not None: return result, False
        return await cls.create(
            session = session, 
            **kwargs
        ), True
    

    @classmethod
    def register(
        cls: SQLModelT, 
        filterby: Optional[Iterable[str]] = None,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        session: Optional[Session] = None,
        **kwargs
    ) -> Tuple[SQLModelT, bool]:
        """
        Create a new instance of the model, or return the existing one.

        Non-async version of `get_or_create` for use in synchronous code.
        """
        filterby = [list(kwargs.keys())[0]] if filterby is None else filterby
        _filterby = {key: kwargs.get(key) for key in filterby}
        with PostgresDB.session(session = session) as db_sess:
            result = cls._get(**_filterby, raise_exceptions = False, _verbose = False, session = db_sess, load_attrs = load_attrs, load_attr_method = load_attr_method)
            return (result, False) if result is not None else (cls._create(session = db_sess, **kwargs), True)
            
    @classmethod
    async def get_or_none(cls: SQLModelT, session: Optional[AsyncSession] = None, **kwargs) -> Optional[SQLModelT]:
        """
        Return an instance of the model, or None.
        """
        return await cls.get(**kwargs, session = session, raise_exceptions = False, _verbose = False)
        # try:
        #     return await cls.get(cls, **kwargs)
        # except NoResultFound:
        #     return None
    
    @classmethod
    async def get_or_create_or_update(
        cls: SQLModelT, 
        filterby: Optional[Iterable[str]] = None,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        session: Optional[AsyncSession] = None,
        _only_new: Optional[bool] = False,
        **kwargs: Dict
    ) -> Tuple[SQLModelT, bool]:
        """
        Create a new instance of the model, 
        or return the existing one after updating it.

        filterby: A list of fields to filter by when checking for an existing record.

        Returns a tuple of (instance, created | updated), where created is a boolean
        """
        # filterby = [list(kwargs.keys())[0]] if filterby is None else filterby
        filterby = list(kwargs.keys()) if filterby is None else filterby
        _filterby = {key: kwargs.get(key) for key in filterby}
        # async with PostgresDB.async_session(session = session) as db_sess:
        # result = await cls.get(
        result = await cls.get_only_one(
            load_attrs = load_attrs,
            load_attr_method = load_attr_method,
            session = session, 
            raise_exceptions = False, 
            _verbose = False,
            **_filterby, 
        )
        if result is None: 
            new_cls = await cls.create(
                session = session,
                **kwargs, 
            )
            return new_cls, True
        if update_data := result._filter_update_data(**kwargs):
            return (
                await result.update(
                    session = session, 
                    **update_data
                ), (False if _only_new else True))
        return (result, False)
    
        
    @classmethod
    async def create_or_update(
        cls: SQLModelT, 
        filterby: Optional[Iterable[str]] = None,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        session: Optional[AsyncSession] = None,
        _only_new: Optional[bool] = False,
        **kwargs
    ) -> Tuple[SQLModelT, bool]:
        """
        Create a new instance of the model, 
        or return the existing one after updating it.

        Returns a tuple of (instance, (true: created or updated, false: not updated), where created is a boolean
        """
        filterby = [list(kwargs.keys())[0]] if filterby is None else filterby
        _filterby = {key: kwargs.get(key) for key in filterby}
        # async with PostgresDB.async_session(session = session) as db_sess:
        result = await cls.get(
            **_filterby, 
            load_attrs = load_attrs,
            load_attr_method = load_attr_method,
            session = session, 
            raise_exceptions = False, 
            _verbose = False
        )
        if result is None: 
            return await cls.create(
                session = session, 
                **kwargs
            ), True
        if update_data := result._filter_update_data(**kwargs):
            logger.info(f"Updating {result} with {update_data}")
            return (
                await result.update(
                session = session, 
                **update_data
                ), (False if _only_new else True)
            )
        return (result, False)
    

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.dict()})>"
    
    def _supdate(
        self, 
        session: Optional[Session] = None,
        **kwargs
    ):
        """
        Update a record
        """
        with PostgresDB.session(session = session) as db_sess:
            query = sqlalchemy_update(self.__class__).where(
                self.__class__.id == self.id).values(
                **kwargs
            )
            db_sess.execute(query)
            db_sess.commit()

            # refresh attributes
        return self._get(id = self.id)


    def supdate(self, session: Optional[Session] = None, **kwargs):
        """
        Update a record
        """
        filtered_update = self._filter_update_data(**kwargs)
        if not filtered_update: return self
        with PostgresDB.session(session = session) as db_sess:
            for field, value in filtered_update.items():
                setattr(self, field, value)

            local_object = db_sess.merge(self)
            db_sess.add(local_object)
            db_sess.refresh(local_object)
            db_sess.commit()
            self = local_object
        return self

    @classmethod
    def query(
        cls: SQLModelT,
        query: str,
        session: Optional[Session] = None,
        **kwargs
    ) -> Any:
        """
        Executes a text query
        """
        with PostgresDB.session(session = session) as db_sess:
            query = query.replace('[table]', cls.__tablename__)
            stmt = text(query)
            result = db_sess.execute(stmt, kwargs)
            db_sess.commit()
        return result

    @classmethod
    async def aquery(
        cls: SQLModelT,
        query: str,
        session: Optional[AsyncSession] = None,
        **kwargs
    ) -> Any:
        """
        Executes a text query
        """
        async with PostgresDB.async_session(session = session) as db_sess:
            query = query.replace('[table]', cls.__tablename__)
            stmt = text(query)
            result = await db_sess.execute(stmt, kwargs)
            await db_sess.commit()
        return result

    @classmethod
    def _get_or_create(
        cls: SQLModelT, 
        filterby: Optional[Iterable[str]] = None,
        session: Optional[Session] = None,
        **kwargs
    ) -> Tuple[SQLModelT, bool]:
        """
        Create a new instance of the model, or return the existing one.
        """
        filterby = [list(kwargs.keys())[0]] if filterby is None else filterby
        _filterby = {key: kwargs.get(key) for key in filterby}
        # async with PostgresDB.async_session(session = session) as db_sess:
        result = cls._get(
            raise_exceptions = False, 
            _verbose = False, 
            session = session,
            **_filterby, 
        )
        if result is not None: return result, False
        return cls._create(
            session = session, 
            **kwargs
        ), True

    @classmethod
    def _get_or_create_or_update(
        cls: SQLModelT, 
        filterby: Optional[Iterable[str]] = None,
        session: Optional[Session] = None,
        _only_new: Optional[bool] = False,
        **kwargs: Dict
    ) -> Tuple[SQLModelT, bool]:
        """
        Create a new instance of the model, 
        or return the existing one after updating it.

        filterby: A list of fields to filter by when checking for an existing record.

        Returns a tuple of (instance, created | updated), where created is a boolean
        """
        filterby = [list(kwargs.keys())[0]] if filterby is None else filterby
        _filterby = {key: kwargs.get(key) for key in filterby}
        # async with PostgresDB.async_session(session = session) as db_sess:
        result = cls._get(
            session = session, 
            raise_exceptions = False, 
            _verbose = False,
            **_filterby, 
        )
        if result is None: 
            new_cls = cls._create(
                session = session,
                **kwargs, 
            )
            return new_cls, True
        if update_data := result._filter_update_data(**kwargs):
            return (
                result._supdate(
                    session = session, 
                    **update_data
                ), (False if _only_new else True))
        return (result, False)

    @classmethod
    def _exists(cls, session: Optional[Session] = None, **kwargs) -> bool:
        """
        Return True if a record exists
        """
        with PostgresDB.session(ro=True, session = session) as db_sess:
            query = cls._filter(sqlalchemy_exists(), **kwargs).select()
            res = db_sess.scalar(query)
        return res
    
    @classmethod
    def _get_or_none(cls, session: Optional[Session] = None, **kwargs) -> Optional[SQLModelT]:
        """
        Return an instance of the model, or None.
        """
        return cls._get(**kwargs, session = session, raise_exceptions = False, _verbose = False)

    """
    Utility Methods
    """
    
    @classmethod
    def _filter(
        cls: SQLModelT, 
        query: Optional[Select] = None, 
        **kwargs
    ) -> Select:
        """
        Build a filter query
        """
        query = query if query is not None else select(cls)
        return query.where(*[getattr(cls, key) == value for key, value in kwargs.items()])

    @classmethod
    def _nested_kwarg_parser(
        cls: SQLModelT,
        top_level_obj: Optional[SQLModelT] = None,
        **kwargs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Parses nested dict kwargs into a flat dict
        """
        attrs = []
        for key, value in kwargs.items():
            obj_attr = getattr(cls, key, None) if top_level_obj is None else getattr(top_level_obj, key, None)
            if obj_attr is None: continue
            if isinstance(value, dict):
                attrs.append(obj_attr.has(**value))
                # attrs.extend(cls._nested_kwarg_parser(top_level_obj, **value))
            else:
                attrs.append(obj_attr == value)
        logger.warning(f'{attrs}')
        return attrs

    @classmethod
    def _build_query(
        cls: SQLModelT,
        query: Optional[Select] = None,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        **kwargs
    ) -> Select:
        """
        Build a query
        """
        query = query if query is not None else select(cls)
        query = query.where(*[getattr(cls, key) == value for key, value in kwargs.items()])
        # query = query.where(*cls._nested_kwarg_parser(**kwargs))
        if load_attrs:
            load_attr_method = get_attr_func(load_attr_method)
            for attr in load_attrs:
                query = query.options(load_attr_method(getattr(cls, attr)))
        return query

    def _filter_update_data(self, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Filter update data
        """
        data = {}
        for field, value in kwargs.items():
            if not hasattr(self, field): continue
            with contextlib.suppress(ValueError):
                if hasattr(value, 'all') and hasattr(getattr(self, field), 'all') \
                    and getattr(self, field).all() == value.all():
                    continue

                if getattr(self, field) == value: 
                    # logger.warning(f"Skipping {field}={getattr(self, field)} as value is the same: {value}")
                    continue
            
            data[field] = value
        return data or None

    @classmethod
    def _handle_exception(
        cls, 
        msg: Optional[str] = None, 
        e: Optional[Exception] = None, 
        verbose: Optional[bool] = False
    ):
        """
        Handle exception
        """
        msg = msg or f"{cls.__name__} not found"
        if verbose: logger.trace(msg, error = e)
        raise e or HTTPException(status_code = 404, detail = msg)

    

