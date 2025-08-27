from __future__ import annotations

import gc
import abc
import contextlib
import typing as t
from lzl.types import eproperty

class MLContext(abc.ABC):
    """
    Base Machine Learning Context Handler
    """

    def __init__(self, **kwargs):
        """
        Initialize the MLContext with the given keyword arguments.
        """
        from lzo.utils import Timer
        from lzl.logging import logger
        from lzo.utils.system import get_gpu_data, aget_gpu_data

        self._extra: t.Dict[str, t.Any] = {}
        self._kwargs = kwargs

        self.timer = Timer
        self.logger = logger

        self.get_gpu_data = get_gpu_data
        self.aget_gpu_data = aget_gpu_data

        self.t = self.timer()
        self.idx: int = 0
        self.num_batches: int = 0
        self.last_batch_size: int = 0
        self.total_duration: float = 0.0
        self.last_duration: float = 0.0
        self.last_gpu_data: t.Dict[str, t.Any] = None

    @eproperty
    def torch_device_name(self) -> str:
        """
        Returns the name of the current PyTorch device.
        """
        from lzo.utils.system import get_torch_device_name
        return get_torch_device_name()
    
    @eproperty
    def torch_device(self):
        """
        Returns the current PyTorch device.
        """
        from lzo.utils.system import get_torch_device
        return get_torch_device()
    
    @eproperty
    def has_gpu(self) -> bool:
        """
        Returns whether the current device has a GPU.
        """
        return self.torch_device_name.startswith("cuda")

    @eproperty
    def model_name(self) -> t.Optional[str]:
        """
        Returns the name of the current model.
        """
        return self._extra.get('model_name')

    def get_gpu_memory(self, compare: t.Optional[bool] = None, previous_usage: t.Optional[t.Dict[str, t.Any]] = None, colored: bool = False) -> t.Optional[str]:
        """
        Returns the GPU memory usage information.

        Args:
            compare (bool, optional): Whether to compare with previous usage.
            short (bool, optional): Whether to return a short summary.
            colored (bool, optional): Whether to return colored output.
        """
        current_usage = self.get_gpu_data()
        if not current_usage: return None

        curr_mem_used = current_usage['memory_used']
        curr_mem_percent = current_usage['utilization_memory']
        curr_mem_total = current_usage['memory_total']
        gpu_name = current_usage['name']
        
        previous_usage = previous_usage or self.last_gpu_data
        self.last_gpu_data = current_usage

        if compare:
            if previous_usage:
                # Compare current usage with previous usage
                comparison = {k: current_usage[k] - previous_usage.get(k, 0) for k in current_usage}
                if curr_mem_used > previous_usage.get('memory_used', 0):
                    comparison['memory_used'] = curr_mem_used - previous_usage['memory_used']
                if curr_mem_percent > previous_usage.get('utilization_memory', 0):
                    comparison['utilization_memory'] = curr_mem_percent - previous_usage['utilization_memory']
                if not colored: return f"{gpu_name}: {previous_usage['memory_used'].human_readable()} -> {curr_mem_used.human_readable()} / {curr_mem_total.human_readable()} + {comparison['memory_used'].human_readable()} ({comparison['utilization_memory']} -> {curr_mem_percent}%)"
                return f"{gpu_name}: |y|{previous_usage['memory_used'].human_readable()}|e| -> |g|{curr_mem_used.human_readable()}|e| / {curr_mem_total.human_readable()} + |b|{comparison['memory_used'].human_readable()}|e|  ({comparison['utilization_memory']} -> {curr_mem_percent}%)"

        if not colored: return f"{gpu_name}: {curr_mem_used.human_readable()} / {curr_mem_total.human_readable()} ({curr_mem_percent}%)"
        return f"{gpu_name}: |g|{curr_mem_used.human_readable()}|e| / |y|{curr_mem_total.human_readable()}|e| ({curr_mem_percent}%)"


    async def aget_gpu_memory(self, compare: t.Optional[bool] = None, previous_usage: t.Optional[t.Dict[str, t.Any]] = None, colored: bool = False) -> t.Optional[str]:
        """
        Returns the GPU memory usage information.

        Args:
            compare (bool, optional): Whether to compare with previous usage.
            short (bool, optional): Whether to return a short summary.
            colored (bool, optional): Whether to return colored output.
        """
        current_usage = await self.aget_gpu_data()
        if not current_usage: return None
        curr_mem_used = current_usage['memory_used']
        curr_mem_percent = current_usage['utilization_memory']
        curr_mem_total = current_usage['memory_total']
        gpu_name = current_usage['name']
        
        previous_usage = previous_usage or self.last_gpu_data
        self.last_gpu_data = current_usage
        if compare:
            if previous_usage:
                # Compare current usage with previous usage
                comparison = {k: current_usage[k] - previous_usage.get(k, 0) for k in current_usage if isinstance(current_usage[k], (int, float))}
                if curr_mem_used > previous_usage.get('memory_used', 0):
                    comparison['memory_used'] = curr_mem_used - previous_usage['memory_used']
                if curr_mem_percent > previous_usage.get('utilization_memory', 0):
                    comparison['utilization_memory'] = curr_mem_percent - previous_usage['utilization_memory']
                if not colored: return f"{gpu_name}: {previous_usage['memory_used'].human_readable()} -> {curr_mem_used.human_readable()} / {curr_mem_total.human_readable()} + {comparison['memory_used'].human_readable()} ({comparison['utilization_memory']} -> {curr_mem_percent}%)"
                return f"{gpu_name}: |y|{previous_usage['memory_used'].human_readable()}|e| -> |g|{curr_mem_used.human_readable()}|e| / {curr_mem_total.human_readable()} + |b|{comparison['memory_used'].human_readable()}|e|  ({comparison['utilization_memory']} -> {curr_mem_percent}%)"

        if not colored: return f"{gpu_name}: {curr_mem_used.human_readable()} / {curr_mem_total.human_readable()} ({curr_mem_percent}%)"
        return f"{gpu_name}: |g|{curr_mem_used.human_readable()}|e| / |y|{curr_mem_total.human_readable()}|e| ({curr_mem_percent}%)"


    @contextlib.contextmanager
    def inference_mode(
        self, 
        batch_size: t.Optional[int] = 1,
        obj_name: t.Optional[str] = None,
        enable_gc: t.Optional[bool] = None,
        enable_summary: t.Optional[bool] = None,
        **kwargs,
    ):
        """
        Context manager for inference mode.

        Args:
            batch_size (int, optional): The batch size for inference.
            obj_name (str, optional): The name of the object being processed.
            enable_gc (bool, optional): Whether to enable garbage collection.
        """
        ts = self.timer(format_ms = True, format_short = 1)
        start_text = "Starting Inference"
        if obj_name: start_text += f" for |g|{obj_name}|e|"
        start_text += f" ({batch_size})"
        self.logger.info(start_text, prefix = self.model_name, colored = True)
        start_gpu_data = self.get_gpu_data()
        try:
            yield
        except Exception as e:
            self.logger.trace(f'[{self.model_name}] Error in Inference Mode: ', e)
            raise e
        finally:
            total_s = ts.total
            self.total_duration += total_s
            self.last_duration = total_s
            self.num_batches += batch_size
            self.idx += 1

            end_text = "Inference Completed"
            if obj_name: end_text += f" for |g|{obj_name}|e|"
            end_text += f" ({batch_size}) in {ts.total_s}"
            if enable_gc: gc.collect()
            
            self.logger.info(end_text, colored = True, prefix = self.model_name)
            if enable_summary:
                self.logger.info(f"Total Requests: |g|{self.idx}|e|. Total Batches Handled: |g|{self.num_batches}|e|. Handled Last Batch Size of |g|{self.last_batch_size}|e|", colored = True, prefix = self.model_name)
                self.logger.info(f"Total Inference Duration: |g|{self.timer.pformat_duration(self.total_duration)}|e|. Total Time Alive: |g|{self.t.total_s}|e|", colored = True, prefix = self.model_name)
            self.logger.info(self.get_gpu_memory(compare = True, previous_usage = start_gpu_data, colored = True), colored = True, prefix = self.model_name)



    @contextlib.asynccontextmanager
    async def ainference_mode(
        self, 
        batch_size: t.Optional[int] = 1,
        obj_name: t.Optional[str] = None,
        enable_gc: t.Optional[bool] = None,
        enable_summary: t.Optional[bool] = None,
        **kwargs,
    ):
        """
        Context manager for inference mode.

        Args:
            batch_size (int, optional): The batch size for inference.
            obj_name (str, optional): The name of the object being processed.
            enable_gc (bool, optional): Whether to enable garbage collection.
        """
        ts = self.timer(format_ms = True, format_short = 1)
        start_text = "Starting Inference"
        if obj_name: start_text += f" for |g|{obj_name}|e|"
        start_text += f" ({batch_size})"
        self.logger.info(start_text, prefix = self.model_name, colored = True)
        start_gpu_data = await self.aget_gpu_data()
        try:
            yield
        except Exception as e:
            self.logger.trace(f'[{self.model_name}] Error in Inference Mode: ', e)
            raise e
        finally:
            total_s = ts.total
            self.total_duration += total_s
            self.last_duration = total_s
            self.num_batches += batch_size
            self.idx += 1

            end_text = "Inference Completed"
            if obj_name: end_text += f" for |g|{obj_name}|e|"
            end_text += f" ({batch_size}) in {ts.total_s}"
            if enable_gc: gc.collect()
            
            self.logger.info(end_text, colored = True, prefix = self.model_name)
            if enable_summary:
                self.logger.info(f"Total Requests: |g|{self.idx}|e|. Total Batches Handled: |g|{self.num_batches}|e|. Handled Last Batch Size of |g|{self.last_batch_size}|e|", colored = True, prefix = self.model_name)
                self.logger.info(f"Total Inference Duration: |g|{self.timer.pformat_duration(self.total_duration)}|e|. Total Time Alive: |g|{self.t.total_s}|e|", colored = True, prefix = self.model_name)
            self.logger.info(await self.aget_gpu_memory(compare = True, previous_usage = start_gpu_data, colored = True), colored = True, prefix = self.model_name)

            
