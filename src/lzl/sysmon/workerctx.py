from __future__ import annotations

import gc
import abc
import contextlib
import typing as t
from lzl.types import eproperty

if t.TYPE_CHECKING:
    from lzo.utils.system.gpu import GPUData
    from lzo.utils.system.resources import ResourceData
    

class WorkerContext(abc.ABC):
    """
    Base Worker Context Handler
    """

    def __init__(self, **kwargs):
        """
        Initialize the WorkerContext with the given keyword arguments.
        """
        from lzo.utils import Timer
        from lzl.logging import logger
        from pydantic.types import ByteSize
        from lzo.utils.system import get_gpu_data, aget_gpu_data
        from lzo.utils.system import get_resource_data

        self._extra: t.Dict[str, t.Any] = {}
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

        self.last_resource_data: t.Optional['ResourceData'] = None
        self.last_gpu_data: t.Optional['GPUData'] = None

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
    

    @eproperty
    def worker_name(self) -> t.Optional[str]:
        """
        Returns the name of the current worker.
        """
        return self._extra.get('worker_name')


    def build_gpu_data_string(self, current_usage: 'GPUData', compare: t.Optional[bool] = None, previous_usage: t.Optional['GPUData'] = None, colored: bool = False) -> t.Optional[str]:
        """
        Constructs the GPU Data String
        """
        curr_mem_used = current_usage['memory_used']
        curr_mem_percent = current_usage['utilization_memory']
        curr_mem_total = current_usage['memory_total']
        gpu_name = current_usage['name']
        
        previous_usage = previous_usage or self.last_gpu_data
        self.last_gpu_data = current_usage
        if compare and previous_usage:
            comparison: GPUData = {
                'memory_used': self._bs(curr_mem_used - previous_usage['memory_used']),
                'utilization_memory': curr_mem_percent - previous_usage['utilization_memory']
            }
            if not colored: return f"{gpu_name}: {previous_usage['memory_used'].human_readable()} -> {curr_mem_used.human_readable()} / {curr_mem_total.human_readable()} + {comparison['memory_used'].human_readable()} ({comparison['utilization_memory']} -> {curr_mem_percent}%)"
            return f"{gpu_name}: {previous_usage['memory_used'].human_readable()} -> |y|{curr_mem_used.human_readable()}|e| / |g|{curr_mem_total.human_readable()}|e| + |r|{comparison['memory_used'].human_readable()}|e|  ({comparison['utilization_memory']} -> {curr_mem_percent}%)"
        if not colored: return f"{gpu_name}: {curr_mem_used.human_readable()} / {curr_mem_total.human_readable()} ({curr_mem_percent}%)"
        return f"{gpu_name}: |y|{curr_mem_used.human_readable()}|e| / |g|{curr_mem_total.human_readable()}|e| ({curr_mem_percent}%)"


    def get_gpu_memory(self, compare: t.Optional[bool] = None, previous_usage: t.Optional[GPUData] = None, colored: bool = False) -> t.Optional[str]:
        """
        Returns the GPU memory usage information.

        Args:
            compare (bool, optional): Whether to compare with previous usage.
            short (bool, optional): Whether to return a short summary.
            colored (bool, optional): Whether to return colored output.
        """
        current_usage = self.get_gpu_data()
        if not current_usage: return None
        return self.build_gpu_data_string(current_usage, compare = compare, previous_usage = previous_usage, colored = colored)

    async def aget_gpu_memory(self, compare: t.Optional[bool] = None, previous_usage: t.Optional[GPUData] = None, colored: bool = False) -> t.Optional[str]:
        """
        Returns the GPU memory usage information.

        Args:
            compare (bool, optional): Whether to compare with previous usage.
            short (bool, optional): Whether to return a short summary.
            colored (bool, optional): Whether to return colored output.
        """
        current_usage = await self.aget_gpu_data()
        if not current_usage: return None
        return self.build_gpu_data_string(current_usage, compare = compare, previous_usage = previous_usage, colored = colored)


    def build_resource_data_string(self, current_usage: 'ResourceData', compare: t.Optional[bool] = None, previous_usage: t.Optional['ResourceData'] = None, colored: bool = False) -> t.Optional[str]:
        """
        Constructs the Resource Data String
        """
        curr_mem_used = current_usage['memory_used']
        curr_mem_percent = current_usage['utilization_memory']
        curr_mem_total = current_usage['memory_total']
        curr_cpu_percent = current_usage['utilization_cpu']

        num_cpu = current_usage['cpu_count']

        previous_usage = previous_usage or self.last_resource_data
        self.last_resource_data = current_usage

        if compare and previous_usage:
            comparison: 'ResourceData' = {
                'memory_used': self._bs(curr_mem_used - previous_usage['memory_used']),
                'utilization_memory': curr_mem_percent - previous_usage['utilization_memory'],
                # 'utilization_cpu': curr_cpu_percent - previous_usage['utilization_cpu']
            }
            if not colored: return f"{num_cpu}vCPU: {curr_cpu_percent}% |  RAM: {previous_usage['memory_used'].human_readable()} -> {curr_mem_used.human_readable()} / {curr_mem_total.human_readable()} + {comparison['memory_used'].human_readable()} ({comparison['utilization_memory']} -> {curr_mem_percent}%)"
            return f"{num_cpu}vCPU: |g|{curr_cpu_percent}%|e| |  RAM: {previous_usage['memory_used'].human_readable()} -> |y|{curr_mem_used.human_readable()}|e| / |g|{curr_mem_total.human_readable()}|e| + |r|{comparison['memory_used'].human_readable()}|e|  ({comparison['utilization_memory']} -> {curr_mem_percent}%)"
        if not colored: return f"{num_cpu}vCPU: {curr_cpu_percent}% |  RAM: {curr_mem_used.human_readable()} / {curr_mem_total.human_readable()} ({curr_mem_percent}%)"
        return f"{num_cpu}vCPU: |g|{curr_cpu_percent}%|e|  RAM: |y|{curr_mem_used.human_readable()}|e| / |g|{curr_mem_total.human_readable()}|e| ({curr_mem_percent}%)"

    def get_resource_info(self, compare: t.Optional[bool] = None, previous_usage: t.Optional['ResourceData'] = None, colored: bool = False) -> t.Optional[str]:
        """
        Returns the resource usage information.

        Args:
            compare (bool, optional): Whether to compare with previous usage.
            previous_usage (ResourceData, optional): Previous resource usage data.
            colored (bool, optional): Whether to return colored output.
        """
        current_usage = self.get_resource_data()
        if not current_usage: return None
        return self.build_resource_data_string(current_usage, compare = compare, previous_usage = previous_usage, colored = colored)

    @contextlib.contextmanager
    def inference_mode(
        self, 
        batch_size: t.Optional[int] = 1,
        obj_name: t.Optional[str] = None,
        enable_gc: t.Optional[bool] = None,
        enable_summary: t.Optional[bool] = None,
        hook: t.Optional[t.Callable[[t.Dict[str, t.Any]], None]] = None,
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
        self.logger.info(start_text, prefix = self.model_name, colored = True, hook = hook)
        start_resource_data = self.get_resource_data()
        if self.has_gpu:
            start_gpu_data = self.get_gpu_data()
        try:
            yield
        except Exception as e:
            self.logger.trace(f'[{self.model_name}] Error in Inference Mode: ', e, hook = hook)
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
            
            self.logger.info(end_text, colored = True, prefix = self.model_name, hook = hook)
            if enable_summary:
                self.logger.info(f"Total Requests: |g|{self.idx}|e|. Total Batches Handled: |g|{self.num_batches}|e|. Handled Last Batch Size of |g|{self.last_batch_size}|e|", colored = True, prefix = self.model_name, hook = hook)
                self.logger.info(f"Total Inference Duration: |g|{self.timer.pformat_duration(self.total_duration)}|e|. Total Time Alive: |g|{self.t.total_s}|e|", colored = True, prefix = self.model_name, hook = hook)
            self.logger.info(self.get_resource_info(compare = True, previous_usage = start_resource_data, colored = True), colored = True, prefix = self.model_name, hook = hook)
            if self.has_gpu:
                self.logger.info(self.get_gpu_memory(compare = True, previous_usage = start_gpu_data, colored = True), colored = True, prefix = self.model_name, hook = hook)



    @contextlib.asynccontextmanager
    async def ainference_mode(
        self, 
        batch_size: t.Optional[int] = 1,
        obj_name: t.Optional[str] = None,
        enable_gc: t.Optional[bool] = None,
        enable_summary: t.Optional[bool] = None,
        hook: t.Optional[t.Callable[[t.Dict[str, t.Any]], None]] = None,
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
        start_resource_data = self.get_resource_data()
        if self.has_gpu:
            start_gpu_data = await self.aget_gpu_data()
        try:
            yield
        except Exception as e:
            self.logger.trace(f'[{self.model_name}] Error in Inference Mode: ', e, hook = hook)
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

            self.logger.info(end_text, colored = True, prefix = self.model_name, hook = hook)
            if enable_summary:
                self.logger.info(f"Total Requests: |g|{self.idx}|e|. Total Batches Handled: |g|{self.num_batches}|e|. Handled Last Batch Size of |g|{self.last_batch_size}|e|", colored = True, prefix = self.model_name, hook = hook)
                self.logger.info(f"Total Inference Duration: |g|{self.timer.pformat_duration(self.total_duration)}|e|. Total Time Alive: |g|{self.t.total_s}|e|", colored = True, prefix = self.model_name, hook = hook)
            self.logger.info(self.get_resource_info(compare = True, previous_usage = start_resource_data, colored = True), colored = True, prefix = self.model_name, hook = hook)
            if self.has_gpu:
                self.logger.info(await self.aget_gpu_memory(compare = True, previous_usage = start_gpu_data, colored = True), colored = True, prefix = self.model_name, hook = hook)


    @contextlib.contextmanager
    def capture(
        self, 
        message: t.Optional[str] = None,
        prefix: t.Optional[str] = None,
        hook: t.Optional[t.Callable[[t.Dict[str, t.Any]], None]] = None,
        **kwargs,
    ):
        """
        Context manager to capture

        Args:
            prefix (str, optional): The prefix for log messages.
        """
        ts = self.timer(format_ms = True, format_short = 1)
        base_name = self.model_name or self.worker_name
        prefix = f'{prefix} {base_name}' if prefix else base_name
        start_resource_data = self.get_resource_data()
        if self.has_gpu:
            start_gpu_data = self.get_gpu_data()
        try:
            yield
        except Exception as e:
            self.logger.trace(f'[{prefix}] Error in Capture: ', e, hook = hook)
            raise e
        finally:
            message = message or "Capture Complete"
            message += f" in {ts.total_s}"
            self.logger.info(message, colored = True, prefix = prefix, hook = hook)
            self.logger.info(self.get_resource_info(compare = True, previous_usage = start_resource_data, colored = True), colored = True, prefix = prefix, hook = hook)
            if self.has_gpu:
                self.logger.info(self.get_gpu_memory(compare = True, previous_usage = start_gpu_data, colored = True), colored = True, prefix = prefix, hook = hook)



    @contextlib.contextmanager
    def start_task(
        self, 
        batch_size: t.Optional[int] = 1,
        obj_name: t.Optional[str] = None,
        task_name: t.Optional[str] = None,
        enable_gc: t.Optional[bool] = None,
        enable_summary: t.Optional[bool] = None,
        hook: t.Optional[t.Callable[[t.Dict[str, t.Any]], None]] = None,
        **kwargs,
    ):
        """
        Context manager for starting a task

        Args:
            batch_size (int, optional): The batch size for task.
            obj_name (str, optional): The name of the object being processed.
            task_name (str, optional): The name of the task being performed.
            enable_gc (bool, optional): Whether to enable garbage collection.
            enable_summary (bool, optional): Whether to enable summary logging.
        """
        ts = self.timer(format_ms = True, format_short = 1)
        start_text = "Starting Task"
        base_name = self.model_name or self.worker_name
        if task_name: start_text += f": |g|{task_name}|e|"
        if obj_name: start_text += f" for |g|{obj_name}|e|"
        start_text += f" ({batch_size})"
        self.logger.info(start_text, prefix = base_name, colored = True, hook = hook)
        start_resource_data = self.get_resource_data()
        if self.has_gpu: start_gpu_data = self.get_gpu_data()
        try:
            yield
        except Exception as e:
            self.logger.trace(f'[{base_name}] Error in Task: ', e, hook = hook)
            raise e
        finally:
            total_s = ts.total
            self.total_duration += total_s
            self.last_duration = total_s
            self.num_batches += batch_size
            self.idx += 1

            end_text = "Task Completed"
            if task_name: end_text += f": |g|{task_name}|e|"
            if obj_name: end_text += f" for |g|{obj_name}|e|"
            end_text += f" ({batch_size}) in {ts.total_s}"
            if enable_gc: gc.collect()

            self.logger.info(end_text, colored = True, prefix = base_name, hook = hook)
            if enable_summary:
                self.logger.info(f"Total Tasks: |g|{self.idx}|e|. Total Batches Handled: |g|{self.num_batches}|e|. Handled Last Batch Size of |g|{self.last_batch_size}|e|", colored = True, prefix = base_name, hook = hook)
                self.logger.info(f"Total Task Duration: |g|{self.timer.pformat_duration(self.total_duration)}|e|. Total Time Alive: |g|{self.t.total_s}|e|", colored = True, prefix = base_name, hook = hook)
            self.logger.info(self.get_resource_info(compare = True, previous_usage = start_resource_data, colored = True), colored = True, prefix = base_name, hook = hook)
            if self.has_gpu:
                self.logger.info(self.get_gpu_memory(compare = True, previous_usage = start_gpu_data, colored = True), colored = True, prefix = base_name, hook = hook)



    def __enter__(self):
        return self
    
