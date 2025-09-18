import asyncio
import sys
import typing as t
from types import ModuleType
from unittest import mock

import pytest

from lzl.require import LazyLib, PkgInstall, require_missing_wrapper, resolve_missing, resolve_missing_custom


def test_get_requirement_normalises_name():
    assert LazyLib.get_requirement("scikit-learn>=1.0") == "scikit_learn"


def test_pkginstall_get_args_includes_binary(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    args = PkgInstall.get_args("python", flags=["--dry-run"])
    assert "python" in args
    assert any("install" in part for part in args)


def test_lazy_import_returns_existing_module():
    module = LazyLib.get("pip")
    assert isinstance(module, ModuleType)
    assert module.__name__ == "pip"


def test_lazy_import_attribute_resolution():
    version = LazyLib.get("pip:__version__")
    assert isinstance(version, str)
    version_via_getitem = LazyLib["pip:__version__"]
    assert version_via_getitem == version


def test_resolve_missing_invokes_import(monkeypatch):
    calls: list[tuple[str, t.Optional[str]]] = []

    def fake_import(lib: str, pip_name: t.Optional[str] = None, *args, **kwargs):
        calls.append((lib, pip_name))
        return mock.Mock()

    monkeypatch.setattr(LazyLib, "import_lib", fake_import)
    resolve_missing(["pkg1", "pkg2"], ["pkgA", "pkgB"])
    assert calls == [("pkg1", "pkgA"), ("pkg2", "pkgB")]


def test_resolve_missing_custom_skips_when_available(monkeypatch):
    monkeypatch.setattr(LazyLib, "is_available", lambda name: True)
    install_mock = mock.Mock()
    monkeypatch.setattr(LazyLib, "install_library", install_mock)
    resolve_missing_custom(["pip"], ["pip"])
    install_mock.assert_not_called()


def test_require_missing_wrapper_sync(monkeypatch):
    resolver = mock.Mock()

    def do_work() -> str:
        return "done"

    wrapped = require_missing_wrapper(resolver, do_work)
    assert wrapped() == "done"
    resolver.assert_called_once_with()


def test_require_missing_wrapper_async(monkeypatch):
    resolver = mock.Mock()

    async def do_work() -> str:
        return "done"

    wrapped = require_missing_wrapper(resolver, do_work)
    assert asyncio.run(wrapped()) == "done"
    resolver.assert_called_once_with()
