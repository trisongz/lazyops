from __future__ import annotations

"""
System Monitoring Client
"""

import abc
import time
import atexit
import contextlib

from lazyops.libs import lazyload
from pydantic import BaseModel
from pydantic.types import ByteSize
from lazyops.utils import logger, Timer
from typing import Optional, List, Dict, Any, Union, Type, Set, TYPE_CHECKING

if lazyload.TYPE_CHECKING:
    import psutil
else:
    psutil = lazyload.LazyLoad("psutil")


class SysMonitorData(BaseModel):
    """
    The System Monitor Data
    """
    cpu: Dict[str, float]
    memory: Dict[str, float]
    disk: Dict[str, float]
    network: Dict[str, float]
    process: Dict[str, float]
    system: Dict[str, float]

class SysMonitorClient(abc.ABC):
    """
    The System Monitor Client
    """

    def __init__(
        self,
        interval: Optional[float] = None, # If interval is set, background tasks will be created
        **kwargs
    ):
        """
        Initializes the System Monitor Client
        """
        self.interval = interval
        self.timer = Timer()
        self.states: Dict[int, SysMonitorData] = {}
    
    def capture(self) -> SysMonitorData:
        """
        Captures the system monitor data
        """
        return SysMonitorData(
            cpu = self.get_cpu(),
            memory = self.get_memory(),
            disk = self.get_disk(),
            network = self.get_network(),
            process = self.get_process(),
            system = self.get_system(),
        )
    
    def get_cpu(self) -> Dict[str, float]:
        """
        Returns the CPU Usage
        """
        return psutil.cpu_percent(interval = self.interval)
    
    def get_memory(self) -> Dict[str, float]:
        """
        Returns the Memory Usage
        """
        mem = psutil.virtual_memory()
        return {
            'total': mem.total,
            'available': mem.available,
            'percent': mem.percent,
            'used': mem.used,
            'free': mem.free,
            'active': mem.active,
            'inactive': mem.inactive,
        }