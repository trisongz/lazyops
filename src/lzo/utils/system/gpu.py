from __future__ import annotations

import os
from typing import Union, Dict, Any, List, TYPE_CHECKING
from functools import lru_cache
from .utils import parse_memory_metric_to_bs, safe_float

if TYPE_CHECKING:
    from pydantic.types import ByteSize

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

GPUData = Union[List[Dict[str, Any]], Dict[str, Union[str, int, float, 'ByteSize']]]

def map_nvidia_smi_result_values(data: List[str]) -> Dict[str, Any]:
    """
    Maps the result values to a dictionary
    """
    result: Dict[str, Any] = {
        key: _nvidia_smi_dict_mapping[key](data[n])
        for n, key in enumerate(_nvidia_smi_dict_mapping)
    }
    return result


async def aget_gpu_data() -> GPUData:
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

def get_gpu_data() -> GPUData:
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

    