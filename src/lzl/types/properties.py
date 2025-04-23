from __future__ import annotations

"""
Custom Property Descriptors.

This module provides enhanced property decorators offering features like
lazy evaluation and caching, designed to work seamlessly with Pydantic models
and other classes.
"""

import threading
import typing as t
import functools
from typing import Any, Union, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    import abc

    from pydantic import BaseModel as _BaseModel, PrivateAttr

    class BaseModel(_BaseModel):
        _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)

    class ObjWithABC(abc.ABC):
        _rxtra: Dict[str, Any] = {}


class eproperty(property):
    """A property that computes its value only once per instance.

    Designed for use with Pydantic models that utilize a `PrivateAttr` named
    `_extra` (a dictionary) for storing the cached value. It memorizes the
    result of the first getter call.

    Default setters/deleters overwrite/remove the value from the `_extra` dict.
    User-defined setters/deleters run before the default actions.

    Example:
        >>> from pydantic import BaseModel, PrivateAttr
        >>> from typing import Any, Dict
        >>> class LazyTest(BaseModel):
        ...     _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)
        ...
        ...     @eproperty
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
    """

    def __init__(self, fget: t.Callable[[Any], Any], fset: t.Callable[[Any, Any], None] | None = None, fdel: t.Callable[[Any], None] | None = None, doc: str | None = None, key: str | None = None):
        """Initializes the eproperty.

        Args:
            fget: The getter function.
            fset: The setter function (optional).
            fdel: The deleter function (optional).
            doc: The docstring (optional, defaults to fget.__doc__).
            key: The key under which to store the value in the instance's
                `_extra` dict (optional, defaults to fget.__name__).
        """
        super().__init__(fget, fset, fdel, doc)
        self._key = key or self.fget.__name__

    def __get__(self, obj: 'BaseModel', owner=None) -> Any:
        """Gets the property value, computing and caching it if needed.

        Args:
            obj: The instance on which the property is accessed.
            owner: The owner class (unused).

        Returns:
            Any: The computed or cached property value.

        Raises:
            AttributeError: If accessed on the class directly or if the instance
                lacks the `_extra` attribute.
        """
        try:
            # Ensure _extra exists and is initialized (handle potential uninitialized PrivateAttr)
            if not hasattr(obj, '_extra') or getattr(obj, '_extra') is None:
                 setattr(obj, '_extra', {}) # Or handle based on PrivateAttr's factory if possible

            if self._key not in obj._extra:
                obj._extra[self._key] = self.fget(obj)
            return obj._extra.get(self._key)
        except AttributeError:
            if obj is None:
                # Property accessed on the class, not an instance
                return self
            # Reraise if it's a different AttributeError (e.g., within fget)
            raise


    def __set__(self, obj: 'BaseModel', val: Any):
        """Sets the property value.

        Runs the custom setter if provided, then updates the cached value
        in `_extra`.

        Args:
            obj: The instance on which to set the value.
            val: The value to set.

        Raises:
            AttributeError: If the instance lacks the `_extra` attribute.
        """
        if not hasattr(obj, '_extra') or getattr(obj, '_extra') is None:
            setattr(obj, '_extra', {}) # Initialize if needed

        if self.fset:
            ret = self.fset(obj, val)
            # Allow setter to signal it handled caching by returning the value
            if ret is not None and obj._extra.get(self._key) is ret:
                return
            val = ret # Allow setter to modify the value before caching
        obj._extra[self._key] = val


    def __delete__(self, obj: 'BaseModel'):
        """Deletes the cached property value.

        Runs the custom deleter if provided, then removes the value from `_extra`.

        Args:
            obj: The instance from which to delete the value.

        Raises:
            AttributeError: If the instance lacks the `_extra` attribute.
        """
        if not hasattr(obj, '_extra') or getattr(obj, '_extra') is None:
            return # Nothing to delete if _extra doesn't exist

        if self.fdel: self.fdel(obj)
        obj._extra.pop(self._key, None)


class xproperty(eproperty):
    """Generic version of eproperty storing the value in a specified attribute.

    Similar to `eproperty`, but caches the value in an instance attribute
    whose name is specified during initialization (defaults to `_extra`).
    The target attribute must be a dictionary.
    """
    def __init__(self, fget: t.Callable[[Any], Any], fset: t.Callable[[Any, Any], None] | None = None, fdel: t.Callable[[Any], None] | None = None, doc: str | None = None, attr_name: str = '_extra'):
        """Initializes the xproperty.

        Args:
            fget: The getter function.
            fset: The setter function (optional).
            fdel: The deleter function (optional).
            doc: The docstring (optional, defaults to fget.__doc__).
            attr_name: The name of the dictionary attribute on the instance
                used for caching (defaults to '_extra').
        """
        super().__init__(fget, fset, fdel, doc)
        self._key = self.fget.__name__ # Use property name as key within the cache dict
        self._attr_name = attr_name

    def __get__(self, obj: 'BaseModel' | 'ObjWithABC', owner=None) -> Any:
        """Gets the property value, computing and caching it if needed.

        Args:
            obj: The instance on which the property is accessed.
            owner: The owner class (unused).

        Returns:
            Any: The computed or cached property value.

        Raises:
            AttributeError: If accessed on the class directly or if the instance
                lacks the specified caching attribute (`attr_name`).
        """
        if obj is None:
            return self # Accessed on class

        _cache = getattr(obj, self._attr_name, None)
        if _cache is None:
             # Dynamically create the cache dict if it doesn't exist
            _cache = {}
            setattr(obj, self._attr_name, _cache)
        elif not isinstance(_cache, dict):
            raise TypeError(f"Attribute '{self._attr_name}' must be a dictionary for xproperty caching.")


        if self._key not in _cache:
            _cache[self._key] = self.fget(obj)
            # No need to setattr again unless _cache was initially None
        return _cache.get(self._key)


    def __set__(self, obj: 'BaseModel' | 'ObjWithABC', val: Any):
        """Sets the property value in the specified cache attribute.

        Args:
            obj: The instance on which to set the value.
            val: The value to set.

        Raises:
            AttributeError: If the instance lacks the specified caching attribute.
            TypeError: If the caching attribute is not a dictionary.
        """
        _cache = getattr(obj, self._attr_name, None)
        if _cache is None:
            _cache = {}
            setattr(obj, self._attr_name, _cache)
        elif not isinstance(_cache, dict):
            raise TypeError(f"Attribute '{self._attr_name}' must be a dictionary for xproperty caching.")

        if self.fset:
            ret = self.fset(obj, val)
            if ret is not None and _cache.get(self._key) is ret:
                return
            val = ret
        _cache[self._key] = val
        # No need to setattr again unless _cache was initially None


    def __delete__(self, obj: 'BaseModel' | 'ObjWithABC'):
        """Deletes the cached property value from the specified attribute.

        Args:
            obj: The instance from which to delete the value.

        Raises:
            AttributeError: If the instance lacks the specified caching attribute.
            TypeError: If the caching attribute is not a dictionary.
        """
        _cache = getattr(obj, self._attr_name, None)
        # Don't raise error if cache or key doesn't exist, just do nothing.
        if not isinstance(_cache, dict):
            return

        if self.fdel: self.fdel(obj)
        _cache.pop(self._key, None)
        # No need to setattr again


def aproperty(
    attr_name: str = '_extra',
) -> t.Callable[[t.Callable], xproperty]:
    """Decorator factory to create an `xproperty`.

    This is a shortcut for applying the `xproperty` descriptor.

    Args:
        attr_name (str): The name of the dictionary attribute on the instance
            to use for caching (defaults to '_extra').

    Returns:
        Callable[[Callable], xproperty]: A decorator that takes the getter
            function and returns an `xproperty` instance.
    """
    def decorator(func: t.Callable) -> xproperty:
        return xproperty(func, attr_name = attr_name)
    return decorator

class rproperty(eproperty):
    """Specialized `eproperty` using `_rxtra` for caching (for non-Pydantic).

    Identical to `eproperty`, but uses an attribute named `_rxtra` instead of
    `_extra` for storing the cached value. This is intended for use with
    classes that might not inherit from Pydantic's `BaseModel` but still need
    lazy property evaluation (like classes using `abc.ABC`).

    Assumes the instance will have a dictionary attribute named `_rxtra`.
    """
    def __get__(self, obj: 'ObjWithABC', owner=None) -> Any:
        """Gets the property value, using `_rxtra` for caching.

        Args:
            obj: The instance on which the property is accessed.
            owner: The owner class (unused).

        Returns:
            Any: The computed or cached property value.

        Raises:
            AttributeError: If accessed on the class, or `_rxtra` is missing/None.
        """
        try:
            # Ensure _rxtra exists and is initialized
            if not hasattr(obj, '_rxtra') or getattr(obj, '_rxtra') is None:
                 setattr(obj, '_rxtra', {})

            if self._key not in obj._rxtra:
                obj._rxtra[self._key] = self.fget(obj)
            return obj._rxtra.get(self._key)
        except AttributeError:
            if obj is None:
                return self
            raise

    def __set__(self, obj: 'ObjWithABC', val: Any):
        """Sets the property value in `_rxtra`.

        Args:
            obj: The instance on which to set the value.
            val: The value to set.

        Raises:
            AttributeError: If `_rxtra` is missing/None.
        """
        if not hasattr(obj, '_rxtra') or getattr(obj, '_rxtra') is None:
            setattr(obj, '_rxtra', {})

        if self.fset:
            ret = self.fset(obj, val)
            if ret is not None and obj._rxtra.get(self._key) is ret:
                return
            val = ret
        obj._rxtra[self._key] = val


    def __delete__(self, obj: 'ObjWithABC'):
        """Deletes the cached property value from `_rxtra`.

        Args:
            obj: The instance from which to delete the value.

        Raises:
            AttributeError: If `_rxtra` is missing/None.
        """
        if not hasattr(obj, '_rxtra') or getattr(obj, '_rxtra') is None:
            return

        if self.fdel: self.fdel(obj)
        obj._rxtra.pop(self._key, None)

_NotFound = object()

# try:
#     from typing import Generic

#     T = TypeVar("T")
#     R = TypeVar("R")

# except ImportError:

CP = t.TypeVar('CP', bound='classproperty')
CPR = t.TypeVar('CPR')
    

class classproperty(property):
    """Creates a read-only class-level property.

    Acts like a combination of `@classmethod` and `@property`. Allows accessing
    a computed value on the class itself or on instances, where the computation
    depends only on the class.

    The wrapped method can optionally be decorated with `@classmethod` (it's
    implicit otherwise).

    Note:
        This descriptor creates *read-only* properties. Attempting to define
        a setter or deleter will raise `NotImplementedError`.

    Args:
        fget (Callable): The function to compute the property value. It receives
            the class as its first argument.
        doc (str, optional): The docstring for the property. Defaults to
            `fget.__doc__`.
        lazy (bool, optional): If True, the value is computed only once per
            class and cached. Defaults to False.

    Examples:
        >>> class MyClass:
        ...     _internal_value = 10
        ...
        ...     @classproperty
        ...     def computed_value(cls):
        ...         print(f'Computing for {cls.__name__}...')
        ...         return cls._internal_value * 2
        ...
        >>> MyClass.computed_value
        Computing for MyClass...
        20
        >>> MyClass.computed_value # Not computed again
        20

        >>> instance = MyClass()
        >>> instance.computed_value # Access via instance
        20

        Lazy evaluation example:
        >>> class LazyDemo:
        ...     @classproperty(lazy=True)
        ...     def lazy_value(cls):
        ...         print(f'Calculating lazy value for {cls.__name__}...')
        ...         return 100
        ...
        >>> LazyDemo.lazy_value
        Calculating lazy value for LazyDemo...
        100
        >>> LazyDemo.lazy_value # Cached
        100

        >>> class SubLazyDemo(LazyDemo):
        ...     pass
        ...
        >>> SubLazyDemo.lazy_value # Recomputed for subclass
        Calculating lazy value for SubLazyDemo...
        100
        >>> SubLazyDemo.lazy_value # Cached for subclass
        100
    """

    def __new__(cls: CP, fget=None, doc=None, lazy=False) -> t.Union[t.Callable, CP]:
        """Handles instantiation and decorator usage.

        Allows `classproperty` to be used as `@classproperty` or
        `@classproperty(lazy=True)`.

        Args:
            fget: The getter function (if used directly, not as decorator).
            doc: The docstring (if used directly).
            lazy: Whether to enable lazy evaluation (if used as decorator).

        Returns:
            Union[Callable, CP]: Either a decorator wrapper or a new instance.
        """
        if fget is None:
            # Being used as a decorator--return a wrapper that implements
            # decorator syntax
            def wrapper(func):
                return cls(func, lazy=lazy)

            return wrapper

        return super().__new__(cls)

    def __init__(self, fget: t.Callable[[t.Type[Any]], CPR], doc: str | None = None, lazy: bool = False) -> None:
        """Initializes the classproperty descriptor.

        Args:
            fget: The getter function (receives class as first arg).
            doc: Optional docstring.
            lazy: Whether to cache the result (lazy evaluation).
        """
        self._lazy = lazy
        if lazy:
            self._lock = threading.RLock()   # Protects _cache
            self._cache: t.Dict[t.Type[Any], CPR] = {}
        fget = self._wrap_fget(fget)

        super().__init__(fget=fget, doc=doc)

        # There is a buglet in Python where self.__doc__ doesn't
        # get set properly on instances of property subclasses if
        # the doc argument was used rather than taking the docstring
        # from fget
        # Related Python issue: https://bugs.python.org/issue24766
        if doc is not None:
            self.__doc__ = doc

    def __get__(self, obj: Any, objtype: t.Type[Any]) -> CPR:
        """Gets the property value, computing/caching as necessary.

        Called when the property is accessed on the class (`obj` is None) or
        an instance (`obj` is the instance).

        Args:
            obj: The instance being accessed (or None if accessed on the class).
            objtype: The class on which the property is accessed.

        Returns:
            The computed or cached property value.
        """
        if self._lazy:
            # Lazy evaluation: check cache first
            val = self._cache.get(objtype, _NotFound)
            if val is _NotFound:
                with self._lock: # Thread-safe check and computation
                    # Check again inside lock if another thread initialized
                    val = self._cache.get(objtype, _NotFound)
                    if val is _NotFound:
                        val = self.fget.__wrapped__(objtype)
                        self._cache[objtype] = val
        else:
            # Non-lazy: compute every time using the class (objtype)
            # The base property.__get__ would return self if obj is None.
            # We always call the wrapped getter with the class.
            val = self.fget.__wrapped__(objtype)
        return val

    def getter(self, fget: t.Callable[[t.Type[Any]], CPR]) -> CP:
        """Descriptor to change the getter method.

        Args:
            fget: The new getter function.

        Returns:
            classproperty: A new classproperty instance with the updated getter.
        """
        return super().getter(self._wrap_fget(fget))


    def setter(self, fset: t.Callable) -> None:
        """Raises NotImplementedError; classproperty is read-only."""
        raise NotImplementedError(
            "classproperty can only be read-only; use a metaclass to "
            "implement modifiable class-level properties")


    def deleter(self, fdel: t.Callable) -> None:
        """Raises NotImplementedError; classproperty is read-only."""
        raise NotImplementedError(
            "classproperty can only be read-only; use a metaclass to "
            "implement modifiable class-level properties")


    @staticmethod
    def _wrap_fget(orig_fget: t.Callable) -> t.Callable[[Any], CPR]:
        """Wraps the getter function to handle implicit classmethod behavior.

        Ensures the function receives the class (`objtype`) even when accessed
        via an instance (`obj`). Also unwraps if `@classmethod` was explicitly used.

        Args:
            orig_fget: The original getter function provided by the user.

        Returns:
            Callable: A new getter function compatible with `property.__init__`.
        """
        if isinstance(orig_fget, classmethod):
            # Unwrap the function if @classmethod was used
            orig_fget = orig_fget.__func__

        # Using stock functools.wraps instead of the fancier version
        # found later in this module, which is overkill for this purpose

        @functools.wraps(orig_fget)
        def fget(obj_or_type: t.Union[Any, t.Type[Any]]) -> CPR:
            # When __get__ calls this, it receives the *instance*
            # if accessed on an instance. We need the *class*.
            cls = obj_or_type if isinstance(obj_or_type, type) else obj_or_type.__class__
            return orig_fget(cls)

        return fget


class lazyclassproperty(classproperty):
    """A shortcut for creating a lazy-evaluated `classproperty`.

    Equivalent to `@classproperty(lazy=True)`.
    """
    def __new__(cls, fget=None, doc=None):
        """Creates a new lazyclassproperty instance.

        Args:
            fget: The getter function.
            doc: Optional docstring.

        Returns:
            classproperty: A new classproperty instance with lazy=True.
        """
        return super().__new__(cls, fget, doc, lazy=True)

# Note: _CachedClassProperty and cached_classproperty seem like an alternative
# implementation to classproperty(lazy=True). Consider unifying if appropriate.

class _CachedClassProperty(object):
    """Cached class property decorator (Alternative Implementation).

    Transforms a class method into a property whose value is computed once
    per class and then cached. Similar to `functools.cached_property` but
    for class-level attributes.

    Note:
        This appears distinct from `classproperty(lazy=True)` and might be
        redundant or serve a slightly different purpose. It directly manages
        a `_cache` dict.

    Args:
        func (Callable): The class method to be turned into a cached property.
            It receives the class as its argument.

    Examples:
        >>> class MyClass:
        ...   @cached_classproperty
        ...   def value(cls):
        ...     print("Computing value")
        ...     return f'<property of {cls.__name__}>'
        ...
        >>> class MySubclass(MyClass):
        ...   pass
        ...
        >>> MyClass.value
        Computing value
        '<property of MyClass>'
        >>> MyClass.value  # uses cached value
        '<property of MyClass>'
        >>> MySubclass.value
        Computing value
        '<property of MySubclass>'
    """

    def __init__(self, func: t.Callable[[t.Type[Any]], CPR]):
        """Initializes the _CachedClassProperty.

        Args:
            func: The function to compute the class property value.
        """
        self._func = func
        self._cache: t.Dict[t.Type[Any], CPR] = {}

    def __get__(self, obj: Any, objtype: t.Type[Any]) -> CPR:
        """Gets the cached or computed class property value.

        Args:
            obj: The instance (or None if accessed via class).
            objtype: The class on which the property is accessed.

        Returns:
            The computed or cached property value for the class.
        """
        # Cache is per-class (using objtype as key)
        if objtype not in self._cache:
            self._cache[objtype] = self._func(objtype)
        return self._cache[objtype]

    def __set__(self, obj: Any, value: Any) -> None:
        """Raises AttributeError; property is read-only."""
        raise AttributeError(f'property {self._func.__name__} is read-only')

    def __delete__(self, obj: Any) -> None:
        """Raises AttributeError; property is read-only."""
        raise AttributeError(f'property {self._func.__name__} is read-only')


def cached_classproperty(func: t.Callable[[t.Type[Any]], CPR]) -> _CachedClassProperty:
    """Decorator that creates a cached, read-only class property.

    Args:
        func: The class method (receiving the class as arg) to decorate.

    Returns:
        _CachedClassProperty: An instance of the descriptor.
    """
    return _CachedClassProperty(func)

LP = t.TypeVar('LP')

class lazyproperty(property):
    """Property descriptor that computes the value only once per instance.

    Similar to `@property`, but the result of the first call to the getter
    is cached in the instance's `__dict__`. Subsequent accesses return the
    cached value directly.

    Uses a thread-safe lock for computing the value initially.
    Default setter/deleter operate on the cached value in `__dict__`.

    Example:
        >>> class DataProcessor:
        ...     def __init__(self, raw_data):
        ...         self.raw_data = raw_data
        ...
        ...     @lazyproperty
        ...     def processed_data(self):
        ...         print(f'Processing data: {self.raw_data}...')
        ...         # Simulate expensive computation
        ...         return self.raw_data.upper()
        ...
        >>> processor = DataProcessor('initial data')
        >>> processor.processed_data
        Processing data: initial data...
        'INITIAL DATA'
        >>> processor.processed_data # Value is cached
        'INITIAL DATA'
    """

    def __init__(self, fget: t.Callable[..., LP], fset: t.Callable[[Any, LP], None] | None = None, fdel: t.Callable[[Any], None] | None = None, doc: str | None = None):
        """Initializes the lazyproperty.

        Args:
            fget: The getter function.
            fset: The setter function (optional).
            fdel: The deleter function (optional).
            doc: The docstring (optional, defaults to fget.__doc__).
        """
        super().__init__(fget, fset, fdel, doc)
        self._key = self.fget.__name__
        self._lock = threading.RLock()

    def __get__(self, obj: t.Any, owner=None) -> LP:
        """Gets the property value, computing and caching it if needed.

        Uses the instance's `__dict__` for caching.

        Args:
            obj: The instance on which the property is accessed.
            owner: The owner class (unused).

        Returns:
            The computed or cached property value.

        Raises:
            AttributeError: If accessed on the class directly or if `obj` lacks
                `__dict__`.
        """
        if obj is None:
            return self # Accessed on class

        try:
            obj_dict = obj.__dict__
        except AttributeError: # Handle objects without __dict__ (e.g., built-ins with __slots__)
             raise AttributeError(f"'{type(obj).__name__}' object has no attribute '__dict__', required by lazyproperty") from None

        val = obj_dict.get(self._key, _NotFound)
        if val is _NotFound:
            with self._lock: # Thread-safe computation
                # Check again inside lock if another thread computed it
                val = obj_dict.get(self._key, _NotFound)
                if val is _NotFound:
                    val = self.fget(obj)
                    obj_dict[self._key] = val
        return val

    def __set__(self, obj: t.Any, val: LP) -> None:
        """Sets the property value, updating the cache in `__dict__`.

        Args:
            obj: The instance on which to set the value.
            val: The value to set.

        Raises:
            AttributeError: If `obj` lacks `__dict__`.
        """
        try:
            obj_dict = obj.__dict__
        except AttributeError:
            raise AttributeError(f"'{type(obj).__name__}' object has no attribute '__dict__', required by lazyproperty") from None

        if self.fset:
            ret = self.fset(obj, val)
            # Allow setter to signal it handled caching
            if ret is not None and obj_dict.get(self._key) is ret:
                return
            # Allow setter to modify value before caching (if it returns None)
            # If setter returns a value different from cache check, update val? <= Original logic didn't do this.
            # Let's keep original logic: setter return value (if not None and not matching cache) is ignored for caching.
            # If setter returns None, the original `val` is cached.

        obj_dict[self._key] = val

    def __delete__(self, obj: t.Any) -> None:
        """Deletes the cached property value from `__dict__`.

        Args:
            obj: The instance from which to delete the value.

        Raises:
            AttributeError: If `obj` lacks `__dict__`.
        """
        try:
            obj_dict = obj.__dict__
        except AttributeError:
            raise AttributeError(f"'{type(obj).__name__}' object has no attribute '__dict__', required by lazyproperty") from None

        if self.fdel:
            self.fdel(obj)
        obj_dict.pop(self._key, None) # Delete if present
