
import threading
import contextlib
from typing import Any, Type, Tuple, Dict, List, Union, Optional, Callable, TypeVar, Generic, TYPE_CHECKING


ProxyObjT = TypeVar('ProxyObjT')


class ProxyObject(Generic[ProxyObjT]):
    def __init__(
        self,
        obj_cls: Optional[Union[Type[ProxyObjT], str]] = None,
        obj_getter: Optional[Union[Callable, str]] = None,
        obj_args: Optional[List[Any]] = None,
        obj_kwargs: Optional[Dict[str, Any]] = None,
        obj_initialize: Optional[bool] = True,
        threadsafe: Optional[bool] = False,
        debug_enabled: Optional[bool] = False,
    ):
        """
        Proxy Object

        args:
            obj_cls: the class of the object
            obj_getter: the function to get the object
            debug_enabled: if True, will raise an error if the object is not found
        """
        # Intentionally underscore on the end to avoid conflicts with the settings
        assert obj_cls or obj_getter, "Either `obj_cls` or `obj_getter` must be provided"
        self.__obj_cls_ = obj_cls
        self.__obj_getter_ = obj_getter
        if self.__obj_getter_ and isinstance(self.__obj_getter_, str):
            from lazyops.utils.helpers import lazy_import
            self.__obj_getter_ = lazy_import(self.__obj_getter_)
        self.__threadlock_ = None if threadsafe else threading.Lock()
        self.__obj_ = None
        self.__obj_args_ = obj_args or []
        self.__obj_kwargs_ = obj_kwargs or {}
        self.__obj_initialize_ = obj_initialize
        self.__debug_enabled_ = debug_enabled
        self.__last_attrs_: Dict[str, int] = {}

    @contextlib.contextmanager
    def _objlock_(self):
        """
        Returns the object lock
        """
        if self.__threadlock_ is not None:
            try:
                with self.__threadlock_:
                    yield
            except Exception as e:
                raise e
        else:
            yield

    @property
    def _obj_(self) -> ProxyObjT:
        """
        Returns the object
        """
        if self.__obj_ is None:
            with self._objlock_():
                if self.__obj_getter_:
                    self.__obj_ = self.__obj_getter_(*self.__obj_args_, **self.__obj_kwargs_)
                elif self.__obj_cls_:
                    if isinstance(self.__obj_cls_, str):
                        from lazyops.utils.helpers import lazy_import
                        self.__obj_cls_ = lazy_import(self.__obj_cls_)
                    if self.__obj_initialize_:
                        self.__obj_ = self.__obj_cls_(*self.__obj_args_, **self.__obj_kwargs_)
                    else:
                        self.__obj_ = self.__obj_cls_
        return self.__obj_
        
    def __getattr__(self, name) -> Any:
        """
        Forward all unknown attributes to the proxy object
        """
        if not self.__debug_enabled_:
            return getattr(self._obj_, name)
        
        # Try to debug the attribute
        if name not in self.__last_attrs_:
            self.__last_attrs_[name] = 0
        self.__last_attrs_[name] += 1
        if self.__last_attrs_[name] > 5:
            raise AttributeError(f"Proxy object has no attribute {name}")

        if hasattr(self._obj_, name):
            self.__last_attrs_[name] = 0
            return getattr(self._obj_, name)
        raise AttributeError(f"Settings object has no attribute {name}")
    
    if TYPE_CHECKING:
        def __new__(cls, *args, **kwargs) -> ProxyObjT:
            ...