import asyncio
import sys
import types
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[2] / 'src'
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

try:
    import aiopath.wrap as wrap  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    wrap = None


def _wrap_sync(func):
    async def runner(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    return runner


required_names = {
    "func_to_async_func": _wrap_sync,
    "func_to_async_method": _wrap_sync,
    "coro_to_async_method": lambda coro: coro,
    "to_async_method": _wrap_sync,
    "method_to_async_method": _wrap_sync,
    "to_thread": asyncio.to_thread,
}

if wrap is None:
    stub = types.ModuleType("aiopath.wrap")
    for name, factory in required_names.items():
        setattr(stub, name, factory)
    sys.modules["aiopath.wrap"] = stub
else:
    for name, factory in required_names.items():
        if not hasattr(wrap, name):
            setattr(wrap, name, factory)
