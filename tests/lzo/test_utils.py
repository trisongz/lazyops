from __future__ import annotations

import math

import pytest

from lzo.utils.helpers.base import extract_function_kwargs, retryable
from lzo.utils.keygen import Generate
from lzo.utils.system.utils import parse_memory_metric, parse_memory_metric_to_bs, safe_float


def sample_function(alpha: int, beta: int = 2) -> int:
    return alpha + beta


def test_extract_function_kwargs_splits_used_and_extra() -> None:
    used, extra = extract_function_kwargs(sample_function, alpha=1, gamma=3)

    assert used == {'alpha': 1}
    assert extra == {'gamma': 3}


def test_retryable_retries_sync_function() -> None:
    attempts = {'count': 0}

    @retryable(limit=3, delay=0)
    def flaky() -> int:
        attempts['count'] += 1
        if attempts['count'] < 3:
            raise ValueError('try again')
        return 42

    assert flaky() == 42
    assert attempts['count'] == 3


@pytest.mark.asyncio
async def test_retryable_handles_async_functions() -> None:
    attempts = {'count': 0}

    @retryable(limit=2, delay=0)
    async def flaky_async() -> int:
        attempts['count'] += 1
        if attempts['count'] == 1:
            raise RuntimeError('first attempt fails')
        return 7

    assert await flaky_async() == 7
    assert attempts['count'] == 2


def test_generate_uuid_passcode_truncates_length() -> None:
    token = Generate.uuid_passcode(length=8)

    assert len(token) == 8
    assert '-' not in token


def test_parse_memory_metric_supports_human_readable_units() -> None:
    assert parse_memory_metric('4Mi') == 4 * 1024 * 1024


def test_parse_memory_metric_to_byte_size_round_trips() -> None:
    result = parse_memory_metric_to_bs(1_048_576)

    assert str(result) == '1024KiB'


def test_safe_float_returns_nan_for_invalid_input() -> None:
    value = safe_float('not-a-number')

    assert math.isnan(value)
