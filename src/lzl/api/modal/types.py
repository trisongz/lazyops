from __future__ import annotations

"""
Modal Classes and Objects that serve as the base class that can be subclassed
"""
import os
import sys
import contextlib
import typing as t
from lzl import load

if load.TYPE_CHECKING:
    import torch
else:
    torch = load.LazyLoad("torch", install_missing=True)


class NoStdStreams(object):
    def __init__(self):
        self.devnull = open(os.devnull, "w")

    def __enter__(self):
        self._stdout, self._stderr = sys.stdout, sys.stderr
        self._stdout.flush(), self._stderr.flush()
        sys.stdout, sys.stderr = self.devnull, self.devnull

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout, sys.stderr = self._stdout, self._stderr
        self.devnull.close()


class ModalClass:
    """
    Base class for Modal classes.
    """

    def _setup_(self, **kwargs):
        """
        Setup method that initializes certain properties or configurations.
        """
        from lzl.logging import logger
        from lzo.utils import Timer
        from .static import MODAL_GPU_PRICING

        self.t = Timer()
        self.timer = Timer
        self.logger = logger

        self.device_name = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = torch.device(self.device_name)
        self.has_gpu = torch.cuda.is_available()
        self.gpu_device_name: t.Optional[str] = None
        self.gpu_cost_per_sec: float = 0.0
        if self.has_gpu:
            # NVIDIA A2
            from lzo.utils.system import get_gpu_data
            gpu_data = get_gpu_data()
            self.gpu_device_name = gpu_data['name'] if gpu_data else None
            self.gpu_cost_per_sec = MODAL_GPU_PRICING.get(self.gpu_device_name, 0.0)
            self.logger.info(f"Using GPU: |g|{self.gpu_device_name}|e|", colored = True, prefix = self.model_name)
        
        self.cold_start_time = self.t.total
        self.cold_start_time_str = self.timer.pformat_duration(self.cold_start_time)
        self.last_req_duration: float = 0.0
        self.last_req_batch_size: int = 0
        self.last_req_cost: float = 0.0
        self.last_gpu_memory: t.Optional[str] = None
        self._load_model_(**kwargs)
        self.logger.info(f"Loading Model: {self.model_id} in |g|{self.t.total_s}|e| on {self.device_name}", colored = True, prefix = self.model_name)
        self.num_requests: int = 0
        self.batches_handled: int = 0
        self.total_duration: float = 0.0


    def _load_model_(self, **kwargs):
        """
        Load the model with the given keyword arguments.
        """
        pass
    
    @property
    def model_id(self) -> t.Optional[str]:
        """
        Returns the model ID.
        """
        return getattr(self, 'MODEL_ID', None)
    
    @property
    def model_name(self) -> t.Optional[str]:
        """
        Returns the model name.
        """
        return getattr(self, 'MODEL_NAME', None)
    
    def update_metadata(self, metadata: t.Dict[str, t.Any]) -> None:
        """
        Updates the metadata
        """
        metadata.update({
            'cost_value': self.last_req_cost,
            'cost_string': f"${self.last_req_cost:,.5f}",
            'batch_size': self.last_req_batch_size,
            'duration_value': self.last_req_duration,
            'duration_string': self.timer.pformat_duration(self.last_req_duration, include_ms = True, short = 1),
            'cold_start_time_string': self.cold_start_time_str,
            'cold_start_time_value': self.cold_start_time,
        })
        if self.has_gpu: metadata['gpu_memory'] = self.last_gpu_memory
    
    """
    Utility functions
    """

    def _prestop_(self):
        """
        The exit point for the model
        """
        self.logger.info(f"|r|[Shutting Down]|e| Completed Requests: |g|{self.num_requests}|e|. Total Batches Handled: |g|{self.batches_handled}|e|", colored = True, prefix = self.model_name)
        self.logger.info(f"|r|[Shutting Down]|e| Total Inference Duration: |g|{self.timer.pformat_duration(self.total_duration)}|e|. Total Time Alive: |g|{self.t.total_s}|e|", colored = True, prefix = self.model_name)
        if self.gpu_cost_per_sec:
            self.logger.info(f"|r|[Shutting Down]|e| Total Cost: |y|${self.t.total * self.gpu_cost_per_sec:,.4f}|e|", colored = True, prefix = self.model_name)
        if self.has_gpu:
            self.logger.info(f"|r|[Shutting Down]|e| {self.get_gpu_memory_nvidia_smi(colored = True)}", colored = True, prefix = self.model_name)


    
    @contextlib.contextmanager
    def inference_mode(self):
        """
        Handles the inference mode
        """
        with torch.inference_mode():
            t = self.timer(format_ms = True, format_short = 1)
            try:
                yield
            except Exception as e:
                self.logger.error(f"[{self.model_id}] Error in inference mode: {e}")
                raise e
            finally:
                total_s = t.total
                self.last_req_duration = total_s
                self.total_duration += total_s
                self.num_requests += 1
                if self.gpu_cost_per_sec:
                    self.last_req_cost = total_s * self.gpu_cost_per_sec
                if self.has_gpu:
                    self.last_gpu_memory = self.get_gpu_memory_nvidia_smi(colored = False)
                self.logger.info(f"Total Requests: |g|{self.num_requests}|e|. Total Batches Handled: |g|{self.batches_handled}|e|. Handled Last Batch Size of |g|{self.last_req_batch_size}|e| in |g|{t.total_s}|e|", colored = True, prefix = self.model_name)
                self.logger.info(f"Total Inference Duration: |g|{self.timer.pformat_duration(self.total_duration)}|e|. Total Time Alive: |g|{self.t.total_s}|e|", colored = True, prefix = self.model_name)
                self.logger.info(f"Total Cost: |y|${self.last_req_cost:,.5f}|e|", colored = True, prefix = self.model_name)
                if self.has_gpu:
                    self.logger.info(f"{self.get_gpu_memory_nvidia_smi(colored = True)}", colored = True, prefix = self.model_name)


    def get_gpu_memory_nvidia_smi(self, short: bool = None, colored: bool = False) -> t.Optional[str]:
        """
        Returns the GPU memory
        """
        from lzo.utils.system import get_gpu_data
        gpu_data = get_gpu_data()
        if not gpu_data: return None
        mem_used = gpu_data['memory_used']
        if short: return mem_used.human_readable()
        mem_percent = gpu_data['utilization_memory']
        mem_total = gpu_data['memory_total']
        gpu_name = gpu_data['name']
        if not colored: return f"{gpu_name}: {mem_used.human_readable()} / {mem_total.human_readable()} ({mem_percent}%)"
        return f"{gpu_name}: |g|{mem_used.human_readable()}|e| / |y|{mem_total.human_readable()}|e| ({mem_percent}%)"
    