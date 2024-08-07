from __future__ import annotations

"""
Application Metrics
"""
import gc
import os
import pathlib
import linecache
import tracemalloc
import contextlib
from pydantic.types import ByteSize
from lazyops.libs.logging import logger
from typing import Optional, Dict, Any, List, Union, Type, Set, TYPE_CHECKING



cgroup_path = pathlib.Path('/sys/fs/cgroup')


def capture_state(
    as_str: bool = False,
    prefix: Optional[str] = None,
    in_k8s: Optional[bool] = None,
    colored: Optional[bool] = True,
) -> Union[str, Dict[str, Any]]:    # sourcery skip: extract-method
    """
    Captures the state of the process
    """
    # Memory
    # {'total': 137438953472, 'available': 65029390336, 'percent': 52.7, 'used': 71518945280, 'free': 2075770880, 'active': 62968168448, 'inactive': 61191651328, 'wired': 8550776832}
    import psutil
    state = {
        'memory': psutil.virtual_memory()._asdict(),
        'cpu': psutil.cpu_percent(),
        # 'cpu_count': psutil.cpu_count(),
    }
    if in_k8s:
        with contextlib.suppress(Exception):
            state['memory']['used'] = int(cgroup_path.joinpath('memory.current').read_text().strip())
            max_mem = cgroup_path.joinpath('memory.max').read_text().strip()
            if max_mem.isnumeric(): state['memory']['total'] = int(max_mem)
            state['memory']['percent'] = round((state['memory']['used'] / state['memory']['total']) * 100, 1)

    mem_used = ByteSize(state['memory']['used'])
    mem_total = ByteSize(state['memory']['total'])
    mem_percent = state['memory']['percent']
    prefix = prefix or ''
    color_suffix = '|e|' if colored else ''
    color_c_prefix = '|g|' if colored else ''
    color_r_prefix = '|y|' if colored else ''
    state['string'] = f'{prefix}{color_c_prefix}CPU:{color_suffix} {state["cpu"]}%, {color_r_prefix}RAM:{color_suffix} {mem_used.human_readable(True)}/{mem_total.human_readable(True)} ({mem_percent}%)'
    return state['string'] if as_str else state


def display_top(
    snapshot: tracemalloc.Snapshot, 
    key_type: str = 'lineno', 
    limit: int = 3,
    colored: Optional[bool] = True,
    as_str: bool = False,
) -> Union[Dict[str, Any], str]:  # sourcery skip: extract-duplicate-method
    """
    Displays the top lines of a tracemalloc snapshot
    """
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap_external>"),
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<unknown>"),
    ))
    state = {}
    top_stats = snapshot.statistics(key_type)
    color_prefix = '|g|' if colored else ''
    color_suffix = '|e|' if colored else ''
    s = f'Top {limit} Lines:\n'

    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        # replace "/path/to/module/file.py" with "module/file.py"
        filename = os.sep.join(frame.filename.split(os.sep)[-2:])
        fstat = ByteSize(stat.size)
        
        s += f'- [{index}] {color_prefix}{fstat.human_readable(True)}{color_suffix} {filename}:{frame.lineno} '
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            s += f'\t{line}'
        state[index] = {
            'filename': filename,
            'lineno': frame.lineno,
            'size': fstat,
        }
        s += '\n'
    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        other_size = ByteSize(size)
        state['other'] = {
            'size': other_size,
        }
        s += f'- [{len(other)}] {color_prefix}{other_size.human_readable(True)}{color_suffix} Other Lines Total\n'
    total = sum(stat.size for stat in top_stats)
    total_size = ByteSize(total)
    state['total'] = {
        'size': total_size,
    }
    s += f'Total Size: {color_prefix}{total_size.human_readable(True)}{color_suffix}'
    state['string'] = s
    return s if as_str else state


class AppStateMetrics:
    def __init__(
        self, 
        in_k8s: Optional[bool] = None, 
        colored: Optional[bool] = True,
        run_gc: Optional[bool] = False,
        verbose: Optional[bool] = True,
        **kwargs
    ):
        self.in_k8s = in_k8s
        self.colored = colored
        self.run_gc = run_gc
        self.verbose = verbose
        self.kwargs = kwargs
        self.capturing: bool = False
    
    def start_capture(self):
        """
        Starts the capture
        """
        self.capturing = True
        tracemalloc.start()
    
    def stop_capture(self):
        """
        Stops the capture
        """
        tracemalloc.stop()
        self.capturing = False
        if self.run_gc: gc.collect()
    
    def display(self, kind: str, value: Union[str, Dict[str, Any]]) -> None:
        """
        Displays the value
        """
        if isinstance(value, str):
            logger.info(value, colored = self.colored, prefix = kind)
        elif isinstance(value, dict):
            logger.info(value['string'], colored = self.colored, prefix = kind)

    def __call__(
        self, 
        prefix: Optional[str] = None,
        as_str: Optional[bool] = None,
        colored: Optional[bool] = None,
        verbose: Optional[bool] = None,
        limit: Optional[int] = 3,
        **kwargs,
    ) -> Union[Dict[str, Any], Dict[str, str]]:
        """
        Returns the metrics
        """
        if prefix: prefix = f'[{prefix}] '
        colored = colored if colored is not None else self.colored
        verbose = verbose if verbose is not None else self.verbose
        
        if not self.capturing:
            self.start_capture()
            state = capture_state(as_str = as_str, prefix = prefix, in_k8s = self.in_k8s, colored = colored)
            if verbose: self.display('State', state)
            return {
                'state': state,
            }
        top_stats = display_top(
            snapshot = tracemalloc.take_snapshot(),
            limit = limit,
            colored = colored,
            as_str = as_str,
        )
        state = capture_state(as_str = as_str, prefix = prefix, in_k8s = self.in_k8s, colored = colored)
        if verbose:
            self.display('State', state)
            self.display('Snapshot', top_stats)
        return {
            'state': state,
            'snapshot': top_stats,
        }
        
