from __future__ import annotations

"""
Workflow Context Utilities
"""

import os
import psutil
import pathlib
import linecache
import tracemalloc
import contextlib
from pydantic.types import ByteSize
from typing import Any, Dict, List, Optional, TypeVar, Union, TYPE_CHECKING


_cgroup_path = pathlib.Path('/sys/fs/cgroup')
_cgroup_mem_path = pathlib.Path('/sys/fs/cgroup/memory.current')

def display_top(snapshot: tracemalloc.Snapshot, key_type: str = 'lineno', limit: int = 3) -> str:
    """
    Displays the top lines of a tracemalloc snapshot
    """
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<unknown>"),
    ))
    top_stats = snapshot.statistics(key_type)
    s = f'Top {limit} Lines:\n'

    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        # replace "/path/to/module/file.py" with "module/file.py"
        filename = os.sep.join(frame.filename.split(os.sep)[-2:])
        fstat = ByteSize(stat.size)
        s += f'- [{index}] {fstat.human_readable(True)} {filename}:{frame.lineno} '
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            s += f'\t{line}'
        s += '\n'
    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        s += f'- [{len(other)}] {ByteSize(size).human_readable(True)} Other Lines Total\n'
    total = sum(stat.size for stat in top_stats)
    s += f'Total Size: {ByteSize(total).human_readable(True)}'
    return s

def capture_state(
    as_str: bool = False,
    prefix: Optional[str] = None,
    in_k8s: Optional[bool] = None,
) -> Union[str, Dict[str, Any]]:
    """
    Captures the state of the process
    """
    # Memory
    # {'total': 137438953472, 'available': 65029390336, 'percent': 52.7, 'used': 71518945280, 'free': 2075770880, 'active': 62968168448, 'inactive': 61191651328, 'wired': 8550776832}
    state = {
        'memory': psutil.virtual_memory()._asdict(),
        'cpu': psutil.cpu_percent(),
        # 'cpu_count': psutil.cpu_count(),
    }
    if in_k8s:
        with contextlib.suppress(Exception):
            state['memory']['used'] = int(_cgroup_path.joinpath('memory.current').read_text().strip())
            max_mem = _cgroup_path.joinpath('memory.max').read_text().strip()
            if max_mem.isnumeric(): state['memory']['total'] = int(max_mem)
            state['memory']['percent'] = round((state['memory']['used'] / state['memory']['total']) * 100, 1)

    if as_str:
        mem_used = ByteSize(state['memory']['used'])
        mem_total = ByteSize(state['memory']['total'])
        mem_percent = state['memory']['percent']
        prefix = prefix or ''
        return f'{prefix}CPU: {state["cpu"]}%, RAM: {mem_used.human_readable(True)}/{mem_total.human_readable(True)} ({mem_percent}%)'
    return state

