
import atexit
from .types import GlobalContext, GracefulKiller
from .workers import spawn_new_worker, stop_worker, terminate_worker


def register_exit():
    """
    Registers the exit function
    """
    atexit.register(GlobalContext.end_all_processes)


def run_until_complete():
    """
    Runs the event loop until complete
    """
    import time
    from lazyops.utils import logger
    while True:
        try: time.sleep(5.0)
        except KeyboardInterrupt:
            logger.warning("Keyboard Interrupt")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            break
    
    GlobalContext.end_all_processes()


async def arun_until_complete(
    termination_file: str = None,
):
    """
    Runs the event loop until complete
    """
    import os
    import asyncio
    import pathlib
    from lazyops.utils import logger

    if termination_file is None:
        termination_file = os.getenv('WORKER_TERMINATION_FILE')

    watch = GracefulKiller()
    tmp_kill_file = pathlib.Path(termination_file) if termination_file is not None else None
    while not watch.kill_now:
        try: 
            await asyncio.sleep(1.0)
            if tmp_kill_file is not None and tmp_kill_file.exists():
                logger.warning(f"Found termination file: {tmp_kill_file}")
                break
        except KeyboardInterrupt:
            logger.warning("Keyboard Interrupt")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            break
    
    GlobalContext.end_all_processes()
    await GlobalContext.aclose_processes()
