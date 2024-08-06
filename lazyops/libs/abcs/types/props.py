from __future__ import annotations

from typing import Any, Union, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel as _BaseModel, PrivateAttr

    class BaseModel(_BaseModel):
        _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)


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

    def __init__(self, fget, fset=None, fdel=None, doc=None):
        super().__init__(fget, fset, fdel, doc)
        self._key = self.fget.__name__

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
