# `lzl.sysmon`

Context managers that wrap blocks of work (training, inference, worker loops)
with light-weight resource sampling. The goal is to standardise how LazyOps
components log CPU/GPU usage without forcing callers to interact directly with
low-level monitoring APIs.

## Components
- **`WorkerContext`** – Tracks CPU and GPU usage for generic worker-style
  processes. Provides synchronous/asynchronous context managers for inference,
  arbitrary tasks, and capture blocks.
- **`MLContext`** – Slimmed-down variant tailored for ML inference where only
  GPU metrics are required.

## Quick Start
```python
from lzl.sysmon import WorkerContext

class InferenceWorker(WorkerContext):
    pass

worker = InferenceWorker()
with worker.inference_mode(batch_size=8, obj_name="batch-1", enable_summary=True):
    run_model()
```

## Testing Notes
- Patch the logger or resource fetchers (`get_resource_data`, `get_gpu_data`)
  when exercising contexts in unit tests to avoid relying on real hardware.
- Byte counts are represented with `pydantic.types.ByteSize`; provide values as
  integers to maintain compatible arithmetic in comparisons.
