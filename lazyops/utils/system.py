import os
import time
import socket
import pathlib
import tempfile
import contextlib

from typing import Union
from functools import lru_cache

__all__ = [
    'get_torch_device_name',
    'get_torch_device',
    'get_cpu_count',
    'is_readonly_dir',
    'get_host_name',
    'get_host_ip',
    'is_in_kubernetes',
    'get_k8s_namespace',
    'get_k8s_kubeconfig',
]

# Lazily get these libraries

@lru_cache()
def get_torch_device_name():
    with contextlib.suppress(ImportError):
        import torch
        if torch.cuda.is_available(): return 'cuda'
    return 'cpu'

@lru_cache()
def get_torch_device():
    with contextlib.suppress(ImportError):
        import torch
        return torch.device(get_torch_device_name())
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
    if isinstance(path, str):
        path = pathlib.Path(path)

    if not path.is_dir(): path = path.parent
    try:
        path.mkdir(parents = True, exist_ok = True)
        with tempfile.NamedTemporaryFile('w', dir = path.as_posix()) as f:
            f.write('test')
        return False
    except Exception as e:
        return True


_host_name = None
_host_ip = None

@lru_cache()
def get_host_name():
    """
    Wrapper to handle the case where the hostname is not yet available.
    """
    global _host_name
    if _host_name is None:
        while _host_name is None:
            with contextlib.suppress(Exception):
                _host_name = socket.gethostname()
            time.sleep(0.2)
    return _host_name


@lru_cache()
def get_host_ip():
    """
    Wrapper to handle the case where the hostname is not yet available.
    """
    global _host_ip
    if _host_ip is None:
        while _host_ip is None:
            with contextlib.suppress(Exception):
                _host_ip = socket.gethostbyname(get_host_name())
            time.sleep(0.2)
    return _host_ip


_is_in_kubernetes: bool = None
_k8s_namespace: str = None
_k8s_kubeconfig: str = None

@lru_cache()
def is_in_kubernetes() -> bool:
    """
    Check if we are running in a kubernetes cluster.
    """
    global _is_in_kubernetes
    if _is_in_kubernetes is None:
        _is_in_kubernetes = os.path.isdir('/var/run/secrets/kubernetes.io/')
    return _is_in_kubernetes


@lru_cache()
def get_k8s_namespace(
    env_var: str = 'NAMESPACE',
    default: str = 'default'
) -> str:
    """
    Get the kubernetes namespace.
    """
    global _k8s_namespace
    if _k8s_namespace is None:
        if is_in_kubernetes():
            with open('/var/run/secrets/kubernetes.io/serviceaccount/namespace') as f:
                _k8s_namespace = f.read().strip()
        else:
            _k8s_namespace = os.getenv(env_var, default)
    return _k8s_namespace

@lru_cache()
def get_k8s_kubeconfig(
    env_var: str = 'KUBECONFIG',
    default: str = None,
) -> str:
    """
    Get the kubernetes kubeconfig.
    """
    global _k8s_kubeconfig
    if _k8s_kubeconfig is None:
        if is_in_kubernetes():
            _k8s_kubeconfig = '/var/run/secrets/kubernetes.io/serviceaccount/token'
        else:
            _k8s_kubeconfig = os.getenv(env_var, default)
            if _k8s_kubeconfig is None:
                _k8s_kubeconfig = os.path.expanduser('~/.kube/config')
    return _k8s_kubeconfig

