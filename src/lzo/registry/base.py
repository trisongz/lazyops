from __future__ import annotations

"""Utilities for building lazy-loading registries."""

import inspect
import os
from pathlib import Path
import typing as t

from lzl.proxied import ProxyObject
from lzo.utils.state import TempData

RT = t.TypeVar('RT')

__all__ = ['combine_parts', 'MRegistry']


def combine_parts(*parts: t.Optional[str], sep: str = '.') -> str:
    """Join non-empty fragments into a dotted identifier.

    Args:
        *parts: Sequence of string fragments that may include ``None`` values.
        sep: Delimiter inserted between fragments. Defaults to ``'.'``.

    Returns:
        A single string containing the provided fragments joined by ``sep``.
    """

    return sep.join(p for p in parts if p)


class MRegistry(t.Generic[RT]):
    """Mutable registry that lazily initialises and caches objects.

    The registry stores three parallel maps:

    - ``mregistry`` for classes/functions registered ahead of time.
    - ``uninit_registry`` for dotted import paths that are resolved on demand.
    - ``init_registry`` for concrete instances that have been constructed.

    Hooks can be attached to modify kwargs before instantiation (``prehooks``)
    or the resulting object after instantiation (``posthooks``).
    """

    mregistry: t.ClassVar[t.Dict[str, t.Type[RT]]] = {}
    uninit_registry: t.ClassVar[t.Dict[str, str]] = {}
    init_registry: t.ClassVar[t.Dict[str, RT]] = {}

    prehooks: t.ClassVar[t.Dict[str, t.Callable[..., t.Any]]] = {}
    posthooks: t.ClassVar[t.Dict[str, t.Callable[..., t.Any]]] = {}

    def __init__(
        self,
        name: str,
        verbose: t.Optional[bool] = False,
        **kwargs: t.Any,
    ) -> None:
        """Initialise the registry with a display name and verbosity flag.

        Args:
            name: Friendly name used when logging registration activity.
            verbose: Enables additional logging when objects are created.
            **kwargs: Forwarded for compatibility; unused presently.
        """

        from lzl.io.ser import get_object_classname
        from lzl.load import lazy_import
        from lzl.logging import logger

        self.name = name
        self.logger = logger
        self.get_classname = get_object_classname
        self.lazy_import = lazy_import
        self.verbose = verbose
        self.idx: t.Dict[str, RT] = {}
        self._extra: t.Dict[str, t.Any] = {}

    def _register(self, key: str, value: RT) -> None:
        """Store a class/constructor in the registry, replacing existing values."""

        self.mregistry[key] = value
        if key in self.uninit_registry:
            self.uninit_registry.pop(key)
        if os.getenv('MUTE_LZ_REGISTRY', 'false').lower() in {'true', '1'}:
            return
        if not isinstance(value, str) and getattr(value, '_rverbose', self.verbose):
            if not TempData.has_logged(f'lzo.registry.register:{key}'):
                self.logger.info(
                    f'Registered: {key}',
                    colored=True,
                    prefix=self.name,
                )

    def __setitem__(self, key: str, value: RT) -> None:
        """Alias for :meth:`_register` so the registry mimics a mapping."""

        self._register(key, value)

    def register_prehook(self, key: str, func: t.Union[t.Callable[..., t.Any], str]) -> None:
        """Attach a callable executed before an object is instantiated."""

        self.prehooks[key] = func

    def register_posthook(self, key: str, func: t.Union[t.Callable[..., t.Any], str]) -> None:
        """Attach a callable executed after an object is instantiated."""

        self.posthooks[key] = func

    def register_hook(
        self,
        key: str,
        func: t.Union[t.Callable[..., t.Any], str],
        kind: t.Literal['pre', 'post'] = 'pre',
    ) -> None:
        """Convenience wrapper for registering pre- or post-hooks."""

        if kind == 'pre':
            self.register_prehook(key, func)
        elif kind == 'post':
            self.register_posthook(key, func)

    def run_obj_init(
        self,
        key: str,
        obj: t.Union[t.Type[RT], RT],
        **kwargs: t.Any,
    ) -> RT:
        """
        Instantiates an object (or invokes a callable) and executes configured hooks.

        If a 'prehook' is registered for the key, it modifies the `kwargs` before instantiation.
        If a 'posthook' is registered, it receives the instantiated object and can modify or replace it.

        Args:
            key: The registry key associated with the object.
            obj: The callable/class to instantiate, or an existing instance.
            **kwargs: Arguments to pass to the object constructor/callable.

        Returns:
            The initialized (and potentially modified) object.
        """

        if key in self.prehooks:
            if isinstance(self.prehooks[key], str):
                self.prehooks[key] = self.lazy_import(self.prehooks[key])
            kwargs = self.prehooks[key](**kwargs)

        if isinstance(obj, ProxyObject):
            if self.verbose:
                self.logger.info(
                    f'Skipping Initialization for Proxy Object: {key}',
                    colored=True,
                    prefix=self.name,
                )
        else:
            obj = obj(**kwargs)

        if key in self.posthooks:
            if isinstance(self.posthooks[key], str):
                self.posthooks[key] = self.lazy_import(self.posthooks[key])
            obj = self.posthooks[key](obj)
        return obj

    def _register_initialized(self, key: str, value: RT) -> None:
        """Cache an already-instantiated object for repeated retrieval."""

        self.init_registry[key] = value

    def _get(
        self,
        key: str,
        _raise_error: bool = True,
        **kwargs: t.Any,
    ) -> RT:
        """Resolve the concrete object backing ``key`` without memoisation."""

        if key in self.init_registry:
            return self.init_registry[key]

        if key in self.uninit_registry:
            _path = self.uninit_registry[key]
            _obj = self.lazy_import(_path)
            self.init_registry[key] = self.run_obj_init(key, _obj, **kwargs)
            self.uninit_registry.pop(key, None)
            return self.init_registry[key]

        if key in self.mregistry:
            _obj = self.mregistry[key]
            self.init_registry[key] = self.run_obj_init(key, _obj, **kwargs)
            return self.init_registry[key]

        if not _raise_error:
            return None
        raise KeyError(f'Key {key} not found in {self.name}')

    def get(self, key: str, **kwargs: t.Any) -> RT:
        """Public accessor that memoises lookups for repeat calls."""

        if key in self.idx:
            return self.idx[key]
        if (item := self._get(key, _raise_error=False, **kwargs)) is not None:
            self.idx[key] = item
            return item
        if possible_key := self.search_for_parent(key, raise_error=False):
            if possible_key in self.idx:
                self.idx[key] = self.idx[possible_key]
                return self.idx[key]
            if (item := self._get(possible_key, _raise_error=False, **kwargs)) is not None:
                self.idx[key] = item
                return item
        raise KeyError(
            f'Key {key} not found in {self.name}: '
            f'init: `{list(self.init_registry.keys())}`, '
            f'idx: `{list(self.idx.keys())}`'
        )

    def get_module_path(self, obj: t.Type[RT]) -> Path:
        """Return the filesystem path where ``obj`` is defined."""

        return Path(inspect.getfile(obj)).parent

    def search_for_parent(self, key: str, raise_error: bool = True) -> t.Optional[str]:
        """Find a registry key that ends with ``key`` (supports partial lookups)."""

        if self.init_registry:
            for k in self.init_registry:
                if k.endswith(key):
                    return k

        if self.uninit_registry:
            for k in self.uninit_registry:
                if k.endswith(key):
                    return k

        if self.mregistry:
            for k in self.mregistry:
                if k.endswith(key):
                    return k

        if not raise_error:
            return None
        raise KeyError(f'Key {key} not found in {self.name}')

    def __getitem__(self, key: str) -> RT:
        """Allow bracket-notation access (``registry[key]``)."""

        return self.get(key)
