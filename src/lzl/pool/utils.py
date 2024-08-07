import contextlib
import asyncio

def is_in_async_loop() -> bool:
    """
    Returns True if the function is called in an async loop
    """
    with contextlib.suppress(Exception):
        return asyncio.get_event_loop().is_running()
    return False

