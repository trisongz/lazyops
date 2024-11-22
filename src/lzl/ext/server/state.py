from __future__ import annotations

import os
import abc
import signal
import pathlib
import asyncio
import contextlib
import multiprocessing
from lzl.proxied import ProxyObject
from lzl.logging import logger, Logger
from lzl.types import eproperty
from typing import Optional, List, TypeVar, Callable, Dict, Any, overload, Type, Union, TYPE_CHECKING


class ServerStateObject(abc.ABC):
    """
    The Server State
    """

    _extra: Dict[str, Any] = {}

    @eproperty
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        return logger

    def start_debug_mode(self):
        """
        Enters Debug Mode
        """
        self.logger.warning('Entering Debug Mode. Sleeping Forever')
        import time
        import sys
        while True:
            try:
                time.sleep(900)
            except Exception as e:
                self.logger.error(e)
                break
        sys.exit(0)

    async def arun_until_complete(
        self,
        termination_file: Optional[str] = None,
    ):
        """
        Runs the event loop until complete
        """
        from .term import GracefulTermination
        watch = GracefulTermination()
        tmp_kill_file = pathlib.Path(termination_file) if termination_file is not None else None
        while not watch.kill_now:
            try: 
                await asyncio.sleep(1.0)
                if tmp_kill_file is not None and tmp_kill_file.exists():
                    self.logger.warning(f"Found termination file: {tmp_kill_file}")
                    break
            except KeyboardInterrupt:
                self.logger.warning("Keyboard Interrupt")
                break
            except Exception as e:
                self.logger.error(f"Error: {e}")
                break
        
        self.end_all_processes()
        await self.aclose_processes()



ServerState: ServerStateObject = ProxyObject(ServerStateObject)