import asyncio

from pydantic.types import ByteSize

from lzl.sysmon import WorkerContext, MLContext


class DummyWorker(WorkerContext):
    pass


class DummyML(MLContext):
    pass


def _sample_resource(mem_used: int = 2 * 1024**3) -> dict:
    return {
        "memory_used": ByteSize(mem_used),
        "utilization_memory": 42,
        "memory_total": ByteSize(8 * 1024**3),
        "utilization_cpu": 65,
        "cpu_count": 8,
    }


def _sample_gpu(mem_used: int = 1 * 1024**3) -> dict:
    return {
        "memory_used": ByteSize(mem_used),
        "utilization_memory": 55,
        "memory_total": ByteSize(6 * 1024**3),
        "name": "FakeGPU",
    }


def test_worker_context_logs_summary(monkeypatch):
    ctx = DummyWorker()
    ctx._extra["model_name"] = "demo-model"
    ctx.get_resource_data = lambda: _sample_resource()
    ctx.get_gpu_data = lambda: _sample_gpu()

    messages = []
    monkeypatch.setattr(ctx.logger, "info", lambda message, **_: messages.append(message))
    monkeypatch.setattr(ctx.logger, "trace", lambda *args, **kwargs: None)

    with ctx.inference_mode(batch_size=4, obj_name="batch", enable_gc=False, enable_summary=True):
        pass

    assert any("Inference Completed" in msg for msg in messages)
    assert any("Total Requests" in msg for msg in messages)
    assert ctx.idx == 1
    assert ctx.num_batches == 4


def test_worker_context_async_inference(monkeypatch):
    ctx = DummyWorker()
    ctx._extra["model_name"] = "demo-model"
    ctx.get_resource_data = lambda: _sample_resource()
    ctx.get_gpu_data = lambda: _sample_gpu()
    ctx.aget_gpu_data = lambda: asyncio.sleep(0, result=_sample_gpu())

    monkeypatch.setattr(ctx.logger, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(ctx.logger, "trace", lambda *args, **kwargs: None)

    async def runner():
        async with ctx.ainference_mode(batch_size=2):
            pass

    asyncio.run(runner())
    assert ctx.idx == 1


def test_ml_context_gpu_summary(monkeypatch):
    ctx = DummyML()
    ctx._extra["model_name"] = "ml-model"
    ctx.get_gpu_data = lambda: _sample_gpu()

    messages = []
    monkeypatch.setattr(ctx.logger, "info", lambda message, **_: messages.append(message))
    monkeypatch.setattr(ctx.logger, "trace", lambda *args, **kwargs: None)

    with ctx.inference_mode(batch_size=3):
        pass

    assert any("Inference Completed" in msg for msg in messages)
    assert ctx.idx == 1


def test_worker_context_resource_string_handles_compare():
    ctx = DummyWorker()
    ctx.get_resource_data = lambda: _sample_resource()
    start = _sample_resource(mem_used=2 * 1024**3)
    end = _sample_resource(mem_used=3 * 1024**3)
    ctx.last_resource_data = start
    output = ctx.build_resource_data_string(end, compare=True)
    assert "vCPU" in output
    assert "RAM" in output
