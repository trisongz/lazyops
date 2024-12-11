from __future__ import annotations

import threading
import typing as t
from typing import Any, Union, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    import abc

    from pydantic import BaseModel as _BaseModel, PrivateAttr

    class BaseModel(_BaseModel):
        _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)

    class ObjWithABC(abc.ABC):
        _rxtra: Dict[str, Any] = {}


class eproperty(property):
    """
    Works similarly to property(), but computes the value only once.

    Designed specifically for `pydantic` models using `PrivateAttr`.
    It expects that the `_extra` attribute is a `PrivateAttr` that is
    used to store the computed value.

    This essentially memorizes the value of the property by storing the result
    of its computation in the ``_extra`` of the object instance.  This is
    useful for computing the value of some property that should otherwise be
    invariant.  For example, the two examples below are equivalent::

        >>> class LazyTest(BaseModel):
        ...     _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)
        ...     @property
        ...     def complicated_property(self):
        ...         if 'complicated_property' not in self._extra:
        ...             print('Computing the value for complicated_property...')
        ...             self._extra['complicated_property'] = 42
        ...         return self._extra['complicated_property']
        ...
        ...     @eproperty('_extra')
        ...     def complicated_property(self):
        ...         print('Computing the value for complicated_property...')
        ...         return 42
        ...
        >>> lt = LazyTest()
        >>> lt.complicated_property
        Computing the value for complicated_property...
        42
        >>> lt.complicated_property
        42

    As the example shows, the second time ``complicated_property`` is accessed,
    the ``print`` statement is not executed.  Only the return value from the
    first access off ``complicated_property`` is returned.

    By default, a setter and deleter are used which simply overwrite and
    delete, respectively, the value stored in ``_extra``. Any user-specified
    setter or deleter is executed before executing these default actions.
    The one exception is that the default setter is not run if the user setter
    already sets the new value in ``_extra`` and returns that value and the
    returned value is not ``None``.
    """

    def __init__(self, fget, fset=None, fdel=None, doc=None, key: t.Optional[str] = None):
        super().__init__(fget, fset, fdel, doc)
        self._key = key or self.fget.__name__

    def __get__(self, obj: 'BaseModel', owner=None):
        """
        Returns the value
        """
        try:
            if self._key not in obj._extra: 
                obj._extra[self._key] = self.fget(obj)
            return obj._extra.get(self._key)
        except AttributeError:
            if obj is None:
                return self
            raise

    def __set__(self, obj: 'BaseModel', val):
        """
        Sets the value
        """
        if self.fset:
            ret = self.fset(obj, val)
            if ret is not None and obj._extra.get(self._key) is ret:
                # By returning the value set the setter signals that it
                # took over setting the value in obj.__dict__; this
                # mechanism allows it to override the input value
                return
            val = ret
        obj._extra[self._key] = val


    def __delete__(self, obj: 'BaseModel'):
        """
        Deletes the value
        """
        if self.fdel: self.fdel(obj)
        obj._extra.pop(self._key, None)    # Delete if present

class xproperty(eproperty):
    def __init__(self, fget, fset=None, fdel=None, doc=None, attr_name: t.Optional[str] = '_extra'):
        super().__init__(fget, fset, fdel, doc)
        self._key = self.fget.__name__
        self._attr_name = attr_name
    
    def __get__(self, obj: 'BaseModel' | 'ObjWithABC', owner=None):
        """
        Returns the value
        """
        if not hasattr(obj, self._attr_name): 
            raise AttributeError(f'Object {obj} does not have attribute {self._attr_name}')
        try:
            _attr = getattr(obj, self._attr_name)
            if _attr is None: _attr = {}
            if self._key not in _attr:
                _attr[self._key] = self.fget(obj)
                setattr(obj, self._attr_name, _attr)
            return _attr.get(self._key)
        except AttributeError:
            if obj is None:
                return self
            raise

    def __set__(self, obj: 'BaseModel' | 'ObjWithABC', val):
        """
        Sets the value
        """
        if not hasattr(obj, self._attr_name): 
            raise AttributeError(f'Object {obj} does not have attribute {self._attr_name}')
        _attr = getattr(obj, self._attr_name)
        if _attr is None: _attr = {}
        if self.fset:
            ret = self.fset(obj, val)
            if ret is not None and _attr.get(self._key) is ret:
                # By returning the value set the setter signals that it
                # took over setting the value in obj.__dict__; this
                # mechanism allows it to override the input value
                return
            val = ret
        _attr[self._key] = val
        setattr(obj, self._attr_name, _attr)

    def __delete__(self, obj: 'BaseModel' | 'ObjWithABC'):
        """
        Deletes the value
        """
        if self.fdel: self.fdel(obj)
        _attr = getattr(obj, self._attr_name)
        if _attr is None: _attr = {}
        if self._key in _attr:
            del _attr[self._key]
            setattr(obj, self._attr_name, _attr)
    
def aproperty(
    attr_name: t.Optional[str] = '_extra',
):
    """
    A shortcut to create an `xproperty`
    """
    def decorator(func):
        return xproperty(func, attr_name = attr_name)
    return decorator
    
class rproperty(eproperty):
    def __get__(self, obj: 'ObjWithABC', owner=None):
        """
        Returns the value
        """
        try:
            if self._key not in obj._rxtra: 
                obj._rxtra[self._key] = self.fget(obj)
            return obj._rxtra.get(self._key)
        except AttributeError:
            if obj is None:
                return self
            raise

    def __set__(self, obj: 'ObjWithABC', val):
        """
        Sets the value
        """
        if self.fset:
            ret = self.fset(obj, val)
            if ret is not None and obj._rxtra.get(self._key) is ret:
                # By returning the value set the setter signals that it
                # took over setting the value in obj.__dict__; this
                # mechanism allows it to override the input value
                return
            val = ret
        obj._rxtra[self._key] = val


    def __delete__(self, obj: 'ObjWithABC'):
        """
        Deletes the value
        """
        if self.fdel: self.fdel(obj)
        obj._rxtra.pop(self._key, None)    # Delete if present

_NotFound = object()

# try:
#     from typing import Generic

#     T = TypeVar("T")
#     R = TypeVar("R")

# except ImportError:

CP = t.TypeVar('CP', bound='classproperty')
CPR = t.TypeVar('CPR')
    

class classproperty(property):
    """
    Similar to `property`, but allows class-level properties.  That is,
    a property whose getter is like a `classmethod`.

    The wrapped method may explicitly use the `classmethod` decorator (which
    must become before this decorator), or the `classmethod` may be omitted
    (it is implicit through use of this decorator).

    .. note::

        classproperty only works for *read-only* properties.  It does not
        currently allow writeable/deletable properties, due to subtleties of how
        Python descriptors work.  In order to implement such properties on a class
        a metaclass for that class must be implemented.

    Parameters
    ----------
    fget : callable
        The function that computes the value of this property (in particular,
        the function when this is used as a decorator) a la `property`.

    doc : str, optional
        The docstring for the property--by default inherited from the getter
        function.

    lazy : bool, optional
        If True, caches the value returned by the first call to the getter
        function, so that it is only called once (used for lazy evaluation
        of an attribute).  This is analogous to `lazyproperty`.  The ``lazy``
        argument can also be used when `classproperty` is used as a decorator
        (see the third example below).  When used in the decorator syntax this
        *must* be passed in as a keyword argument.

    Examples
    --------

    ::

        >>> class Foo:
        ...     _bar_internal = 1
        ...     @classproperty
        ...     def bar(cls):
        ...         return cls._bar_internal + 1
        ...
        >>> Foo.bar
        2
        >>> foo_instance = Foo()
        >>> foo_instance.bar
        2
        >>> foo_instance._bar_internal = 2
        >>> foo_instance.bar  # Ignores instance attributes
        2

    As previously noted, a `classproperty` is limited to implementing
    read-only attributes::

        >>> class Foo:
        ...     _bar_internal = 1
        ...     @classproperty
        ...     def bar(cls):
        ...         return cls._bar_internal
        ...     @bar.setter
        ...     def bar(cls, value):
        ...         cls._bar_internal = value
        ...
        Traceback (most recent call last):
        ...
        NotImplementedError: classproperty can only be read-only; use a
        metaclass to implement modifiable class-level properties

    When the ``lazy`` option is used, the getter is only called once::

        >>> class Foo:
        ...     @classproperty(lazy=True)
        ...     def bar(cls):
        ...         print("Performing complicated calculation")
        ...         return 1
        ...
        >>> Foo.bar
        Performing complicated calculation
        1
        >>> Foo.bar
        1

    If a subclass inherits a lazy `classproperty` the property is still
    re-evaluated for the subclass::

        >>> class FooSub(Foo):
        ...     pass
        ...
        >>> FooSub.bar
        Performing complicated calculation
        1
        >>> FooSub.bar
        1
    """

    def __new__(cls: CP, fget=None, doc=None, lazy=False) -> t.Union[t.Callable, CP]:
        if fget is None:
            # Being used as a decorator--return a wrapper that implements
            # decorator syntax
            def wrapper(func):
                return cls(func, lazy=lazy)

            return wrapper

        return super().__new__(cls)

    def __init__(self, fget, doc=None, lazy=False) -> None:
        self._lazy = lazy
        if lazy:
            self._lock = threading.RLock()   # Protects _cache
            self._cache = {}
        fget = self._wrap_fget(fget)

        super().__init__(fget=fget, doc=doc)

        # There is a buglet in Python where self.__doc__ doesn't
        # get set properly on instances of property subclasses if
        # the doc argument was used rather than taking the docstring
        # from fget
        # Related Python issue: https://bugs.python.org/issue24766
        if doc is not None:
            self.__doc__ = doc

    def __get__(self, obj: Any, objtype: t.Type[CP]) -> CPR:
        if self._lazy:
            val = self._cache.get(objtype, _NotFound)
            if val is _NotFound:
                with self._lock:
                    # Check if another thread initialised before we locked.
                    val = self._cache.get(objtype, _NotFound)
                    if val is _NotFound:
                        val = self.fget.__wrapped__(objtype)
                        self._cache[objtype] = val
        else:
            # The base property.__get__ will just return self here;
            # instead we pass objtype through to the original wrapped
            # function (which takes the class as its sole argument)
            val = self.fget.__wrapped__(objtype)
        return val

    def getter(self, fget: t.Callable[[Any], Any]) -> CP:
        return super().getter(self._wrap_fget(fget))


    def setter(self, fset):
        raise NotImplementedError(
            "classproperty can only be read-only; use a metaclass to "
            "implement modifiable class-level properties")


    def deleter(self, fdel):
        raise NotImplementedError(
            "classproperty can only be read-only; use a metaclass to "
            "implement modifiable class-level properties")


    @staticmethod
    def _wrap_fget(orig_fget) -> t.Callable[[Any], Any]:
        if isinstance(orig_fget, classmethod):
            orig_fget = orig_fget.__func__

        # Using stock functools.wraps instead of the fancier version
        # found later in this module, which is overkill for this purpose

        @functools.wraps(orig_fget)
        def fget(obj):
            return orig_fget(obj.__class__)

        return fget


class lazyclassproperty(classproperty):
    def __new__(cls, fget=None, doc=None):
        return super().__new__(cls, fget, doc, lazy=True)


class _CachedClassProperty(object):
    """Cached class property decorator.
    Transforms a class method into a property whose value is computed once
    and then cached as a normal attribute for the life of the class.  Example
    usage:
    >>> class MyClass(object):
    ...   @cached_classproperty
    ...   def value(cls):
    ...     print("Computing value")
    ...     return '<property of %s>' % cls.__name__
    >>> class MySubclass(MyClass):
    ...   pass
    >>> MyClass.value
    Computing value
    '<property of MyClass>'
    >>> MyClass.value  # uses cached value
    '<property of MyClass>'
    >>> MySubclass.value
    Computing value
    '<property of MySubclass>'
    This decorator is similar to `functools.cached_property`, but it adds a
    property to the class, not to individual instances.
    """

    def __init__(self, func):
        self._func = func
        self._cache = {}

    def __get__(self, obj, objtype):
        if objtype not in self._cache:
            self._cache[objtype] = self._func(objtype)
        return self._cache[objtype]

    def __set__(self, obj, value):
        raise AttributeError(f'property {self._func.__name__} is read-only')

    def __delete__(self, obj):
        raise AttributeError(f'property {self._func.__name__} is read-only')


def cached_classproperty(func) -> property:
    return _CachedClassProperty(func)

LP = t.TypeVar('LP')

class lazyproperty(property):
    """
    Works similarly to property(), but computes the value only once.

    This essentially memorizes the value of the property by storing the result
    of its computation in the ``__dict__`` of the object instance.  This is
    useful for computing the value of some property that should otherwise be
    invariant.  For example::

        >>> class LazyTest:
        ...     @lazyproperty
        ...     def complicated_property(self):
        ...         print('Computing the value for complicated_property...')
        ...         return 42
        ...
        >>> lt = LazyTest()
        >>> lt.complicated_property
        Computing the value for complicated_property...
        42
        >>> lt.complicated_property
        42

    As the example shows, the second time ``complicated_property`` is accessed,
    the ``print`` statement is not executed.  Only the return value from the
    first access off ``complicated_property`` is returned.

    By default, a setter and deleter are used which simply overwrite and
    delete, respectively, the value stored in ``__dict__``. Any user-specified
    setter or deleter is executed before executing these default actions.
    The one exception is that the default setter is not run if the user setter
    already sets the new value in ``__dict__`` and returns that value and the
    returned value is not ``None``.

    """

    def __init__(self, fget: t.Callable[..., LP], fset=None, fdel=None, doc=None):
        super().__init__(fget, fset, fdel, doc)
        self._key = self.fget.__name__
        self._lock = threading.RLock()

    def __get__(self, obj: t.Any, owner=None):
        try:
            obj_dict = obj.__dict__
            val = obj_dict.get(self._key, _NotFound)
            if val is _NotFound:
                with self._lock:
                    # Check if another thread beat us to it.
                    val = obj_dict.get(self._key, _NotFound)
                    if val is _NotFound:
                        val = self.fget(obj)
                        obj_dict[self._key] = val
            return val
        except AttributeError:
            if obj is None:
                return self
            raise

    def __set__(self, obj, val):
        obj_dict = obj.__dict__
        if self.fset:
            ret = self.fset(obj, val)
            if ret is not None and obj_dict.get(self._key) is ret:
                # By returning the value set the setter signals that it
                # took over setting the value in obj.__dict__; this
                # mechanism allows it to override the input value
                return
        obj_dict[self._key] = val

    def __delete__(self, obj):
        if self.fdel:
            self.fdel(obj)
        obj.__dict__.pop(self._key, None)    # Delete if present
