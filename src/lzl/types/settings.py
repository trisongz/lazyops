from __future__ import annotations

"""
Custom Pydantic BaseSettings with Module Introspection.

Provides a `BaseSettings` subclass that includes helpful properties
to automatically determine the module's path, name, version, etc.,
and methods for configuration updates and environment variable setting.
"""
import os
import inspect
# import pkg_resources
from importlib import metadata
from pathlib import Path
from .base import (
    Field,
    BaseSettings as _BaseSettings,
    PYDANTIC_VERSION,
    get_pydantic_dict,
)
from .properties import eproperty
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if PYDANTIC_VERSION == 2:
    from pydantic import PrivateAttr

if TYPE_CHECKING:
    from lzo.types import AppEnv

class BaseSettings(_BaseSettings):
    """Base class for settings, powered by Pydantic BaseSettings.

    Includes automatic environment variable loading, nested settings updates,
    and properties providing context about the module defining the settings class.

    Attributes:
        _extra (Dict[str, Any]): Private attribute for storing cached property
            values (used by `eproperty`). Handled for Pydantic v1/v2.
    """

    if PYDANTIC_VERSION == 2:
        _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)
    else:
        _extra: Dict[str, Any] = Field(default_factory = dict, exclude = True, hidden = True)

    
    class Config:
        env_prefix: str = ""
        case_sensitive: bool = False
        arbitrary_types_allowed: bool = True


    @property
    def __module_path(self) -> Path:
        """[DEPRECATED/BROKEN] Attempts to get the module root path using pkg_resources.

        Note:
            This property relies on the deprecated `pkg_resources` and might not
            work correctly, especially with modern packaging. Use `module_path`
            instead.

        Returns:
            Path: The determined module path.
        """
        # p = Path(pkg_resources.get_distribution(self.module_name).location)
        # if 'src' in p.name and p.joinpath(self.module_name).exists():
        #     p = p.joinpath(self.module_name)
        # elif p.joinpath('src').exists() and p.joinpath('src', self.module_name).exists():
        #     p = p.joinpath('src', self.module_name)
        # return p
        raise NotImplementedError("__module_path is deprecated and broken. Use module_path instead.")

    @eproperty
    def module_path(self) -> Path | None:
        """Gets the root installation directory of the settings module's package.

        Uses `importlib.metadata` to find the package location. Attempts to
        handle structures with and without a `src` layout.

        Returns:
            Optional[Path]: The path to the package directory, or None if the
                package cannot be found.
        """
        # sourcery skip: remove-redundant-path-exists
        try:
            dist = metadata.distribution(self.module_name)
            site_packages_path = Path(dist.locate_file('.'))  # Get site-packages path
            module_base_name = self.module_name.split('.')[0] # Handle submodules like pandas.plotting
            package_dir_path = site_packages_path / module_base_name # Construct package directory path
            if package_dir_path.exists() and package_dir_path.is_dir(): # Verify package dir exists
                p = package_dir_path
            else:
                # Fallback: if package dir not found (unusual but handle it), use site-packages
                p = site_packages_path

            if p.joinpath('src').exists() and p.joinpath('src', module_base_name).exists():
                p = p.joinpath('src', module_base_name)
            return p

        except metadata.PackageNotFoundError:
            return None

    @eproperty
    def module_config_path(self) -> Path:
        """Gets the directory path containing the settings class definition.

        Returns:
            Path: The path to the directory of the settings file.
        """
        return Path(inspect.getfile(self.__class__)).parent
    
    @eproperty
    def module_name(self) -> str:
        """Gets the top-level module name for the settings class.

        Example:
            If the class is defined in `my_package.config.settings`, returns 'my_package'.

        Returns:
            str: The top-level module name.
        """
        return self.__class__.__module__.split(".")[0]
    
    @eproperty
    def module_version(self) -> str:
        """Gets the installed version of the settings module's package.

        Uses `importlib.metadata`.

        Returns:
            str: The package version string.

        Raises:
            importlib.metadata.PackageNotFoundError: If the package is not found.
        """
        return metadata.version(self.module_name)
        # return pkg_resources.get_distribution(self.module_name).version
    
    @eproperty
    def module_pkg_name(self) -> str:
        """Determines the likely package source directory name within the module path.

        Tries to infer if the structure is `module_path/src/...` or
        `module_path/package_name/...` based on the config file location.

        Returns:
            str: The inferred package directory name (e.g., 'src' or 'my_package').
        """
        config_path = self.module_config_path.as_posix()
        module_path = self.module_path.as_posix()
        return config_path.replace(module_path, "").strip().split("/", 2)[1]

    @eproperty
    def in_k8s(self) -> bool:
        """Checks if the application is running within a Kubernetes environment.

        Returns:
            bool: True if running in Kubernetes, False otherwise.
        """
        from lzo.utils.system import is_in_kubernetes
        return is_in_kubernetes()
    
    @eproperty
    def host_name(self) -> str:
        """Gets the hostname of the current machine.

        Returns:
            str: The hostname.
        """
        from lzo.utils.system import get_host_name
        return get_host_name()

    def update_config(self, **kwargs):
        """Recursively updates the settings fields from keyword arguments.

        Handles nested `BaseSettings` instances and `Path` objects.

        Args:
            **kwargs: Keyword arguments mapping setting names to new values.
                Keys not corresponding to settings fields are ignored.
        """
        for k, v in kwargs.items():
            if not hasattr(self, k): continue
            if isinstance(getattr(self, k), Path):
                setattr(self, k, Path(v))
            elif isinstance(getattr(self, k), self.__class__):
                val = getattr(self, k)
                if hasattr(val, 'update_config'):
                    val.update_config(**v)
                else: val = val.__class__(**v)
                setattr(self, k, val)
            else: 
                setattr(self, k, v)


    def set_envvars(self):
        """Sets environment variables based on the current settings values.

        Iterates through settings fields, converting values to strings and
        setting corresponding environment variables (prefixed with
        `Config.env_prefix` and uppercased).
        Recursively calls `set_envvars` for nested `BaseSettings` instances.
        """
        data = get_pydantic_dict(self, exclude_none=True)
        for k, v in data.items():
            if isinstance(v, BaseSettings):
                v.set_envvars()
            else:
                os.environ[self.Config.env_prefix + k.upper()] = str(v)
    

    def get(self, name: str, default: Any = None):
        """Gets an attribute from the settings instance, returning a default if not found.

        Args:
            name: The name of the attribute (setting field) to retrieve.
            default: The value to return if the attribute does not exist.
                Defaults to None.

        Returns:
            Any: The value of the attribute or the default.
        """
        return getattr(self, name, default)


    @classmethod
    def _fetch_app_env(cls, module: Optional[str] = None) -> Optional['AppEnv']:
        """Determines the application environment (`AppEnv`).

        Uses `lzo.types.AppEnv.from_module_name` to determine the environment
        based on the provided module name or the class's module.

        Args:
            module (Optional[str]): The module name to use for environment
                detection. Defaults to the module of the settings class.

        Returns:
            Optional[AppEnv]: The determined AppEnv member, or None if it
                cannot be determined (although `from_module_name` usually
                returns a default).
        """
        if module is None: module = cls.__module__.split('.')[0]
        from lzo.types import AppEnv
        return AppEnv.from_module_name(module)
