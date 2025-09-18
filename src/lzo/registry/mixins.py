from __future__ import annotations

"""Shared mixins for auto-registering LazyOps components."""

import abc
import copy
import typing as t

if t.TYPE_CHECKING:
    from pathlib import Path
    from pydantic import ConfigDict

__all__ = [
    'ExtraMeta',
    'RegisteredClient',
    'RegisteredObject',
    'RegisteredSettings',
    'add_extra_meta',
]


def add_extra_meta(obj: t.Type['ExtraMeta']) -> None:
    """Populate bookkeeping metadata on registration-aware classes.

    Args:
        obj: Class that derives from :class:`ExtraMeta`.
    """

    import inspect
    from pathlib import Path

    from lzl.io.ser import get_object_classname
    from lzl.logging import logger

    cls_name = get_object_classname(obj, is_type=True)
    cls_module = obj.__module__.split('.')[0]
    module_lib_path = Path(inspect.getfile(obj)).parent
    obj._rxtra['module'] = cls_module
    obj._rxtra['cls_name'] = cls_name
    obj._rxtra['module_lib_path'] = module_lib_path
    logger.debug('Registered meta for %s.%s', cls_module, cls_name)
    if '__main__' in cls_module:
        return

    p = module_lib_path
    m_path, iters = None, 0
    while p.name != cls_module and iters < 4:
        p = p.parent
        iters += 1
        if p.name == cls_module:
            m_path = p
            break
    if m_path is not None:
        obj._rxtra['module_path'] = m_path


class ExtraMeta(abc.ABC):
    """Base class that captures module and path metadata for registries."""

    _rxtra: t.Dict[str, t.Any] = {}

    def __init_subclass__(cls, **kwargs: t.Any) -> None:  # pragma: no cover - instrumentation
        add_extra_meta(cls)
        super().__init_subclass__(**kwargs)

    @property
    def module_path(self) -> 'Path':
        """Absolute path to the package containing the class."""

        return self._rxtra.get('module_path')

    @property
    def module_lib_path(self) -> 'Path':
        """Filesystem path of the module where the class is defined."""

        return self._rxtra.get('module_lib_path')

    @property
    def module_name(self) -> str:
        """Dotted module name derived from the class namespace."""

        return self._rxtra.get('module')

    @property
    def cls_name(self) -> str:
        """Original class name captured during registration."""

        return self._rxtra.get('cls_name')


class RegisteredClient(abc.ABC):
    """Mixin that auto-registers client classes with :mod:`lzo.registry`."""

    name: t.Optional[str] = None
    _rxtra: t.Dict[str, t.Any] = {}
    _rmodule: t.Optional[str] = None
    _rsubmodule: t.Optional[str] = None

    if t.TYPE_CHECKING:
        enable_registration: bool

    def __init_subclass__(cls, **kwargs: t.Any) -> None:  # pragma: no cover - registration glue
        if not hasattr(cls, 'enable_registration') or cls.enable_registration is True:
            from lzo.registry.clients import register_client

            register_client(cls)
        super().__init_subclass__(**kwargs)

    @classmethod
    def configure_registered(cls, **kwargs: t.Any) -> 'RegisteredClient':
        """Return a copy of ``cls`` with overridden registration metadata."""

        new_cls = copy.deepcopy(cls)
        if kwargs.get('module'):
            new_cls._rmodule = kwargs.pop('module')
        if kwargs.get('submodule'):
            new_cls._rsubmodule = kwargs.pop('submodule')
        if kwargs.get('name'):
            new_cls.name = kwargs.pop('name')
        if kwargs:
            new_cls._rxtra.update(kwargs)
        return new_cls


class RegisteredObject(abc.ABC):
    """Mixin that registers singleton-like objects for lazy access."""

    name: t.Optional[str] = None
    kind: t.Optional[str] = None

    _rxtra: t.Dict[str, t.Any] = {}
    _rmodule: t.Optional[str] = None

    def __init_subclass__(cls, **kwargs: t.Any) -> None:  # pragma: no cover - registration glue
        from lzo.registry.clients import register_client

        register_client(cls)
        super().__init_subclass__(**kwargs)

    @classmethod
    def configure_registered(cls, **kwargs: t.Any) -> 'RegisteredObject':
        """Return a copy of ``cls`` with custom registration metadata."""

        new_cls = copy.deepcopy(cls)
        if kwargs.get('module'):
            new_cls._rmodule = kwargs.pop('module')
        if kwargs.get('kind'):
            new_cls.kind = kwargs.pop('kind')
        if kwargs.get('name'):
            new_cls.name = kwargs.pop('name')
        if kwargs:
            new_cls._rxtra.update(kwargs)
        return new_cls


class RegisteredSettings(abc.ABC):
    """Mixin that registers pydantic settings classes with the registry."""

    _rmodule: t.Optional[str] = None
    _rsubmodule: t.Optional[str] = None
    _rxtra: t.Dict[str, t.Any] = {}

    def __init_subclass__(cls, **kwargs: 'ConfigDict') -> None:  # pragma: no cover - registration glue
        from lzo.registry.settings import register_settings

        register_settings(cls)
        super().__init_subclass__(**kwargs)

    @classmethod
    def configure_registered(cls, **kwargs: t.Any) -> 'RegisteredSettings':
        """Return a copy of ``cls`` with overridden registry metadata."""

        new_cls = copy.deepcopy(cls)
        if kwargs.get('module'):
            new_cls._rmodule = kwargs.pop('module')
        if kwargs.get('submodule'):
            new_cls._rsubmodule = kwargs.pop('submodule')
        if kwargs:
            new_cls._rxtra.update(kwargs)
        return new_cls

    @property
    def _rverbose(self) -> bool:
        """Flag controlling whether verbose logging is enabled for this class."""

        return self._rxtra.get('verbose', False)

    if t.TYPE_CHECKING:

        @property
        def module_path(self) -> Path:  # pragma: no cover - typing helper
            ...

        @property
        def module_config_path(self) -> Path:  # pragma: no cover - typing helper
            ...

        @property
        def module_name(self) -> str:  # pragma: no cover - typing helper
            ...
