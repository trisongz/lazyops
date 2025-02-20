from __future__ import annotations

"""
Support Lazy Loading of Modules

- Credit: https://github.com/kevdog824
"""

import importlib
from typing import Generic, TypeVar, Any, Dict, Any, Union, Iterable, Optional
from types import ModuleType


_M = TypeVar("_M", bound=ModuleType)


class LazyLoad(Generic[_M]):
    def __init__(
        self, 
        name: str, 
        package: str | None = None, 
        install_missing: bool = True,
        install_options: Dict[str, Any] = None,
        dependencies: Union['LazyLoad', Iterable['LazyLoad']] = None,
    ) -> None:
        self._lzlname = name  # Ridiculous name avoids name clash with module
        if dependencies and not isinstance(dependencies, list):
            dependencies = [dependencies]
        self._lzldeps: Optional[Iterable['LazyLoad']] = dependencies
        self._lzlpackage = package  # Ridiculous name avoids name clash with module
        self._lzlinstall = install_missing
        if install_missing:
            install_options = install_options or {}
            if 'package' not in install_options: install_options['package'] = package or name
            self._lzlinstall_options = install_options
        self.__module__: ModuleType | None = None

    def __do_import__(self) -> _M:
        """
        Imports the module
        """
        try:
            return importlib.import_module(self._lzlname, self._lzlpackage)
        except Exception as e:
            if self._lzlinstall:
                from lzl.require import LazyLib
                LazyLib.install_pip_package(**self._lzlinstall_options)
                return importlib.import_module(self._lzlname, self._lzlpackage)
            raise e
        
    def __do_load_dependencies__(self):
        """
        Loads the dependencies
        """
        if not self._lzldeps: return
        for dep in self._lzldeps:
            dep.__load__()
    
    def __do_reload_dependencies__(self):
        """
        Reloads the dependencies
        """
        if not self._lzldeps: return
        for dep in self._lzldeps:
            dep.__reload__()


    def __load__(self) -> _M:
        """Explicitly load the import."""
        if self.__module__ is None:
            self.__module__ = self.__do_import__()
            self.__do_load_dependencies__()
        return self.__module__

    def __reload__(self) -> _M:
        """Explicitly reload the import."""
        try:
            self.__module__ = importlib.reload(self.__module__)
            self.__do_reload_dependencies__()
        except Exception as exc:
            try:
                self.__module__ = self.__do_import__()
                self.__do_load_dependencies__()
            except Exception as e:
                raise exc from e
        return self.__module__

    def __repr__(self) -> str:
        """Gives a good representation before import is loaded.
        Uses import's __repr__ after it is loaded.
        """
        if self.__module__ is None:
            if self._lzlpackage:
                return f"<Uninitialized module '{self._lzlname}' @ '{self._lzlpackage}'>"
            return f"<Uninitialized module '{self._lzlname}'>"
        try:
            return self.__module__.__repr__()
        # Shouldn't happen unless someone del'd module __repr__ method for some reason
        except AttributeError:
            if self._lzlpackage:
                return f"<Initialized module '{self._lzlname}' @ '{self._lzlpackage}'>"
            return f"<Initialized module '{self._lzlname}'>"

    def __getattribute__(self, __name: str) -> Any:
        """Proxies attribute access to import (loads the import if not yet loaded)."""
        if __name in {
            "_lzlname",
            "_lzlpackage",
            "_lzlinstall",
            "_lzldeps",
            "_lzlinstall_options",
            "__module__",
            "__load__",
            "__reload__",
            "__do_import__",
            "__do_load_dependencies__",
            "__do_reload_dependencies__",
        }:
            return super().__getattribute__(__name)
        if self.__module__ is None:
            self.__module__ = self.__do_import__()
            self.__do_load_dependencies__()
        return getattr(self.__module__, __name)


def lazy_load(name: str, package: str | None = None, install_missing: bool = True, install_options: Dict[str, Any] = None, dependencies: Union['LazyLoad', Iterable['LazyLoad']] = None) -> LazyLoad:
    """Lazily load an import.
    Returns a LazyLoad object which won't load the import until you attempt
    attribute access, you call the load function with this object, or you call the
    __load__ method of this object.
    """
    return LazyLoad(name, package = package, install_missing = install_missing, install_options = install_options, dependencies = dependencies)


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