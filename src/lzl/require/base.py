from __future__ import annotations

"""Utilities for lazily installing and importing optional dependencies."""

import functools
import importlib
import importlib.metadata
import inspect
import os
import pathlib
import shlex
import subprocess
import sys
import typing as t
from types import ModuleType

from lzl.logging import default_logger as logger

__all__ = [
    "PkgInstall",
    "LazyLibType",
    "LazyLib",
    "resolve_missing",
    "resolve_missing_custom",
    "require_missing_wrapper",
]


def get_variable_separator() -> str:
    """Return the PATH separator for the current operating system."""

    return ";" if sys.platform.startswith("win") else ":"


def is_coro_func(obj: t.Any, func_name: str | None = None) -> bool:
    """Return ``True`` when ``obj`` (or ``obj.func_name``) is awaitable."""

    try:
        if inspect.iscoroutinefunction(obj) or inspect.isawaitable(obj):
            return True
        if func_name and hasattr(obj, func_name) and inspect.iscoroutinefunction(
            getattr(obj, func_name)
        ):
            return True
        return bool(hasattr(obj, "__call__") and inspect.iscoroutinefunction(obj.__call__))
    except Exception:  # pragma: no cover - mirrors legacy permissive behaviour
        return False


class PkgInstall:
    """Platform-specific installer command templates."""

    win: str = "choco install [flags]"
    mac: str = "brew [flags] install"
    linux: str = "apt-get -y [flags] install"

    @classmethod
    def get_args(cls, binary: str, flags: list[str] | None = None) -> list[str]:
        """Return a shell-escaped argument list for installing ``binary``."""

        flag_str = " ".join(flags) if flags else ""
        if sys.platform.startswith("win"):
            command = f"{cls.win} {binary}".replace("[flags]", flag_str)
        elif sys.platform.startswith("linux"):
            command = f"{cls.linux} {binary}".replace("[flags]", flag_str)
        else:
            command = f"{cls.mac} {binary}".replace("[flags]", flag_str)
        return shlex.split(command)


_has_uv_available: bool | None = None


def _has_uv() -> bool:
    """Return ``True`` when the ``uv`` CLI is available on PATH."""

    global _has_uv_available
    if _has_uv_available is None:
        _has_uv_available = LazyLib.is_exec_available("uv")
    return _has_uv_available


class LazyLibType(type):
    """Metaclass providing lazy import/install helpers."""

    @classmethod
    def install_binary(cls, binary: str, flags: list[str] | None = None) -> None:
        if cls.get_binary_path(binary):
            return
        args = PkgInstall.get_args(binary, flags)
        subprocess.check_call(args, stdout=subprocess.DEVNULL)

    @classmethod
    def get_requirement(cls, name: str, clean: bool = True) -> str:
        name = name.replace("-", "_")
        return name.split("=")[0].replace(">", "").replace("<", "").strip() if clean else name.strip()

    @classmethod
    def install_library(cls, library: str, upgrade: bool = True) -> None:
        if _has_uv():
            try:
                pip_exec = ["uv", "pip", "install"]
                if "=" not in library or upgrade:
                    pip_exec.append("--upgrade")
                pip_exec.append(library)
                subprocess.check_call(pip_exec, stdout=subprocess.DEVNULL)
                return
            except Exception as exc:  # pragma: no cover - fallback path
                logger.warning("Failed to install %s using uv: %s. Falling back to pip.", library, exc)

        pip_exec = [sys.executable, "-m", "pip", "install"]
        if "=" not in library or upgrade:
            pip_exec.append("--upgrade")
        pip_exec.append(library)
        subprocess.check_call(pip_exec, stdout=subprocess.DEVNULL)

    @classmethod
    def install_pip_package(
        cls,
        package: str,
        version: str | None = None,
        **options: t.Any,
    ) -> None:
        if _has_uv():
            try:
                if version:
                    if "=" not in version:
                        version = f"=={version}"
                    package = f"{package}{version}"
                pip_exec = ["uv", "pip", "install", package]
                for key, value in options.items():
                    opt = key if key.startswith("--") else f"--{key}"
                    if value and not isinstance(value, bool):
                        pip_exec.append(f"{opt}={value}")
                    else:
                        pip_exec.append(opt)
                subprocess.check_call(pip_exec, stdout=subprocess.DEVNULL)
                return
            except Exception as exc:  # pragma: no cover - fallback path
                logger.warning("Failed to install %s using uv: %s. Falling back to pip.", package, exc)

        pip_exec = [sys.executable, "-m", "pip", "install"]
        for key, value in options.items():
            opt = key if key.startswith("--") else f"--{key}"
            if value and not isinstance(value, bool):
                pip_exec.append(f"{opt}={value}")
            else:
                pip_exec.append(opt)
        if version:
            if "=" not in version:
                version = f"=={version}"
            package = f"{package}{version}"
        pip_exec.append(package)
        subprocess.check_call(pip_exec, stdout=subprocess.DEVNULL)

    @classmethod
    def is_available(cls, library: str) -> bool:
        try:
            importlib.metadata.version(library)
            return True
        except importlib.metadata.PackageNotFoundError:
            return False

    @classmethod
    def __is_available(cls, library: str) -> bool:
        try:
            import pkg_resources
        except ImportError:
            cls.install_pip_package("setuptools")
            import pkg_resources
        try:
            pkg_resources.get_distribution(library)
            return True
        except pkg_resources.DistributionNotFound:  # pragma: no cover - legacy path
            return False

    @classmethod
    def is_imported(cls, library: str) -> bool:
        return library in sys.modules

    @classmethod
    def _ensure_lib_imported(cls, library: str) -> ModuleType:
        clean_lib = cls.get_requirement(library, True)
        if not cls.is_imported(clean_lib):
            sys.modules[clean_lib] = importlib.import_module(clean_lib)
        return sys.modules[clean_lib]

    @classmethod
    def _ensure_lib_installed(cls, library: str, pip_name: str | None = None, upgrade: bool = False) -> None:
        clean_lib = cls.get_requirement(library, True)
        if not cls.is_available(clean_lib):
            cls.install_library(pip_name or library, upgrade=upgrade)

    @classmethod
    def _ensure_binary_installed(cls, binary: str, flags: list[str] | None = None) -> None:
        cls.install_binary(binary, flags)

    @classmethod
    def import_lib(
        cls,
        library: str,
        pip_name: str | None = None,
        resolve_missing: bool = True,
        require: bool = False,
        upgrade: bool = False,
    ) -> ModuleType:
        clean_lib = cls.get_requirement(library, True)
        if not cls.is_available(clean_lib):
            if require and not resolve_missing:
                raise ImportError(f"Required Lib {library} is not available.")
            if not resolve_missing:
                return None  # type: ignore[return-value]
            cls.install_library(pip_name or library, upgrade=upgrade)
        return cls._ensure_lib_imported(library)

    @classmethod
    def import_module(
        cls,
        name: str,
        library: str | None = None,
        pip_name: str | None = None,
        resolve_missing: bool = True,
        require: bool = False,
        upgrade: bool = False,
    ) -> ModuleType:
        if library:
            cls.import_lib(library, pip_name, resolve_missing, require, upgrade)
            return importlib.import_module(name, package=library)
        return importlib.import_module(name)

    @classmethod
    def import_module_attr(
        cls,
        name: str,
        module_name: str,
        library: str | None = None,
        pip_name: str | None = None,
        resolve_missing: bool = True,
        require: bool = False,
        upgrade: bool = False,
    ) -> t.Any:
        module = cls.import_module(
            name=module_name,
            library=library,
            pip_name=pip_name,
            resolve_missing=resolve_missing,
            require=require,
            upgrade=upgrade,
        )
        return getattr(module, name)

    @classmethod
    def import_cmd(
        cls,
        binary: str,
        resolve_missing: bool = True,
        require: bool = False,
        flags: list[str] | None = None,
    ) -> t.Any:
        if not cls.is_exec_available(binary):
            if require and not resolve_missing:
                raise ImportError(f"Required Executable {binary} is not available.")
            if not resolve_missing:
                return None
            cls.install_binary(binary, flags=flags)
        from lazy.cmd import Cmd  # type: ignore

        return Cmd(binary=binary)

    @classmethod
    def get_binary_path(cls, executable: str) -> str | None:
        if "PATH" not in os.environ:
            return None
        for directory in os.environ["PATH"].split(get_variable_separator()):
            binary = os.path.abspath(os.path.join(directory, executable))
            if os.path.isfile(binary) and os.access(binary, os.X_OK):
                return binary
        return None

    @classmethod
    def is_exec_available(cls, executable: str) -> bool:
        return cls.get_binary_path(executable) is not None

    @staticmethod
    def reload_module(module: ModuleType) -> ModuleType:
        return importlib.reload(module)

    @staticmethod
    def get_cwd(*paths: t.Any, string: bool = True) -> str | pathlib.Path:
        if not paths:
            return pathlib.Path.cwd().as_posix() if string else pathlib.Path.cwd()
        resolved = pathlib.Path.cwd().joinpath(*paths)
        return resolved.as_posix() if string else resolved

    @staticmethod
    def run_cmd(cmd: str, raise_error: bool = True) -> str:
        try:
            out = subprocess.check_output(cmd, shell=True)
            return out.decode("utf8") if isinstance(out, bytes) else out.strip()
        except Exception as exc:
            if not raise_error:
                return ""
            raise exc

    def __getattr__(cls, key: str) -> t.Any:
        if key.startswith("is_avail_bin_") or key.startswith("is_avail_exec_"):
            exec_name = key.split("_", 3)[-1].strip()
            return cls.is_exec_available(exec_name)
        if key.startswith("is_avail_lib_") or key.startswith("is_avail_"):
            lib_name = key.split("is_avail_")[-1].strip()
            return cls.is_available(lib_name)
        if key.startswith("is_imported_"):
            lib_name = key.split("is_imported_")[-1].strip()
            return cls.is_imported(lib_name)
        if key.startswith("cmd_"):
            binary_name = key.split("cmd_")[-1].strip()
            return cls.import_cmd(binary=binary_name)
        return cls.import_lib(key, resolve_missing=False, require=False)

    @classmethod
    def get(
        cls,
        name: str,
        attr_name: str | None = None,
        pip_name: str | None = None,
        resolve_missing: bool = True,
    ) -> ModuleType | t.Any:
        parsed = cls._parse_name(name)
        if attr_name is not None:
            parsed["attr_name"] = attr_name
        if pip_name is not None:
            parsed["pip_name"] = pip_name

        library = t.cast(str, parsed["library"])
        module_name = parsed["module_name"] or library

        if parsed.get("attr_name"):
            return cls.import_module_attr(
                parsed["attr_name"],
                module_name=module_name,
                library=library,
                pip_name=parsed["pip_name"],
                resolve_missing=resolve_missing,
            )
        if parsed.get("module_name"):
            return cls.import_module(
                module_name,
                library=library,
                pip_name=parsed["pip_name"],
                resolve_missing=resolve_missing,
            )
        return cls.import_lib(library, pip_name=parsed["pip_name"], resolve_missing=resolve_missing)

    @classmethod
    def _parse_name(cls, name: str) -> dict[str, str | None]:
        result: dict[str, str | None] = {
            "library": "",
            "pip_name": None,
            "module_name": None,
            "attr_name": None,
        }
        current = name.strip()
        if ":" in current:
            current, attr = current.split(":", 1)
            result["attr_name"] = attr
        if "|" in current:
            pip, current = current.split("|", 1)
            result["pip_name"] = pip
        if "." in current:
            result["module_name"] = current
            result["library"] = current.split(".", 1)[0]
        else:
            result["library"] = current
        return result

    @classmethod
    def __getitem__(cls, name: str) -> ModuleType:
        parsed = cls._parse_name(name)
        library = t.cast(str, parsed["library"])
        module_name = parsed["module_name"] or library
        if parsed.get("attr_name"):
            return cls.import_module_attr(
                parsed["attr_name"],
                module_name=module_name,
                library=library,
                pip_name=parsed["pip_name"],
                resolve_missing=True,
                require=True,
            )
        if parsed.get("module_name"):
            return cls.import_module(
                name=parsed["module_name"],
                library=library,
                pip_name=parsed["pip_name"],
                resolve_missing=True,
                require=True,
            )
        return cls.import_lib(
            library,
            pip_name=parsed["pip_name"],
            resolve_missing=True,
            require=True,
        )


class LazyLib(metaclass=LazyLibType):
    """Concrete helper exposing ``LazyLibType`` utilities via attribute access."""

    pass


def resolve_missing(
    modules: str | list[str],
    packages: str | list[str] | None = None,
    required: bool = True,
) -> None:
    if not isinstance(modules, list):
        modules = [modules]
    if packages is not None and not isinstance(packages, list):
        packages = [packages]
    elif packages is None:
        packages = modules
    kind = "required" if required else "optionally required"
    logger.info("%s are %s. Installing...", ", ".join(modules), kind)
    for module, pkg in zip(modules, packages):
        LazyLib.import_lib(module, pkg)


def resolve_missing_custom(
    modules: str | list[str],
    packages: str | list[str] | None = None,
    required: bool = True,
) -> None:
    if not isinstance(modules, list):
        modules = [modules]
    if packages is not None and not isinstance(packages, list):
        packages = [packages]
    elif packages is None:
        packages = modules

    module_names = [module.split(" ", 1)[0] for module in modules]
    kind = "required" if required else "optionally required"
    logger.info("%s are %s. Installing...", ", ".join(module_names), kind)
    for module, pkg in zip(modules, packages):
        module_name = LazyLib.get_requirement(module, True)
        if LazyLib.is_available(module_name):
            continue
        LazyLib.install_library(pkg)


def require_missing_wrapper(
    resolver: t.Callable[..., None],
    func: t.Callable[..., t.Any],
    **resolver_kwargs: t.Any,
) -> t.Callable[..., t.Any]:
    if is_coro_func(func):

        @functools.wraps(func)
        async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            resolver(**resolver_kwargs)
            return await func(*args, **kwargs)

        return async_wrapper

    @functools.wraps(func)
    def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        resolver(**resolver_kwargs)
        return func(*args, **kwargs)

    return wrapper


_require_registry: dict[str, bool] = {}
