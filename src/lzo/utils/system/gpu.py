from __future__ import annotations

import os
from typing import Union, Dict, Any, List, TYPE_CHECKING
from functools import lru_cache


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

    