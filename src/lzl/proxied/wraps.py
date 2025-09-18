from __future__ import annotations

"""Utility decorator for creating lazily initialised proxy objects."""

import typing as t

from .base import ProxyObject

ObjT = t.TypeVar("ObjT")
ProxyObjT = t.Type[ObjT]


@t.overload
def proxied(
    obj_cls: t.Optional[ObjT] = None,
    obj_getter: t.Optional[t.Union[t.Callable[..., ObjT], str]] = None,
    obj_args: t.Optional[t.List[t.Any]] = None,
    obj_kwargs: t.Optional[t.Dict[str, t.Any]] = None,
    obj_initialize: t.Optional[bool] = True,
    threadsafe: t.Optional[bool] = True,
) -> ObjT:
    ...


@t.overload
def proxied(
    **kwargs: t.Any,
) -> t.Callable[..., ObjT]:
    ...


def proxied(
    obj_cls: t.Optional[ObjT] = None,
    obj_getter: t.Optional[t.Union[t.Callable[..., ObjT], str]] = None,
    obj_args: t.Optional[t.List[t.Any]] = None,
    obj_kwargs: t.Optional[t.Dict[str, t.Any]] = None,
    obj_initialize: t.Optional[bool] = True,
    threadsafe: t.Optional[bool] = True,
) -> t.Union[t.Callable[..., ObjT], ObjT]:
    """Return a proxy that defers constructing ``obj_cls`` until first use."""

    if obj_cls is not None:
        return ProxyObject(
            obj_cls=obj_cls,
            obj_getter=obj_getter,
            obj_args=obj_args,
            obj_kwargs=obj_kwargs,
            obj_initialize=obj_initialize,
            threadsafe=threadsafe,
        )

    def wrapper(inner_cls: ObjT) -> ProxyObjT:
        return ProxyObject(
            obj_cls=inner_cls,
            obj_getter=obj_getter,
            obj_args=obj_args,
            obj_kwargs=obj_kwargs,
            obj_initialize=obj_initialize,
            threadsafe=threadsafe,
        )

    return wrapper


__all__ = ["proxied", "ObjT", "ProxyObjT"]
