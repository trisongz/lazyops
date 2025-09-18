from __future__ import annotations

import typing as t
from functools import lru_cache

if t.TYPE_CHECKING:
    from pydantic.types import ByteSize

__all__ = ['parse_memory_metric', 'parse_memory_metric_to_bs', 'safe_float']


def parse_memory_metric(data: t.Union[int, float, str]) -> float:
    """Convert Kubernetes-style memory strings (``Mi``, ``Gi``) into bytes."""

    if isinstance(data, (int, float)): return data
    if data.endswith('B'): 
        data = data[:-1]
    cast_type = float if '.' in data else int
    if data.endswith('Ki') or data.endswith('KiB'):
        return cast_type(data.split('Ki')[0].strip()) * 1024
    if data.endswith('Mi') or data.endswith('MiB'):
        return cast_type(data.split('Mi')[0].strip()) * (1024 * 1024)
    if data.endswith('Gi') or data.endswith('GiB'):
        return cast_type(data.split('Gi')[0].strip()) * (1024 * 1024 * 1024)
    if data.endswith('Ti') or data.endswith('TiB'):
        return cast_type(data.split('Ti')[0].strip()) * (1024 * 1024 * 1024 * 1024)
    if data.endswith('Pi') or data.endswith('PiB'):
        return cast_type(data.split('Pi')[0].strip()) * (1024 * 1024 * 1024 * 1024 * 1024)
    if data.endswith('Ei') or data.endswith('EiB'):
        return cast_type(data.split('Ei')[0].strip()) * (1024 * 1024 * 1024 * 1024 * 1024 * 1024)
    return cast_type(data.strip())


def parse_memory_metric_to_bs(data: t.Union[int, float, str]) -> 'ByteSize':
    """Return a :class:`ByteSize` instance from byte or string input."""

    from pydantic.types import ByteSize
    if isinstance(data, (int, float)): 
        return ByteSize(data)
    data = parse_memory_metric(f'{data} MiB')
    return ByteSize(data)


def safe_float(item: str) -> float:
    """Return ``float(item)`` or ``nan`` when conversion fails."""

    try:
        number = float(item)
    except ValueError:
        number = float('nan')
    return number
