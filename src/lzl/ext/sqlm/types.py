from __future__ import annotations

"""
SQLModel Extended Types
"""


# from sqlmodel import SQLModel as BaseSQLModel
import functools
from sqlmodel._compat import get_annotations
from pydantic._internal._repr import Representation
from sqlmodel.main import SQLModelMetaclass, Field, FieldInfo, SQLModelConfig, SQLModel as BaseSQLModel
from sqlmodel.main import default_registry
from lzl.types import eproperty, PrivateAttr
from typing import Any, ClassVar, Coroutine, List, Dict, Tuple, TypeVar, Type, Awaitable, Callable, Set, Optional, Union, ClassVar, TYPE_CHECKING
from sqlalchemy.util.concurrency import greenlet_spawn


def schema_extra(schema: dict, _):
    props = {
        k: v
        for k, v in schema.get('properties', {}).items()
        if not v.get("hidden", False) and not k.startswith('_')
    }
    schema["properties"] = props

_T = TypeVar("_T")
def __dataclass_transform__(
    *,
    eq_default: bool = True,
    order_default: bool = False,
    kw_only_default: bool = False,
    field_descriptors: Tuple[Union[type, Callable[..., Any]], ...] = (()),
) -> Callable[[_T], _T]: # type: ignore
    return lambda a: a


class SQLModel(BaseSQLModel):
    """
    SQLModel with additional features
    """
    if not TYPE_CHECKING:
        _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)
        model_config = SQLModelConfig(from_attributes = True, arbitrary_types_allowed = True, json_schema_extra = schema_extra)


_sql_model_init_hooks: Set[Callable[..., Any]] = set()

def add_sql_model_init_hook(func: Callable[..., Any]) -> None:
    """
    Adds an SQLModel Init Hook
    """
    _sql_model_init_hooks.add(func)

def run_sql_model_init_hooks(model: Type['SQLModel']) -> None:
    """
    Runs the SQLModel Init Hooks
    """
    for hook in _sql_model_init_hooks:
        hook(model)

# Adding AsyncSQLModel to the list of SQLModels
# https://github.com/fastapi/sqlmodel/pull/872/files

class AwaitableFieldInfo(Representation):
    def __init__(self, *, field: str):
        self.field = field


def AwaitableField(*, field: str) -> Any:
    return AwaitableFieldInfo(field=field)

@__dataclass_transform__(kw_only_default=True, field_descriptors=(Field, FieldInfo))
class AsyncSQLModelMetaclass(SQLModelMetaclass):
    __async_sqlmodel_awaitable_fields__: Dict[str, AwaitableFieldInfo]

    def __new__(
        cls,
        name: str,
        bases: Tuple[Type[Any], ...],
        class_dict: Dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        awaitable_fields: Dict[str, AwaitableFieldInfo] = {}
        dict_for_sqlmodel = {}
        original_annotations = get_annotations(class_dict)
        sqlmodel_annotations = {}
        awaitable_fields_annotations = {}
        for k, v in class_dict.items():
            if isinstance(v, AwaitableFieldInfo):
                awaitable_fields[k] = v
            else:
                dict_for_sqlmodel[k] = v
        for k, v in original_annotations.items():
            if k in awaitable_fields:
                awaitable_fields_annotations[k] = v
            else:
                sqlmodel_annotations[k] = v

        dict_used = {
            **dict_for_sqlmodel,
            "__async_sqlmodel_awaitable_fields__": awaitable_fields,
            "__annotations__": sqlmodel_annotations,
        }
        return super().__new__(cls, name, bases, dict_used, **kwargs)

    def __init__(
        cls, classname: str, bases: Tuple[type, ...], dict_: Dict[str, Any], **kw: Any
    ) -> None:
        for field_name, field_info in cls.__async_sqlmodel_awaitable_fields__.items():

            def get_awaitable_field(
                self: "AsyncSQLModel", field: str = field_info.field
            ) -> Coroutine[Any, Any, Any]:
                return greenlet_spawn(getattr, self, field)

            setattr(cls, field_name, property(get_awaitable_field))
        
        SQLModelMetaclass.__init__(cls, classname, bases, dict_, **kw)
        run_sql_model_init_hooks(cls)

class AsyncSQLModel(SQLModel, metaclass=AsyncSQLModelMetaclass):
    
    __async_sqlmodel_awaitable_fields__: ClassVar[Dict[str, AwaitableFieldInfo]]


    async def __await_all_fields__(self):
        """
        Await all fields
        """
        field = None
        try:
            for field in self.__async_sqlmodel_awaitable_fields__:
                await getattr(self, field)
        except Exception as e:
            from lzl.logging import logger
            logger.trace(f'Error Awaiting Field: {field}', e)
            raise e

    def __await__(self):
        """
        Await the model fields
        """
        return self.__await_all_fields__().__await__()
    
_SM = TypeVar("_SM", bound=AsyncSQLModel)
_RM = TypeVar("_RM", bound=AsyncSQLModel)

def sqlm_method_wrapper(
    source: _SM,
    source_kws: Optional[List[str]] = None,
    inject_kwargs: Dict[str, Union[Callable, Any]] = None,
    exclude_none: Optional[bool] = True,
    method: Optional[str] = 'create',
    target_validator: Optional[str] = None,
) -> Callable[[_RM], _SM]:
    """
    Wrapper for SQLModel Methods
    """
    source_kws = source_kws or []
    def target_wrapper(target: _RM) -> Callable[[_RM], _SM]:
        """
        Target Wrapper
        """
        def inner_method(**kwargs: Any) -> _SM:
            """
            Inner Method
            """
            target_kws = {k:v for k,v in kwargs.items() if k not in source_kws}
            if exclude_none:
                target_kws = {k:v for k,v in target_kws.items() if v is not None}
            new_target = target(**target_kws)
            update_kwargs = {k:v for k,v in kwargs.items() if k in source_kws}
            if exclude_none:
                update_kwargs = {k:v for k,v in update_kwargs.items() if v is not None}
            if inject_kwargs:
                for k, v in inject_kwargs.items():
                    if callable(v): v = v()
                    update_kwargs[k] = v
            
            return source.model_validate(new_target, update = update_kwargs)
        
        setattr(target, method, inner_method)
        return target
        
    return target_wrapper

