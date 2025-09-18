from __future__ import annotations

"""Machine-learning specific metrics context helpers."""

import abc
import contextlib
import gc
import typing as t

from lzl.types import eproperty

if t.TYPE_CHECKING:
    from pydantic.types import ByteSize

GPUData = t.Union[t.List[t.Dict[str, t.Any]], t.Dict[str, t.Union[str, int, float, "ByteSize"]]]


class MLContext(abc.ABC):
    """Capture GPU statistics during ML inference workloads."""

    def __init__(self, **kwargs: t.Any) -> None:
        """Initialise timer/logging helpers used for metric collection."""

        from lzl.logging import logger
        from lzo.utils import Timer
        from lzo.utils.system import aget_gpu_data, get_gpu_data
        from pydantic.types import ByteSize

        self._extra: dict[str, t.Any] = {}
        self._kwargs = kwargs

        self.timer = Timer
        self.logger = logger
        self._bs = ByteSize

        self.get_gpu_data = get_gpu_data
        self.aget_gpu_data = aget_gpu_data

        self.t = self.timer()
        self.idx: int = 0
        self.num_batches: int = 0
        self.last_batch_size: int = 0
        self.total_duration: float = 0.0
        self.last_duration: float = 0.0
        self.last_gpu_data: t.Optional[t.Dict[str, t.Any]] = None

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
        """Return ``True`` when the runtime has a CUDA device."""

        return self.torch_device_name.startswith("cuda")

    @eproperty
    def model_name(self) -> t.Optional[str]:
        """Optional model identifier used in log prefixes."""

        return self._extra.get("model_name")

    def build_gpu_data_string(
        self,
        current_usage: GPUData,
        compare: bool | None = None,
        previous_usage: GPUData | None = None,
        colored: bool = False,
    ) -> t.Optional[str]:
        """Format GPU usage details with optional comparison."""

        curr_mem_used = current_usage["memory_used"]
        curr_mem_percent = current_usage["utilization_memory"]
        curr_mem_total = current_usage["memory_total"]
        gpu_name = current_usage["name"]

        previous_usage = previous_usage or self.last_gpu_data
        self.last_gpu_data = current_usage
        if compare and previous_usage:
            comparison: GPUData = {
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
        previous_usage: GPUData | None = None,
        colored: bool = False,
    ) -> t.Optional[str]:
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
        previous_usage: GPUData | None = None,
        colored: bool = False,
    ) -> t.Optional[str]:
        current_usage = await self.aget_gpu_data()
        if not current_usage:
            return None
        return self.build_gpu_data_string(
            current_usage,
            compare=compare,
            previous_usage=previous_usage,
            colored=colored,
        )

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
        """Track a block of inference work, logging GPU usage before/after."""

        ts = self.timer(format_ms=True, format_short=1)
        start_text = "Starting Inference"
        if obj_name:
            start_text += f" for |g|{obj_name}|e|"
        start_text += f" ({batch_size})"
        self.logger.info(start_text, prefix=self.model_name, colored=True, hook=hook)
        start_gpu_data = self.get_gpu_data()
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
        start_gpu_data = await self.aget_gpu_data()
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
                await self.aget_gpu_memory(compare=True, previous_usage=start_gpu_data, colored=True),
                colored=True,
                prefix=self.model_name,
                hook=hook,
            )
