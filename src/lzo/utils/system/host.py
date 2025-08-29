from __future__ import annotations

import os
import time
import socket
import pathlib
import tempfile
import contextlib

from typing import Union, Optional, Dict, Any, List, TYPE_CHECKING
from functools import lru_cache

if TYPE_CHECKING:
    from torch import device

# Stateful Variables
_system_host_name: Optional[str] = None
_system_host_ip: Optional[str] = None


@lru_cache()
def get_torch_device_name(mps_enabled: bool = False):
    """
    Returns the torch device name
    """
    with contextlib.suppress(ImportError):
        import torch
        if torch.cuda.is_available(): return 'cuda'
        if mps_enabled and torch.torch.backends.mps.is_available(): return 'mps'
    return 'cpu'

@lru_cache()
def get_torch_device(mps_enabled: bool = False) -> 'device':
    """
    Returns the torch device
    """
    with contextlib.suppress(ImportError):
        import torch
        return torch.device(get_torch_device_name(mps_enabled))
    return 'cpu'

@lru_cache()
def get_cpu_count() -> int:
    """Get the available CPU count for this system.
    Takes the minimum value from the following locations:
    - Total system cpus available on the host.
    - CPU Affinity (if set)
    - Cgroups limit (if set)
    """
    import sys
    count = os.cpu_count()
    # Check CPU affinity if available
    with contextlib.suppress(Exception):
        import psutil
        affinity_count = len(psutil.Process().cpu_affinity())
        if affinity_count > 0:
            count = min(count, affinity_count)
    # Check cgroups if available
    if sys.platform == "linux":
        with contextlib.suppress(Exception):
            with open("/sys/fs/cgroup/cpu,cpuacct/cpu.cfs_quota_us") as f:
                quota = int(f.read())
            with open("/sys/fs/cgroup/cpu,cpuacct/cpu.cfs_period_us") as f:
                period = int(f.read())
            cgroups_count = quota // period
            if cgroups_count > 0:
                count = min(count, cgroups_count)

    return count


@lru_cache()
def is_readonly_dir(path: Union[str, pathlib.Path]) -> bool:
    """
    Check if a directory is read-only.
    """
    if isinstance(path, str): path = pathlib.Path(path)
    if not path.is_dir(): path = path.parent
    try:
        path.mkdir(parents = True, exist_ok = True)
        with tempfile.NamedTemporaryFile('w', dir = path.as_posix()) as f:
            f.write('test')
        return False
    except Exception as e:
        return True



@lru_cache()
def get_host_name():
    """
    Wrapper to handle the case where the hostname is not yet available.
    """
    global _system_host_name
    if _system_host_name is None:
        while _system_host_name is None:
            with contextlib.suppress(Exception):
                _system_host_name = socket.gethostname()
            time.sleep(0.2)
    return _system_host_name


@lru_cache()
def get_host_ip():
    """
    Wrapper to handle the case where the hostname is not yet available.
    """
    global _system_host_ip
    if _system_host_ip is None:
        while _system_host_ip is None:
            with contextlib.suppress(Exception):
                _system_host_ip = socket.gethostbyname(get_host_name())
            time.sleep(0.2)
    return _system_host_ip



@lru_cache()
def fetch_resolver_nameserver(
    path: Optional[str] = '/etc/resolv.conf',
) -> Optional[str]:
    """
    Fetches the nameserver from the resolv.conf
    """
    if path is None: return None
    p = pathlib.Path(path)
    if not p.exists(): return None
    lines = p.read_text().splitlines()
    return next(
        (
            line.split(' ')[-1].strip()
            for line in lines
            if line.startswith('nameserver')
        ),
        None,
    )

    
def get_ulimits():
    import resource
    soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    return soft_limit


def set_ulimits(
    max_connections: int = 500,
    verbose: bool = False,
):
    """
    Sets the system ulimits
    to allow for the maximum number of open connections

    - if the current ulimit > max_connections, then it is ignored
    - if it is less, then we set it.
    """
    import resource
    from lzl.logging import logger
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft_limit > max_connections: return
    if hard_limit < max_connections and verbose:
        logger.warning(f"The current hard limit ({hard_limit}) is less than max_connections ({max_connections}).")
    new_hard_limit = max(hard_limit, max_connections)
    if verbose: logger.info(f"Setting new ulimits to ({soft_limit}, {hard_limit}) -> ({max_connections}, {new_hard_limit})")
    resource.setrlimit(resource.RLIMIT_NOFILE, (max_connections + 10, new_hard_limit))
    new_soft, new_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if verbose: logger.info(f"New Limits: ({new_soft}, {new_hard})")




