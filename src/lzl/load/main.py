from __future__ import annotations

"""Utilities for lazily importing optional dependencies.

The helpers mirror the original design from
https://github.com/kevdog824 while adapting the interface to LazyOps-specific
needs.  All behaviour remains identical; the improvements here focus on
providing richer inline documentation so that automated tooling can generate
meaningful reference pages.
"""

import importlib
import typing as t
from types import ModuleType


_M = t.TypeVar("_M", bound=ModuleType)


__all__ = ["LazyLoad", "lazy_load", "load", "reload"]


class LazyLoad(t.Generic[_M]):
    """Proxy object that defers importing a module until it is accessed.

    Parameters
    ----------
    name:
        The absolute or relative module name that should be imported lazily.
    package:
        Package name used as the anchor for relative imports.  Mirrors
        :func:`importlib.import_module`.
    install_missing:
        When ``True`` (default) missing dependencies are installed via
        :mod:`lzl.require`.  This mirrors the legacy behaviour and is kept for
        backwards compatibility.
    install_options:
        Keyword arguments forwarded to
        :meth:`lzl.require.LazyLib.install_pip_package` if installation is
        required.
    dependencies:
        An optional dependency or iterable of dependencies that should be
        loaded before the target module becomes available.  Each dependency is
        expected to be another :class:`LazyLoad` instance.
    """

    def __init__(
        self, 
        name: str, 
        package: str | None = None, 
        install_missing: bool = True,
        install_options: t.Optional[t.Dict[str, t.Any]] = None,
        dependencies: t.Optional[t.Union['LazyLoad', t.Iterable['LazyLoad']]] = None,
    ) -> None:
        self._lzlname = name  # Ridiculous name avoids name clash with module
        if dependencies and not isinstance(dependencies, list):
            dependencies = [dependencies]
        self._lzldeps: t.Optional[t.Iterable['LazyLoad']] = dependencies
        self._lzlpackage = package  # Ridiculous name avoids name clash with module
        self._lzlinstall = install_missing
        if install_missing:
            install_options = install_options or {}
            if 'package' not in install_options: install_options['package'] = package or name
            self._lzlinstall_options = install_options
        self.__module__: ModuleType | None = None

    def __do_import__(self) -> _M:
        """Import the target module, optionally installing missing deps."""
        try:
            return importlib.import_module(self._lzlname, self._lzlpackage)
        except Exception as e:
            if self._lzlinstall:
                from lzl.require import LazyLib
                LazyLib.install_pip_package(**self._lzlinstall_options)
                return importlib.import_module(self._lzlname, self._lzlpackage)
            raise e
        
    def __do_load_dependencies__(self) -> None:
        """Ensure any declared lazy dependencies are loaded."""
        if not self._lzldeps: return
        for dep in self._lzldeps:
            dep.__load__()
    
    def __do_reload_dependencies__(self) -> None:
        """Force reload on dependencies before returning the module."""
        if not self._lzldeps: return
        for dep in self._lzldeps:
            dep.__reload__()


    def __load__(self) -> _M:
        """Explicitly load the import if it has not already been resolved."""
        if self.__module__ is None:
            self.__module__ = self.__do_import__()
            self.__do_load_dependencies__()
        return self.__module__

    def __reload__(self) -> _M:
        """Force a reload of the proxied module and its dependencies."""
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
        """Return a helpful representation regardless of load state."""
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

    def __getattribute__(self, __name: str) -> t.Any:
        """Proxy attribute access to the resolved module when available."""
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


def lazy_load(
    name: str,
    package: str | None = None,
    install_missing: bool = True,
    install_options: t.Optional[t.Dict[str, t.Any]] = None,
    dependencies: t.Optional[t.Union["LazyLoad", t.Iterable["LazyLoad"]]] = None,
) -> LazyLoad:
    """Create a :class:`LazyLoad` proxy for a module import.

    Returns
    -------
    LazyLoad
        A proxy object that defers the import until attribute access occurs.
    """

    return LazyLoad(
        name,
        package=package,
        install_missing=install_missing,
        install_options=install_options,
        dependencies=dependencies,
    )


def load(__module: LazyLoad | _M) -> _M:
    """Eagerly resolve a lazy module and return the imported module object."""

    return __module.__load__() if isinstance(__module, LazyLoad) else __module


def reload(__module: LazyLoad | _M) -> _M:
    """Reload a module regardless of whether it is proxied or real."""

    if isinstance(__module, LazyLoad):
        return __module.__reload__()
    return importlib.reload(__module)
