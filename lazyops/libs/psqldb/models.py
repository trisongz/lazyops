
from sqlalchemy import func
from sqlalchemy import delete as sqlalchemy_delete
from sqlalchemy import update as sqlalchemy_update
from sqlalchemy.future import select
from sqlalchemy.sql.expression import Select
from sqlalchemy.orm import selectinload, joinedload, immediateload
from typing import Any, Generator, AsyncGenerator, Optional, Union, Type, Dict, cast, TYPE_CHECKING, List, Tuple, TypeVar, Callable
from lazyops.utils.logs import logger
from lazyops.libs.psqldb.base import Base, PostgresDB, AsyncSession, Session

ModelType = TypeVar("ModelType", bound = Base)

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
    def create(cls, **kwargs):
        new_cls = cls(**kwargs)
        with PostgresDB.session() as db_sess:
            db_sess.add(new_cls)
            db_sess.commit()
            db_sess.refresh(new_cls)
        return new_cls
    
    async def acreate(cls, **kwargs):
        async with PostgresDB.async_session() as db_sess:
            new_cls = cls(**kwargs)
            db_sess.add(new_cls)
            await db_sess.commit()
            await db_sess.refresh(new_cls)
        return new_cls
    
    @classmethod
    def update(cls, id: Any, **kwargs):
        with PostgresDB.session() as db_sess:
            query = (
                sqlalchemy_update(cls)
                .where(cls.id == id)
                .values(**kwargs)
                .execution_options(synchronize_session="fetch")
            )
            db_sess.execute(query)
            db_sess.commit()
    
    @classmethod
    async def aupdate(cls, id: Any, **kwargs):
        async with PostgresDB.async_session() as db_sess:
            query = (
                sqlalchemy_update(cls)
                .where(cls.id == id)
                .values(**kwargs)
                .execution_options(synchronize_session="fetch")
            )
            await db_sess.execute(query)
            await db_sess.commit()

    @classmethod
    def get(
        cls, 
        value: Any, 
        key: str = "id", 
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
    ):
        with PostgresDB.session(ro=readonly) as db_sess:
            query = select(cls).where(getattr(cls, key) == value)
            if load_attrs:
                load_attr_method = get_attr_func(load_attr_method)
                for attr in load_attrs:
                    query = query.options(load_attr_method(getattr(cls, attr)))
            results = db_sess.execute(query)
            (result,) = results.one()
            return result

    @classmethod
    async def aget(
        cls, 
        value: Any, 
        key: str = "id",
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
    ):
        async with PostgresDB.async_session(ro=readonly) as db_sess:
            query = select(cls).where(getattr(cls, key) == value)
            if load_attrs:
                load_attr_method = get_attr_func(load_attr_method)
                for attr in load_attrs:
                    query = query.options(load_attr_method(getattr(cls, attr)))
            results = await db_sess.execute(query)
            (result,) = results.one()
            return result

    @classmethod
    def get_all(
        cls,
        load_attrs: Optional[List[str]] = None,
        load_attr_method: Optional[Union[str, Callable]] = None,
        readonly : Optional[bool] = False,
    ):
        with PostgresDB.session(ro=readonly) as db_sess:
            query = select(cls)
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
    ):
        async with PostgresDB.async_session(ro=readonly) as db_sess:
            query = select(cls)
            if load_attrs:
                load_attr_method = get_attr_func(load_attr_method)
                for attr in load_attrs:
                    query = query.options(load_attr_method(getattr(cls, attr)))
            results = await db_sess.execute(query)
            return results.scalars().all()
    
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


    @classmethod
    def delete(cls, id: Any):
        with PostgresDB.session() as db_sess:
            query = sqlalchemy_delete(cls).where(cls.id == id)
            db_sess.execute(query)
            db_sess.commit()
    
    @classmethod
    async def async_delete(cls, id: Any):
        async with PostgresDB.async_session() as db_sess:
            query = sqlalchemy_delete(cls).where(cls.id == id)
            await db_sess.execute(query)
            await db_sess.commit()
    
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
    def count(
        cls, 
        owner_id: Optional[Any] = None,
        owner_key: Optional[str] = "owner_id",
        readonly: Optional[bool] = True,

    ) -> int:
        """
        Count the number of records in the table.
        """
        query = select(func.count(cls.id)).filter(getattr(cls, owner_key) == owner_id) \
            if owner_id else select(func.count(cls.id))

        try:
            with PostgresDB.session(ro=readonly) as db_sess:
                return db_sess.scalar(query)
        except Exception as e:
            logger.error(e)
            return 0
        
    @classmethod
    async def acount(
        cls, 
        owner_id: Optional[Any] = None,
        owner_key: Optional[str] = "owner_id",
        readonly: Optional[bool] = True,
    ):
        """
        Count the number of records in the table.
        """

        query = select(func.count(cls.id)).filter(getattr(cls, owner_key) == owner_id) \
            if owner_id else select(func.count(cls.id))
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
        **kwargs
    ) -> Dict[str, Any]:
        """
        Return a dictionary representation of the model.
        """
        if exclude is None:
            exclude = []
        if include is None:
            include = []
        return {
            key: value
            for key, value in self.__dict__.items()
            if key not in exclude and (not include or key in include)
        }
    
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
        res = (await db.scalars(stmt)).first()
        res = cast(model_type, res)
        return res