from __future__ import annotations

"""
Host Resources
"""

import typing as t
from lzl import load
from .utils import parse_memory_metric_to_bs, safe_float

if t.TYPE_CHECKING:
    import psutil
    from pydantic.types import ByteSize
else:
    psutil = load.lazy_load("psutil")


_resource_dict_mapping = {
    'cpu_count': int,
    
    'memory_total': parse_memory_metric_to_bs,
    'memory_used': parse_memory_metric_to_bs,
    'memory_free': parse_memory_metric_to_bs,

    'utilization_cpu': safe_float,
    'utilization_memory': safe_float,
}

ResourceData = t.Dict[str, t.Union[str, int, float, 'ByteSize']]

def get_resource_data() -> ResourceData:
    """
    Returns the resource data of the host system.
    """
    return {
        'cpu_count': psutil.cpu_count(),
        'memory_total': parse_memory_metric_to_bs(psutil.virtual_memory().total),
        'memory_used': parse_memory_metric_to_bs(psutil.virtual_memory().used),
        'memory_free': parse_memory_metric_to_bs(psutil.virtual_memory().free),
        'utilization_cpu': safe_float(psutil.cpu_percent()),
        'utilization_memory': safe_float(psutil.virtual_memory().percent),
    }