from __future__ import annotations

import typing as t

import pytest

from lzo.types import AppEnv, BaseModel, BaseSettings


class BatchModel(BaseModel):
    value: int


class ExampleSettings(BaseSettings):
    value: int = 10

    class Config:
        env_prefix = 'EXAMPLE_'


def test_model_validate_batch_produces_instances() -> None:
    payload = [{'value': 1}, {'value': 2}]

    instances = BatchModel.model_validate_batch(payload)

    assert [item.value for item in instances] == [1, 2]


@pytest.mark.parametrize('input_value, expected', [
    ('development', AppEnv.DEVELOPMENT),
    ('production', AppEnv.PRODUCTION),
])
def test_settings_validate_app_env_normalises_strings(input_value: str, expected: AppEnv) -> None:
    settings = ExampleSettings(app_env=input_value)

    assert settings.app_env == expected
