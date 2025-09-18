from __future__ import annotations

import typing as t

import pytest

from lzo.registry.base import MRegistry, combine_parts
from lzo.registry import clients as registry_clients

from . import fixtures


def test_combine_parts_skips_none_segments() -> None:
    assert combine_parts('module', None, 'client') == 'module.client'


def test_registry_hooks_apply_pre_and_post(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = MRegistry('test-registry', verbose=True)
    registry.register_prehook('pkg.dummy', fixtures.tweak_kwargs)
    registry.register_posthook('pkg.dummy', fixtures.tweak_instance)
    registry['pkg.dummy'] = fixtures.DummyClient

    instance = registry.get('pkg.dummy', payload='value')

    assert isinstance(instance, fixtures.DummyClient)
    assert instance.payload == 'value-hooked-post'


def test_client_registration_populates_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    temp_registry = MRegistry('clients-test')
    monkeypatch.setattr(registry_clients, '_cregistry', temp_registry)

    class InlineClient:
        _rxtra: t.Dict[str, t.Any] = {}
        name = 'inline'

        def __init__(self, *, payload: str) -> None:
            self.payload = payload

    registry_clients.register_client(InlineClient)
    module_name = InlineClient.__module__.split('.')[0]
    key = combine_parts(module_name, None, InlineClient.name)
    instance = registry_clients.get_app_client(InlineClient.name, module=module_name, payload='test')

    assert key in temp_registry.mregistry
    assert InlineClient._rxtra['client_name'] == 'inline'
    assert instance.payload == 'test'
