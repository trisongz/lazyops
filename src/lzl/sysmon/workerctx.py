from __future__ import annotations

"""Context helpers for tracking system metrics during worker execution."""

import abc
import contextlib
import gc
import typing as t

from lzl.types import eproperty

if t.TYPE_CHECKING:
    from lzo.utils.system.gpu import GPUData
    from lzo.utils.system.resources import ResourceData


class WorkerContext(abc.ABC):
    """Capture CPU/GPU statistics around long-running worker operations."""

    def __init__(self, **kwargs: t.Any) -> None:
        """Initialise timer/logging helpers used during metric collection."""

        from lzl.logging import logger
        from lzo.utils import Timer
        from lzo.utils.system import aget_gpu_data, get_gpu_data, get_resource_data
        from pydantic.types import ByteSize

        self._extra: dict[str, t.Any] = {}
        self._kwargs = kwargs

        self.timer = Timer
        self.logger = logger
        self._bs = ByteSize

        self.get_gpu_data = get_gpu_data
        self.aget_gpu_data = aget_gpu_data
        self.get_resource_data = get_resource_data

        self.t = self.timer()
        self.idx: int = 0
        self.num_batches: int = 0
        self.last_batch_size: int = 0
        self.total_duration: float = 0.0
        self.last_duration: float = 0.0

        self.last_resource_data: t.Optional["ResourceData"] = None
        self.last_gpu_data: t.Optional["GPUData"] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @eproperty
    def torch_device_name(self) -> str:
        """Return the active PyTorch device name."""

        from lzo.utils.system import get_torch_device_name

        return get_torch_device_name()

    @eproperty
    def torch_device(self):
        """Return the active PyTorch device instance."""

        from lzo.utils.system import get_torch_device

        return get_torch_device()

    @eproperty
    def has_gpu(self) -> bool:
        """Return ``True`` when the runtime is backed by CUDA."""

        return self.torch_device_name.startswith("cuda")

    @eproperty
    def model_name(self) -> t.Optional[str]:
        """Optional model identifier surfaced in log prefixes."""

        return self._extra.get("model_name")

    @eproperty
    def worker_name(self) -> t.Optional[str]:
        """Optional worker identifier used in log prefixes."""

        return self._extra.get("worker_name")

    # ------------------------------------------------------------------
    # GPU helpers
    # ------------------------------------------------------------------

    def build_gpu_data_string(
        self,
        current_usage: "GPUData",
        compare: bool | None = None,
        previous_usage: "GPUData" | None = None,
        colored: bool = False,
    ) -> t.Optional[str]:
        """Format GPU usage statistics with optional comparison."""

        curr_mem_used = current_usage["memory_used"]
        curr_mem_percent = current_usage["utilization_memory"]
        curr_mem_total = current_usage["memory_total"]
        gpu_name = current_usage["name"]

        previous_usage = previous_usage or self.last_gpu_data
        self.last_gpu_data = current_usage

        if compare and previous_usage:
            comparison = {
                "memory_used": self._bs(curr_mem_used - previous_usage["memory_used"]),
                "utilization_memory": curr_mem_percent - previous_usage["utilization_memory"],
            }
            if not colored:
                return (
                    f"{gpu_name}: {previous_usage['memory_used'].human_readable()} -> "
                    f"{curr_mem_used.human_readable()} / {curr_mem_total.human_readable()} + "
                    f"{comparison['memory_used'].human_readable()} "
                    f"({comparison['utilization_memory']} -> {curr_mem_percent}%)"
                )
            return (
                f"{gpu_name}: {previous_usage['memory_used'].human_readable()} -> |y|{curr_mem_used.human_readable()}|e| / "
                f"|g|{curr_mem_total.human_readable()}|e| + |r|{comparison['memory_used'].human_readable()}|e| "
                f"({comparison['utilization_memory']} -> {curr_mem_percent}%)"
            )

        if not colored:
            return (
                f"{gpu_name}: {curr_mem_used.human_readable()} / {curr_mem_total.human_readable()} "
                f"({curr_mem_percent}%)"
            )
        return (
            f"{gpu_name}: |y|{curr_mem_used.human_readable()}|e| / |g|{curr_mem_total.human_readable()}|e| "
            f"({curr_mem_percent}%)"
        )

    def get_gpu_memory(
        self,
        compare: bool | None = None,
        previous_usage: "GPUData" | None = None,
        colored: bool = False,
    ) -> t.Optional[str]:
        """Return formatted GPU usage, optionally comparing against a prior sample."""

        current_usage = self.get_gpu_data()
        if not current_usage:
            return None
        return self.build_gpu_data_string(
            current_usage,
            compare=compare,
            previous_usage=previous_usage,
            colored=colored,
        )

    async def aget_gpu_memory(
        self,
        compare: bool | None = None,
        previous_usage: "GPUData" | None = None,
        colored: bool = False,
    ) -> t.Optional[str]:
        """Asynchronous variant of :meth:`get_gpu_memory`."""

        current_usage = await self.aget_gpu_data()
        if not current_usage:
            return None
        return self.build_gpu_data_string(
            current_usage,
            compare=compare,
            previous_usage=previous_usage,
            colored=colored,
        )

    # ------------------------------------------------------------------
    # Resource helpers
    # ------------------------------------------------------------------

    def build_resource_data_string(
        self,
        current_usage: "ResourceData",
        compare: bool | None = None,
        previous_usage: "ResourceData" | None = None,
        colored: bool = False,
    ) -> t.Optional[str]:
        """Format CPU/RAM usage into a human-readable string."""

        curr_mem_used = current_usage["memory_used"]
        curr_mem_percent = current_usage["utilization_memory"]
        curr_mem_total = current_usage["memory_total"]
        curr_cpu_percent = current_usage["utilization_cpu"]
        num_cpu = current_usage["cpu_count"]

        previous_usage = previous_usage or self.last_resource_data
        self.last_resource_data = current_usage

        if compare and previous_usage:
            comparison = {
                "memory_used": self._bs(curr_mem_used - previous_usage["memory_used"]),
            }
            base = (
                f"{num_cpu} vCPU: {curr_cpu_percent}% | RAM: {previous_usage['memory_used'].human_readable()} -> "
                f"{curr_mem_used.human_readable()} / {curr_mem_total.human_readable()} + "
                f"{comparison['memory_used'].human_readable()} ({curr_mem_percent}%)"
            )
            if not colored:
                return base
            return (
                f"{num_cpu} vCPU: |g|{curr_cpu_percent}%|e| | RAM: {previous_usage['memory_used'].human_readable()} -> "
                f"|y|{curr_mem_used.human_readable()}|e| / |g|{curr_mem_total.human_readable()}|e| + "
                f"|r|{comparison['memory_used'].human_readable()}|e| ({curr_mem_percent}%)"
            )

        if not colored:
            return (
                f"{num_cpu} vCPU: {curr_cpu_percent}% | RAM: {curr_mem_used.human_readable()} / "
                f"{curr_mem_total.human_readable()} ({curr_mem_percent}%)"
            )
        return (
            f"{num_cpu} vCPU: |g|{curr_cpu_percent}%|e| RAM: |y|{curr_mem_used.human_readable()}|e| / "
            f"|g|{curr_mem_total.human_readable()}|e| ({curr_mem_percent}%)"
        )

    def get_resource_info(
        self,
        compare: bool | None = None,
        previous_usage: "ResourceData" | None = None,
        colored: bool = False,
    ) -> t.Optional[str]:
        """Return formatted CPU/memory usage snapshot."""

        current_usage = self.get_resource_data()
        if not current_usage:
            return None
        return self.build_resource_data_string(
            current_usage,
            compare=compare,
            previous_usage=previous_usage,
            colored=colored,
        )
    # ------------------------------------------------------------------
    # Context managers
    # ------------------------------------------------------------------

    @contextlib.contextmanager
    def inference_mode(
        self,
        batch_size: int | None = 1,
        obj_name: str | None = None,
        enable_gc: bool | None = None,
        enable_summary: bool | None = None,
        hook: t.Optional[t.Callable[[dict[str, t.Any]], None]] = None,
        **kwargs: t.Any,
    ):
        """Wrap a block of inference work with resource logging."""

        ts = self.timer(format_ms=True, format_short=1)
        start_text = "Starting Inference"
        if obj_name:
            start_text += f" for |g|{obj_name}|e|"
        start_text += f" ({batch_size})"
        self.logger.info(start_text, prefix=self.model_name, colored=True, hook=hook)
        start_resource_data = self.get_resource_data()
        start_gpu_data = self.get_gpu_data() if self.has_gpu else None
        try:
            yield
        except Exception as exc:  # pragma: no cover - logging path
            self.logger.trace(f"[{self.model_name}] Error in Inference Mode: ", exc, hook=hook)
            raise
        finally:
            total_s = ts.total
            self.total_duration += total_s
            self.last_duration = total_s
            self.num_batches += batch_size or 0
            self.idx += 1

            end_text = "Inference Completed"
            if obj_name:
                end_text += f" for |g|{obj_name}|e|"
            end_text += f" ({batch_size}) in {ts.total_s}"
            if enable_gc:
                gc.collect()

            self.logger.info(end_text, colored=True, prefix=self.model_name, hook=hook)
            if enable_summary:
                self.logger.info(
                    f"Total Requests: |g|{self.idx}|e|. Total Batches Handled: |g|{self.num_batches}|e|. "
                    f"Handled Last Batch Size of |g|{self.last_batch_size}|e|",
                    colored=True,
                    prefix=self.model_name,
                    hook=hook,
                )
                self.logger.info(
                    f"Total Inference Duration: |g|{self.timer.pformat_duration(self.total_duration)}|e|. "
                    f"Total Time Alive: |g|{self.t.total_s}|e|",
                    colored=True,
                    prefix=self.model_name,
                    hook=hook,
                )
            self.logger.info(
                self.get_resource_info(compare=True, previous_usage=start_resource_data, colored=True),
                colored=True,
                prefix=self.model_name,
                hook=hook,
            )
            if self.has_gpu and start_gpu_data is not None:
                self.logger.info(
                    self.get_gpu_memory(compare=True, previous_usage=start_gpu_data, colored=True),
                    colored=True,
                    prefix=self.model_name,
                    hook=hook,
                )

    @contextlib.asynccontextmanager
    async def ainference_mode(
        self,
        batch_size: int | None = 1,
        obj_name: str | None = None,
        enable_gc: bool | None = None,
        enable_summary: bool | None = None,
        hook: t.Optional[t.Callable[[dict[str, t.Any]], None]] = None,
        **kwargs: t.Any,
    ):
        """Async variant of :meth:`inference_mode`."""

        ts = self.timer(format_ms=True, format_short=1)
        start_text = "Starting Inference"
        if obj_name:
            start_text += f" for |g|{obj_name}|e|"
        start_text += f" ({batch_size})"
        self.logger.info(start_text, prefix=self.model_name, colored=True, hook=hook)
        start_resource_data = self.get_resource_data()
        start_gpu_data = await self.aget_gpu_data() if self.has_gpu else None
        try:
            yield
        except Exception as exc:  # pragma: no cover - logging path
            self.logger.trace(f"[{self.model_name}] Error in Inference Mode: ", exc, hook=hook)
            raise
        finally:
            total_s = ts.total
            self.total_duration += total_s
            self.last_duration = total_s
            self.num_batches += batch_size or 0
            self.idx += 1

            end_text = "Inference Completed"
            if obj_name:
                end_text += f" for |g|{obj_name}|e|"
            end_text += f" ({batch_size}) in {ts.total_s}"
            if enable_gc:
                gc.collect()

            self.logger.info(end_text, colored=True, prefix=self.model_name, hook=hook)
            if enable_summary:
                self.logger.info(
                    f"Total Requests: |g|{self.idx}|e|. Total Batches Handled: |g|{self.num_batches}|e|. "
                    f"Handled Last Batch Size of |g|{self.last_batch_size}|e|",
                    colored=True,
                    prefix=self.model_name,
                    hook=hook,
                )
                self.logger.info(
                    f"Total Inference Duration: |g|{self.timer.pformat_duration(self.total_duration)}|e|. "
                    f"Total Time Alive: |g|{self.t.total_s}|e|",
                    colored=True,
                    prefix=self.model_name,
                    hook=hook,
                )
            self.logger.info(
                self.get_resource_info(compare=True, previous_usage=start_resource_data, colored=True),
                colored=True,
                prefix=self.model_name,
                hook=hook,
            )
            if self.has_gpu and start_gpu_data is not None:
                self.logger.info(
                    await self.aget_gpu_memory(compare=True, previous_usage=start_gpu_data, colored=True),
                    colored=True,
                    prefix=self.model_name,
                    hook=hook,
                )

    @contextlib.contextmanager
    def capture(
        self,
        message: str | None = None,
        prefix: str | None = None,
        hook: t.Optional[t.Callable[[dict[str, t.Any]], None]] = None,
        **kwargs: t.Any,
    ):
        """Capture resources across an arbitrary block of work."""

        ts = self.timer(format_ms=True, format_short=1)
        base_name = self.model_name or self.worker_name
        prefix = f"{prefix} {base_name}" if prefix else base_name
        start_resource_data = self.get_resource_data()
        start_gpu_data = self.get_gpu_data() if self.has_gpu else None
        try:
            yield
        except Exception as exc:  # pragma: no cover - logging path
            self.logger.trace(f"[{prefix}] Error in Capture: ", exc, hook=hook)
            raise
        finally:
            message = (message or "Capture Complete") + f" in {ts.total_s}"
            self.logger.info(message, colored=True, prefix=prefix, hook=hook)
            self.logger.info(
                self.get_resource_info(compare=True, previous_usage=start_resource_data, colored=True),
                colored=True,
                prefix=prefix,
                hook=hook,
            )
            if self.has_gpu and start_gpu_data is not None:
                self.logger.info(
                    self.get_gpu_memory(compare=True, previous_usage=start_gpu_data, colored=True),
                    colored=True,
                    prefix=prefix,
                    hook=hook,
                )

    @contextlib.contextmanager
    def start_task(
        self,
        batch_size: int | None = 1,
        obj_name: str | None = None,
        task_name: str | None = None,
        enable_gc: bool | None = None,
        enable_summary: bool | None = None,
        hook: t.Optional[t.Callable[[dict[str, t.Any]], None]] = None,
        **kwargs: t.Any,
    ):
        """Track a generic worker task, logging CPU/GPU usage."""

        ts = self.timer(format_ms=True, format_short=1)
        base_name = self.model_name or self.worker_name
        start_text = "Starting Task"
        if task_name:
            start_text += f": |g|{task_name}|e|"
        if obj_name:
            start_text += f" for |g|{obj_name}|e|"
        start_text += f" ({batch_size})"
        self.logger.info(start_text, prefix=base_name, colored=True, hook=hook)
        start_gpu_data = self.get_gpu_data() if self.has_gpu else None
        try:
            yield
        except Exception as exc:  # pragma: no cover - logging path
            self.logger.trace(f"[{base_name}] Error in Task: ", exc, hook=hook)
            raise
        finally:
            total_s = ts.total
            self.total_duration += total_s
            self.last_duration = total_s
            self.num_batches += batch_size or 0
            self.idx += 1

            end_text = "Task Completed"
            if task_name:
                end_text += f": |g|{task_name}|e|"
            if obj_name:
                end_text += f" for |g|{obj_name}|e|"
            end_text += f" ({batch_size}) in {ts.total_s}"
            if enable_gc:
                gc.collect()

            self.logger.info(end_text, colored=True, prefix=base_name, hook=hook)
            if enable_summary:
                self.logger.info(
                    f"Total Tasks: |g|{self.idx}|e|. Total Batches Handled: |g|{self.num_batches}|e|. "
                    f"Handled Last Batch Size of |g|{self.last_batch_size}|e|",
                    colored=True,
                    prefix=base_name,
                    hook=hook,
                )
                self.logger.info(
                    f"Total Task Duration: |g|{self.timer.pformat_duration(self.total_duration)}|e|. "
                    f"Total Time Alive: |g|{self.t.total_s}|e|",
                    colored=True,
                    prefix=base_name,
                    hook=hook,
                )
            self.logger.info(
                self.get_resource_info(compare=False, colored=True),
                colored=True,
                prefix=base_name,
                hook=hook,
            )
            if self.has_gpu and start_gpu_data is not None:
                self.logger.info(
                    self.get_gpu_memory(compare=True, previous_usage=start_gpu_data, colored=True),
                    colored=True,
                    prefix=base_name,
                    hook=hook,
                )

    def __enter__(self) -> "WorkerContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None
