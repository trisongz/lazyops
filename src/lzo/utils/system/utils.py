from __future__ import annotations

import os
from typing import Union, Dict, Any, List, TYPE_CHECKING
from functools import lru_cache

if TYPE_CHECKING:
    from pydantic.types import ByteSize

def parse_memory_metric(data: Union[int, float, str]):
    """
    Parses memory to full memory
    """
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

def parse_memory_metric_to_bs(data: Union[int, float, str]) -> 'ByteSize':
    """
    Parses memory to ByteSize
    """
    from pydantic.types import ByteSize
    if isinstance(data, (int, float)): 
        return ByteSize(data)
    data = parse_memory_metric(f'{data} MiB')
    return ByteSize(data)

def safe_float(item: str) -> float:
    try: number = float(item)
    except ValueError: number = float('nan')
    return number