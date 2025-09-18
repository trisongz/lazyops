from __future__ import annotations

"""Extended pydantic models and settings used throughout ``lzo``."""

import abc
import inspect
from pathlib import Path
import typing as t

from pydantic import PrivateAttr

from lzl.types import (
    BaseModel as _BaseModel,
    BaseSettings as _BaseSettings,
    ByteSize,
    ConfigDict,
    Field,
    PYDANTIC_VERSION,
    eproperty,
    field_validator,
    get_pydantic_field_names,
    get_schema_extra,
    model_validator,
    pre_root_validator,
    root_validator,
    validator,
)
from .common.appenv import AppEnv, get_app_env

if t.TYPE_CHECKING:
    from lzl.logging import Logger, NullLogger
    from lzo.types.settings.context import AppContext

ModelT = t.TypeVar('ModelT', bound='BaseModel')

__all__ = [
    'BaseModel',
    'BaseSettings',
    'ByteSize',
    'Registered',
    'RBaseModel',
    'ConfigDict',
    'Field',
    'get_schema_extra',
    'get_pydantic_field_names',
    'validator',
    'root_validator',
    'pre_root_validator',
    'field_validator',
    'model_validator',
]


class Registered(abc.ABC):
    """Mixin that auto-registers subclasses as module settings."""

    _rmodule: t.Optional[str] = None
    _rsubmodule: t.Optional[str] = None
    _rxtra: t.Dict[str, t.Any] = {}

    def __init_subclass__(cls, **kwargs: ConfigDict) -> None:  # pragma: no cover - registration glue
        from lzo.registry.settings import register_settings

        register_settings(cls)
        super().__init_subclass__(**kwargs)

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


class BaseSettings(_BaseSettings):
    """Augmented base settings with environment helpers and logging accessors."""

    app_env: t.Optional[AppEnv] = None
    debug_enabled: t.Optional[bool] = None

    if t.TYPE_CHECKING:
        _rxtra: t.Dict[str, t.Any]

    @eproperty
    def _is_registered(self) -> bool:
        """Return ``True`` when instantiated via the registry infrastructure."""

        return hasattr(self, '_rxtra')

    @eproperty
    def module_path(self) -> Path:
        """Filesystem path of the module that owns this settings object."""

        if self._is_registered and self._rxtra.get('module_path'):
            return self._rxtra['module_path']
        return super().module_path

    @eproperty
    def module_config_path(self) -> Path:
        """Directory containing configuration files for this module."""

        if self._is_registered and self._rxtra.get('module_config_path'):
            return self._rxtra['module_config_path']
        return super().module_config_path

    @eproperty
    def module_name(self) -> str:
        """Top-level package name inferred from the module namespace."""

        if self._is_registered and self._rxtra.get('module'):
            return self._rxtra['module']
        return super().module_name

    @eproperty
    def logger(self) -> 'Logger':
        """Name-spaced logger for emitting structured diagnostics."""

        from lzl.logging import logger

        return logger

    @eproperty
    def null_logger(self) -> 'NullLogger':
        """No-op logger for silencing diagnostics when debug is disabled."""

        from lzl.logging import null_logger

        return null_logger

    @eproperty
    def autologger(self) -> 'Logger':
        """Return ``logger`` when in debug contexts, else ``null_logger``."""

        return self.logger if (self.debug_enabled or self.is_development_env) else self.null_logger

    @eproperty
    def app_module_name(self) -> t.Optional[str]:
        """Override used to derive the environment prefix for this settings object."""

        return self._extra.get('app_module_name')

    @eproperty
    def ctx(self) -> t.Optional['AppContext']:
        """Return the app context when the settings is registry managed."""

        if not self._is_registered:
            return None
        from lzo.types.settings.context import AppContextManager

        return AppContextManager.get_ctx(self.module_name)

    @model_validator(mode='after')
    def validate_app_env(self) -> 'BaseSettings':
        """Populate ``app_env`` based on module or explicit overrides."""

        if self.app_env is None:
            try:
                if self.app_module_name:
                    self.app_env = AppEnv.from_module_name(self.app_module_name)
                elif self.Config.env_prefix:
                    self.app_env = get_app_env(self.Config.env_prefix.rstrip('_'))
                else:
                    self.app_env = get_app_env(self.app_module_name or self.module_name)
            except Exception:  # pragma: no cover - defensive fallback
                self.app_env = get_app_env('lzo')
        elif isinstance(self.app_env, str):
            self.app_env = AppEnv.from_env(self.app_env)
        return self

    @property
    def is_local_env(self) -> bool:
        """Return ``True`` when running in local/development contexts."""

        return self.app_env in {AppEnv.DEVELOPMENT, AppEnv.LOCAL} and not self.in_k8s

    @property
    def is_production_env(self) -> bool:
        """Return ``True`` when production deployments are detected."""

        return self.app_env == AppEnv.PRODUCTION and self.in_k8s

    @property
    def is_development_env(self) -> bool:
        """Return ``True`` when operating in development or CI modes."""

        return self.app_env in {AppEnv.DEVELOPMENT, AppEnv.LOCAL, AppEnv.CICD}

    def set_app_env(self, env: AppEnv) -> None:
        """Force the active application environment."""

        self.app_env = self.app_env.from_env(env)


class BaseModel(_BaseModel):
    """Thin wrapper over :class:`pydantic.BaseModel` with permissive extras."""

    if PYDANTIC_VERSION == 2:
        _extra: t.Dict[str, t.Any] = PrivateAttr(default_factory=dict)
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
    else:
        _extra: t.Dict[str, t.Any] = Field(default_factory=dict, exclude=True, hidden=True)

        class Config:  # noqa: D106 - pydantic compatibility shim
            extra = 'allow'
            arbitrary_types_allowed = True

    def get(self, name: str, default: t.Any = None) -> t.Any:
        """Retrieve ``name`` if present, returning ``default`` otherwise."""

        return getattr(self, name, default)

    @classmethod
    def model_validate_batch(
        cls: t.Type['ModelT'],
        items: t.Iterable[t.Any],
        *,
        strict: t.Optional[bool] = None,
        from_attributes: t.Optional[bool] = None,
        context: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs: t.Any,
    ) -> t.List['ModelT']:
        """Validate many payloads and return instantiated models."""

        return [
            cls.model_validate(item, strict=strict, from_attributes=from_attributes, context=context)
            for item in items
        ]


class RBaseModel(BaseModel):
    """Base model variant that exposes module-level metadata helpers."""

    @eproperty
    def module_path(self) -> Path:
        """Return the installation path where the module is located."""

        import pkg_resources

        path = Path(pkg_resources.get_distribution(self.module_name).location)
        if 'src' in path.name and path.joinpath(self.module_name).exists():
            path = path.joinpath(self.module_name)
        elif path.joinpath('src').exists() and path.joinpath('src', self.module_name).exists():
            path = path.joinpath('src', self.module_name)
        return path

    @eproperty
    def module_config_path(self) -> Path:
        """Directory containing the module configuration files."""

        return Path(inspect.getfile(self.__class__)).parent

    @eproperty
    def module_name(self) -> str:
        """Top-level module name inferred from the class namespace."""

        return self.__class__.__module__.split('.')[0]

    @eproperty
    def module_version(self) -> str:
        """Resolve the installed package version for this module."""

        import pkg_resources

        return pkg_resources.get_distribution(self.module_name).version

    @eproperty
    def module_pkg_name(self) -> str:
        """Return the package-relative path segment hosting configuration."""

        config_path = self.module_config_path.as_posix()
        module_path = self.module_path.as_posix()
        return config_path.replace(module_path, '').strip().split('/', 2)[1]

    @eproperty
    def in_k8s(self) -> bool:
        """Return whether the process is detected inside a Kubernetes pod."""

        from lzo.utils.system import is_in_kubernetes

        return is_in_kubernetes()


if t.TYPE_CHECKING:

    from .settings.context import AppContext

    class RegisteredSettings(BaseSettings, Registered):  # pragma: no cover - typing helper
        """Stub combining :class:`BaseSettings` and :class:`Registered`."""

        ctx: AppContext
