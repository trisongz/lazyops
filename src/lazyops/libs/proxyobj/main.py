import copy
import threading
import contextlib
import operator
import copyreg
from typing import Any, Type, Tuple, Dict, List, Union, Optional, Callable, TypeVar, Iterable, Generic, TYPE_CHECKING


ProxyObjT = TypeVar('ProxyObjT')


class ProxyObjectV1(Generic[ProxyObjT]):
    def __init__(
        self,
        obj_cls: Optional[Union[Type[ProxyObjT], str]] = None,
        obj_getter: Optional[Union[Callable, str]] = None,
        obj_args: Optional[List[Any]] = None,
        obj_kwargs: Optional[Dict[str, Any]] = None,
        obj_initialize: Optional[bool] = True,
        threadsafe: Optional[bool] = True,
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
        # Evaluate better approach with https://github.com/seperman/dotobject/blob/master/dot/borrowed_lazy.py
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
    

    def __call__(self, *args, **kwargs) -> Any:
        """
        Call the proxy object
        """
        return self._obj_(*args, **kwargs)

    def __getattr__(self, name):
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


class ProxyObjectV2(Generic[ProxyObjT]):
    def __init__(
        self,
        obj_cls: Optional[Union[Type[ProxyObjT], str]] = None,
        obj_getter: Optional[Union[Callable, str]] = None,
        obj_args: Optional[List[Any]] = None,
        obj_kwargs: Optional[Dict[str, Any]] = None,
        obj_initialize: Optional[bool] = True,
        threadsafe: Optional[bool] = True,
        debug_enabled: Optional[bool] = False,
    ) -> ProxyObjT:
        """
        Proxy Object

        args:
            obj_cls: the class of the object
            obj_getter: the function to get the object
            debug_enabled: if True, will raise an error if the object is not found
        """
        # Intentionally underscore on the end to avoid conflicts with the settings
        # Evaluate better approach with https://github.com/seperman/dotobject/blob/master/dot/borrowed_lazy.py
        assert obj_cls or obj_getter, "Either `obj_cls` or `obj_getter` must be provided"
        self.__dict__['__obj_cls_'] = obj_cls
        if obj_getter and isinstance(obj_getter, str):
            from lazyops.utils.helpers import lazy_import
            obj_getter = lazy_import(obj_getter)
        self.__dict__['__obj_getter_'] = obj_getter
        self.__dict__['__threadlock_'] = None if threadsafe else threading.Lock()
        self.__dict__['__obj_'] = None
        self.__dict__['__obj_args_'] = obj_args or []
        self.__dict__['__obj_kwargs_'] = obj_kwargs or {}
        self.__dict__['__obj_initialize_'] = obj_initialize
        self.__dict__['__debug_enabled_'] = debug_enabled
        self.__dict__['__last_attrs_'] = {}

        
    @contextlib.contextmanager
    def _objlock_(self):
        """
        Returns the object lock
        """
        if self.__dict__['__threadlock_'] is not None:
            try:
                with self.__dict__['__threadlock_']:
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
        if self.__dict__['__obj_'] is None:
            with self._objlock_():
                if self.__dict__['__obj_getter_']:
                    self.__dict__['__obj_'] = self.__dict__['__obj_getter_'](*self.__dict__['__obj_args_'], **self.__dict__['__obj_kwargs_'])
                elif self.__dict__['__obj_cls_']:
                    if isinstance(self.__dict__['__obj_cls_'], str):
                        from lazyops.utils.helpers import lazy_import
                        self.__dict__['__obj_cls_'] = lazy_import(self.__dict__['__obj_cls_'])
                    if self.__dict__['__obj_initialize_']:
                        self.__dict__['__obj_'] = self.__dict__['__obj_cls_'](*self.__dict__['__obj_args_'], **self.__dict__['__obj_kwargs_'])
                    else:
                        self.__dict__['__obj_'] = self.__dict__['__obj_cls_']
        return self.__dict__['__obj_']
    
    def __call__(self, *args, **kwargs) -> Any:
        """
        Call the proxy object
        """
        return self._obj_(*args, **kwargs)

    def __getattr__(self, name) -> Any:
        """
        Forward all unknown attributes to the proxy object
        """
        if name in self.__dict__:
            return self.__dict__[name]
        
        if not self.__dict__['__debug_enabled_']:
            return getattr(self._obj_, name)
        
        # Try to debug the attribute
        if name not in self.__dict__['__last_attrs_']:
            self.__dict__['__last_attrs_'][name] = 0
        self.__dict__['__last_attrs_'][name] += 1
        if self.__dict__['__last_attrs_'][name] > 5:
            raise AttributeError(f"Proxy object has no attribute {name}")
        if hasattr(self._obj_, name):
            self.__dict__['__last_attrs_'][name] = 0
            return getattr(self._obj_, name)
        raise AttributeError(f"Proxy object has no attribute {name}")
    
    if TYPE_CHECKING:
        def __new__(cls, *args, **kwargs) -> Type[ProxyObjT]:
            ...



class Constant(tuple):
    "Pretty display of immutable constant."

    def __new__(cls, name):
        return tuple.__new__(cls, (name,))

    def __repr__(self):
        return f'{self[0]}'

EMPTY = Constant('EMPTY')
empty = object()


def new_method_proxy(func):
    def inner(self: 'ProxyObjectV3', *args):
        if self._wrapped is empty:
            self._setup()
        return func(self._wrapped, *args)
    return inner

"""
Borrowed from 
https://github.com/seperman/dotobject/blob/master/dot/borrowed_lazy.py
"""


class ProxyObjectV3(Generic[ProxyObjT]):
    
    _wrapped = None

    if TYPE_CHECKING:
        def __new__(cls: Type[ProxyObjT], *args, **kwargs) -> ProxyObjT:
            ...

    def __init__(
        self,
        obj_cls: Optional[Union[Type[ProxyObjT], str]] = None,
        obj_getter: Optional[Union[Callable[..., ProxyObjT], str]] = None,
        obj_args: Optional[Union[str, Callable[..., Iterable[Any]], Iterable[Any]]] = None,
        obj_kwargs: Optional[Union[str, Callable[..., Dict[str, Any]], Dict[str, Any]]] = None,
        obj_initialize: Optional[bool] = True,
        threadsafe: Optional[bool] = True,
        # debug_enabled: Optional[bool] = False,
    ) -> ProxyObjT:
        """
        args:
            obj_cls: the class of the object
            obj_getter: the function to get the object
            debug_enabled: if True, will raise an error if the object is not found
        """
        
        assert obj_cls or obj_getter, "Either `obj_cls` or `obj_getter` must be provided"
        self._wrapped = empty
        self.__dict__['__obj_cls_'] = obj_cls
        # Defer until called.
        # if obj_getter and isinstance(obj_getter, str):
        #     from lazyops.utils.helpers import lazy_import
        #     obj_getter = lazy_import(obj_getter)
        # if obj_args and isinstance(obj_args, str):
        #     from lazyops.utils.helpers import lazy_import
        #     obj_args = lazy_import(obj_args)
        # if obj_kwargs and isinstance(obj_kwargs, str):
        #     from lazyops.utils.helpers import lazy_import
        #     obj_kwargs = lazy_import(obj_kwargs)
        self.__dict__['__obj_getter_'] = obj_getter
        self.__dict__['__threadlock_'] = None if threadsafe else threading.Lock()
        self.__dict__['__obj_args_'] = obj_args or []
        self.__dict__['__obj_kwargs_'] = obj_kwargs or {}
        self.__dict__['__obj_initialize_'] = obj_initialize
        # self.__dict__['__debug_enabled_'] = debug_enabled
        self.__dict__['__last_attrs_'] = {}

    
    @contextlib.contextmanager
    def _objlock_(self):
        """
        Returns the object lock
        """
        if self.__dict__['__threadlock_'] is not None:
            try:
                with self.__dict__['__threadlock_']:
                    yield
            except Exception as e:
                raise e
        else:
            yield

    __getattr__ = new_method_proxy(getattr)

    def __setattr__(self, name, value):
        if name == "_wrapped":
            # Assign to __dict__ to avoid infinite __setattr__ loops.
            self.__dict__["_wrapped"] = value
        else:
            if self._wrapped is empty:
                self._setup()
            setattr(self._wrapped, name, value)

    def __delattr__(self, name):
        if name == "_wrapped":
            raise TypeError("can't delete _wrapped.")
        if self._wrapped is empty:
            self._setup()
        delattr(self._wrapped, name)

    def __call__(self, *args, **kwargs) -> Any:
        """
        Call the proxy object
        """
        if self._wrapped is empty:
            self._setup()
        return self._wrapped(*args, **kwargs)

    def _setup_init(self):
        """
        Setup and initialize the proxy object arguments
        """
        from lazyops.utils.helpers import lazy_import
        if self.__dict__['__obj_args_'] is not None and not isinstance(self.__dict__['__obj_args_'], (list, tuple)):
            if isinstance(self.__dict__['__obj_args_'], str):
                self.__dict__['__obj_args_'] = lazy_import(self.__dict__['__obj_args_'])
            if callable(self.__dict__['__obj_args_']):
                self.__dict__['__obj_args_'] = self.__dict__['__obj_args_']()
        
        if self.__dict__['__obj_kwargs_'] is not None and not isinstance(self.__dict__['__obj_kwargs_'], dict):
            if isinstance(self.__dict__['__obj_kwargs_'], str):
                self.__dict__['__obj_kwargs_'] = lazy_import(self.__dict__['__obj_kwargs_'])
            if callable(self.__dict__['__obj_kwargs_']):
                self.__dict__['__obj_kwargs_'] = self.__dict__['__obj_kwargs_']()
        
        if self.__dict__['__obj_getter_'] is not None and isinstance(self.__dict__['__obj_getter_'], str):
            self.__dict__['__obj_getter_'] = lazy_import(self.__dict__['__obj_getter_'])

        elif self.__dict__['__obj_cls_'] is not None and isinstance(self.__dict__['__obj_cls_'], str):
            self.__dict__['__obj_cls_'] = lazy_import(self.__dict__['__obj_cls_'])


    def _setup(self):
        """
        Initializes the Proxy Object
        """
        # if self.__dict__['__obj_'] is not None: return
        
        with self._objlock_():
            self._setup_init()    
            if self.__dict__['__obj_getter_'] is not None:
                self.__dict__['_wrapped'] = self.__dict__['__obj_getter_'](*self.__dict__['__obj_args_'], **self.__dict__['__obj_kwargs_'])
            
            elif self.__dict__['__obj_cls_']:
                if self.__dict__['__obj_initialize_']:
                    self.__dict__['_wrapped'] = self.__dict__['__obj_cls_'](*self.__dict__['__obj_args_'], **self.__dict__['__obj_kwargs_'])
                else:
                    self.__dict__['_wrapped'] = self.__dict__['__obj_cls_']
        

    # Because we have messed with __class__ below, we confuse pickle as to what
    # class we are pickling. It also appears to stop __reduce__ from being
    # called. So, we define __getstate__ in a way that cooperates with the way
    # that pickle interprets this class.  This fails when the wrapped class is
    # a builtin, but it is better than nothing.
    def __getstate__(self):
        if self._wrapped is empty:
            self._setup()
        return self._wrapped.__dict__

    # Python 3.3 will call __reduce__ when pickling; this method is needed
    # to serialize and deserialize correctly.
    @classmethod
    def __newobj__(cls, *args):
        return cls.__new__(cls, *args)
    
    def __reduce_ex__(self, proto):
        return (self.__newobj__, (self.__class__,), self.__getstate__())


    def __deepcopy__(self, memo):
        if self._wrapped is empty:
            # We have to use type(self), not self.__class__, because the
            # latter is proxied.
            result = type(self)()
            memo[id(self)] = result
            return result
        return copy.deepcopy(self._wrapped, memo)

    __bytes__ = new_method_proxy(bytes)
    __str__ = new_method_proxy(str)
    __bool__ = new_method_proxy(bool)
    # Introspection support
    __dir__ = new_method_proxy(dir)

    # Need to pretend to be the wrapped class, for the sake of objects that
    # care about this (especially in equality tests)
    __class__ = property(new_method_proxy(operator.attrgetter("__class__")))
    __eq__ = new_method_proxy(operator.eq)
    __ne__ = new_method_proxy(operator.ne)
    __hash__ = new_method_proxy(hash)

    # Dictionary methods support
    __getitem__ = new_method_proxy(operator.getitem)
    __setitem__ = new_method_proxy(operator.setitem)
    __delitem__ = new_method_proxy(operator.delitem)

    __len__ = new_method_proxy(len)
    __contains__ = new_method_proxy(operator.contains)

    # Additions for DotObject
    __gt__ = new_method_proxy(operator.gt)
    __lt__ = new_method_proxy(operator.lt)
    __ge__ = new_method_proxy(operator.ge)
    __le__ = new_method_proxy(operator.le)
    __add__ = new_method_proxy(operator.add)
    __radd__ = new_method_proxy(operator.add)
    __sub__ = new_method_proxy(operator.sub)
    __rsub__ = new_method_proxy(operator.sub)
    __mul__ = new_method_proxy(operator.mul)
    __rmul__ = new_method_proxy(operator.mul)
    __floordiv__ = new_method_proxy(operator.floordiv)
    __div__ = new_method_proxy(operator.truediv)
    __rdiv__ = new_method_proxy(operator.truediv)
    __truediv__ = new_method_proxy(operator.truediv)
    __rtruediv__ = new_method_proxy(operator.truediv)
    __mod__ = new_method_proxy(operator.mod)
    __rmod__ = new_method_proxy(operator.mod)
    __pow__ = new_method_proxy(operator.pow)
    __rpow__ = new_method_proxy(operator.pow)
    __lshift__ = new_method_proxy(operator.lshift)
    __rshift__ = new_method_proxy(operator.rshift)
    __and__ = new_method_proxy(operator.and_)
    __or__ = new_method_proxy(operator.or_)
    __xor__ = new_method_proxy(operator.xor)




ProxyObject = ProxyObjectV3