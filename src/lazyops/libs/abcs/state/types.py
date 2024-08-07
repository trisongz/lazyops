import os
import signal
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from lazyops.utils.logs import Logger


class GracefulKiller:
    kill_now = False
    signals = {
        signal.SIGINT: 'SIGINT',
        signal.SIGTERM: 'SIGTERM',
        signal.SIGKILL: 'SIGKILL',
        signal.SIGQUIT: 'SIGQUIT',
        signal.SIGSTOP: 'SIGSTOP',
        signal.SIGABRT: 'SIGABRT',
    }

    def __init__(
        self, 
        enabled: Optional[List[signal.Signals]] = [signal.SIGINT, signal.SIGTERM],
        logger: Optional['Logger'] = None
    ):  # sourcery skip: default-mutable-arg
        
        self.enabled = enabled
        if logger is None:
            from lazyops.utils.logs import logger as _logger
            logger = _logger
        self.logger = logger
        for sig in self.enabled:
            signal.signal(sig, self.exit_gracefully)
        self.pid = os.getpid()

    def exit_gracefully(self, signum, frame):
        self.logger.warning(f"[{self.pid}] Received {self.signals[signum]} signal. Exiting gracefully")
        self.kill_now = True