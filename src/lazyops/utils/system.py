from __future__ import annotations

import os
import time
import socket
import pathlib
import tempfile
import contextlib

from typing import Union, Optional, Dict, Any, List, TYPE_CHECKING
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


@lru_cache()
def get_nvidia_smi_cmd() -> str:
    """
    Returns the nvidia-smi command
    """
    import platform
    from distutils import spawn
    if platform.system() == "Windows":
        # If the platform is Windows and nvidia-smi 
        # could not be found from the environment path, 
        # try to find it from system drive with default installation path
        nvidia_smi = spawn.find_executable('nvidia-smi')
        if nvidia_smi is None:
            nvidia_smi = "%s\\Program Files\\NVIDIA Corporation\\NVSMI\\nvidia-smi.exe" % os.environ['systemdrive']
    else:
        nvidia_smi = "nvidia-smi"
    return nvidia_smi



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

if TYPE_CHECKING:
    from pydantic.types import ByteSize

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



_nvidia_smi_dict_mapping = {
    'index': str,
    'name': str,
    'uuid': str,
    'utilization_gpu': safe_float,
    'utilization_memory': safe_float,
    'memory_total': parse_memory_metric_to_bs,
    'memory_used': parse_memory_metric_to_bs,
    'memory_free': parse_memory_metric_to_bs,
}

def map_nvidia_smi_result_values(data: List[str]) -> Dict[str, Any]:
    """
    Maps the result values to a dictionary
    """
    result: Dict[str, Any] = {
        key: _nvidia_smi_dict_mapping[key](data[n])
        for n, key in enumerate(_nvidia_smi_dict_mapping)
    }
    return result


async def aget_gpu_data() -> Union[List[Dict[str, Any]], Dict[str, Union[str, int, float, 'ByteSize']]]:
    """
    Returns the GPU Data
    """
    import asyncio
    nvidia_smi = get_nvidia_smi_cmd()
    if nvidia_smi is None: return []
    try:
        p = await asyncio.subprocess.create_subprocess_shell(
            f"{nvidia_smi} --query-gpu=index,name,uuid,utilization.gpu,utilization.memory,memory.total,memory.used,memory.free --format=csv,noheader,nounits", 
            stdout = asyncio.subprocess.PIPE, stderr = asyncio.subprocess.PIPE
        )
        stdout, _ = await p.communicate()
    except Exception:
        return []
    output = stdout.decode('UTF-8')
    if 'has failed' in output or 'command not found' in output: return []
    lines = output.split(os.linesep)
    num_devices = len(lines)-1
    gpu_data = []
    for g in range(num_devices):
        line = lines[g]
        values = line.split(', ')
        gpu_data.append(map_nvidia_smi_result_values(values))
    if len(gpu_data) == 1: gpu_data = gpu_data[0]
    return gpu_data

def get_gpu_data() -> Union[List[Dict[str, Any]], Dict[str, Union[str, int, float, 'ByteSize']]]:
    """
    Gets the GPU data
    """
    nvidia_smi = get_nvidia_smi_cmd()
    if nvidia_smi is None: return []
    import subprocess
    try:
        p = subprocess.Popen(
            f"{nvidia_smi} --query-gpu=index,name,uuid,utilization.gpu,utilization.memory,memory.total,memory.used,memory.free --format=csv,noheader,nounits", 
            stdout = subprocess.PIPE, stderr = subprocess.PIPE,
            shell = True,
        )
        stdout, _ = p.communicate()
    except Exception:
        return []
    output = stdout.decode('UTF-8')
    if 'has failed' in output or 'command not found' in output: return []
    lines = output.split(os.linesep)
    num_devices = len(lines)-1
    gpu_data = []
    for g in range(num_devices):
        line = lines[g]
        values = line.split(', ')
        gpu_data.append(map_nvidia_smi_result_values(values))
    if len(gpu_data) == 1: gpu_data = gpu_data[0]
    return gpu_data

    
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
    from lazyops.utils.logs import logger
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft_limit > max_connections: return
    if hard_limit < max_connections and verbose:
        logger.warning(f"The current hard limit ({hard_limit}) is less than max_connections ({max_connections}).")
    new_hard_limit = max(hard_limit, max_connections)
    if verbose: logger.info(f"Setting new ulimits to ({soft_limit}, {hard_limit}) -> ({max_connections}, {new_hard_limit})")
    resource.setrlimit(resource.RLIMIT_NOFILE, (max_connections + 10, new_hard_limit))
    new_soft, new_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if verbose: logger.info(f"New Limits: ({new_soft}, {new_hard})")
