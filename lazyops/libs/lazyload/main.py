from __future__ import annotations

"""
Support Lazy Loading of Modules

- Credit: https://github.com/kevdog824
"""

import importlib
from typing import Generic, TypeVar, Any
from types import ModuleType


_M = TypeVar("_M", bound=ModuleType)


class LazyLoad(Generic[_M]):
    def __init__(self, name: str, package: str | None = None) -> None:
        self._lzyname = name  # Ridiculous name avoids name clash with module
        self._lzypackage = package  # Ridiculous name avoids name clash with module
        self.__module__: ModuleType | None = None

    def __load__(self) -> _M:
        """Explicitly load the import."""
        if self.__module__ is None:
            self.__module__ = importlib.import_module(self._lzyname, self._lzypackage)
        return self.__module__

    def __reload__(self) -> _M:
        """Explicitly reload the import."""
        try:
            self.__module__ = importlib.reload(self.__module__)
        except Exception as exc:
            try:
                self.__module__ = importlib.import_module(self._lzyname, self._lzypackage)
            except Exception as e:
                raise exc from e
        return self.__module__

    def __repr__(self) -> str:
        """Gives a good representation before import is loaded.
        Uses import's __repr__ after it is loaded.
        """
        if self.__module__ is None:
            if self._lzypackage:
                return f"<Uninitialized module '{self._lzyname}' @ '{self._lzypackage}'>"
            return f"<Uninitialized module '{self._lzyname}'>"
        try:
            return self.__module__.__repr__()
        # Shouldn't happen unless someone del'd module __repr__ method for some reason
        except AttributeError:
            if self._lzypackage:
                return f"<Initialized module '{self._lzyname}' @ '{self._lzypackage}'>"
            return f"<Initialized module '{self._lzyname}'>"

    def __getattribute__(self, __name: str) -> Any:
        """Proxies attribute access to import (loads the import if not yet loaded)."""
        if __name in {
            "_lzyname",
            "_lzypackage",
            "__module__",
            "__load__",
            "__reload__",
        }:
            return super().__getattribute__(__name)
        if self.__module__ is None:
            self.__module__ = importlib.import_module(self._lzyname, self._lzypackage)
        return getattr(self.__module__, __name)


def lazy_load(name: str, package: str | None = None) -> LazyLoad:
    """Lazily load an import.
    Returns a LazyLoad object which won't load the import until you attempt
    attribute access, you call the load function with this object, or you call the
    __load__ method of this object.
    """
    return LazyLoad(name, package)


def load(__module: LazyLoad | _M) -> _M:
    """Explicitly load an import.
    If module is a LazyLoad object its wrapped import is loaded and returned.
    If module is an actual ModuleType it is simply returned.
    """
    return __module.__load__() if isinstance(__module, LazyLoad) else __module


def reload(__module: LazyLoad | _M) -> _M:
    """Explicitly reload an import.
    If module is a LazyLoad object its wrapped import is reloaded and returned.
    If module is an actual ModuleType it is reloaded and returned.
    """
    if isinstance(__module, LazyLoad):
        return __module.__reload__()
    return importlib.reload(__module)