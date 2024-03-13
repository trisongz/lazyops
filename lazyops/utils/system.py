import os
import time
import socket
import pathlib
import tempfile
import contextlib

from typing import Union, Optional
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
def get_torch_device_name(mps_enabled: bool = False):
    with contextlib.suppress(ImportError):
        import torch
        if torch.cuda.is_available(): return 'cuda'
        if mps_enabled and torch.torch.backends.mps.is_available(): return 'mps'
    return 'cpu'

@lru_cache()
def get_torch_device(mps_enabled: bool = False):
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


# Local K8s
_kubeconfig_dir: str = None

def get_local_kubeconfig_dir(
    env_var: str = 'KUBECONFIG_DIR',
    default: str = None,
) -> str:
    """
    Get the local kubernetes kubeconfig.
    """
    global _kubeconfig_dir
    if _kubeconfig_dir is None:
        _kubeconfig_dir = os.getenv(env_var, default) or os.path.expanduser('~/.kube')
    return _kubeconfig_dir

@lru_cache()
def get_local_kubeconfig(
    name: Optional[str] = None,
    set_as_envval: bool = False,
) -> str:
    """
    Get the local kubernetes kubeconfig
    - this assumes that it's not the default one.
    """
    if name is None: return get_k8s_kubeconfig()
    p = os.path.join(get_local_kubeconfig_dir(), name)
    for stem in ('', '-cluster', '-admin-config', '-config', '-kubeconfig'):
        for ext in ('', '.yaml', '.yml'):
            if os.path.isfile(p + stem + ext): 
                px = os.path.abspath(p + stem + ext)
                if set_as_envval:
                    os.environ['KUBECONFIG'] = px
                return px
    raise FileNotFoundError(f'Could not find kubeconfig file: {name} @ {p}')


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


