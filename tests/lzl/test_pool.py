import asyncio
import concurrent.futures

from lzl.pool import (
    ThreadPool,
    ensure_coro,
    get_concurrency_limit,
    is_coro_func,
    is_in_async_loop,
    set_concurrency_limit,
)


def test_set_and_get_concurrency_limit_restores_previous_value():
    original = get_concurrency_limit()
    try:
        set_concurrency_limit(2)
        assert get_concurrency_limit() == 2
    finally:
        set_concurrency_limit(original)


def test_asyncish_runs_sync_function():
    calls = []

    def sync_fn(value: int) -> int:
        calls.append(value)
        return value * 2

    async def runner():
        result = await ThreadPool.asyncish(sync_fn, 5)
        assert result == 10

    asyncio.run(runner())
    assert calls == [5]


def test_background_returns_task_inside_event_loop():
    async def runner():
        task = ThreadPool.background(lambda: "done")
        assert isinstance(task, asyncio.Task)
        assert await task == "done"

    asyncio.run(runner())


def test_background_returns_future_outside_event_loop():
    future = ThreadPool.background(lambda: "done-sync")
    assert isinstance(future, concurrent.futures.Future)
    assert future.result(timeout=1) == "done-sync"


def test_ensure_coro_wraps_sync_callable():
    async def runner():
        wrapped = ensure_coro(lambda x: x + 1)
        assert await wrapped(4) == 5

    asyncio.run(runner())


def test_is_in_async_loop_detects_running_loop():
    async def runner():
        assert is_in_async_loop() is True

    asyncio.run(runner())


def test_is_coro_func_handles_regular_functions():
    def plain_fn() -> None:
        return None

    assert is_coro_func(plain_fn) is False
    assert is_coro_func(asyncio.sleep) is True
