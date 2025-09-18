from __future__ import annotations

"""Test fixtures for exercising lzo registry behaviour."""

import typing as t


class DummyClient:
    """Simple client used to validate registry hooks."""

    _rxtra: t.Dict[str, t.Any] = {}
    name = 'dummy'

    def __init__(self, *, payload: str) -> None:
        self.payload = payload

    def transform(self) -> str:
        return self.payload.upper()


def tweak_kwargs(*, payload: str) -> dict[str, t.Any]:
    """Pretend pre-hook that adds a suffix to the payload."""

    return {'payload': f'{payload}-hooked'}


def tweak_instance(instance: DummyClient) -> DummyClient:
    """Post-hook that annotates the payload to show it ran."""

    instance.payload += '-post'
    return instance
