# lzl.sysmon - System Monitoring

The `lzl.sysmon` module provides system monitoring and resource tracking capabilities.

## Module Reference

::: lzl.sysmon
    options:
      show_root_heading: true
      show_source: true

## Overview

The system monitoring module tracks CPU, memory, GPU, and other system resources, providing real-time insights into application performance.

## Usage Examples

### Basic Resource Monitoring

```python
from lzl.sysmon import get_system_info

info = get_system_info()
print(f"CPU Usage: {info.cpu_percent}%")
print(f"Memory Usage: {info.memory_percent}%")
print(f"Available Memory: {info.memory_available_mb}MB")
```

### Context-Based Monitoring

```python
from lzl.sysmon import SystemMonitor

with SystemMonitor() as monitor:
    # Your code here
    expensive_operation()
    
# Monitor automatically captures metrics
print(f"Peak memory: {monitor.peak_memory_mb}MB")
print(f"Average CPU: {monitor.avg_cpu_percent}%")
```

### GPU Monitoring

```python
from lzl.sysmon import get_gpu_info

if get_gpu_info().available:
    gpu = get_gpu_info()
    print(f"GPU Memory: {gpu.memory_used_mb}MB / {gpu.memory_total_mb}MB")
    print(f"GPU Utilization: {gpu.utilization_percent}%")
```

### Worker Context

```python
from lzl.sysmon import WorkerContext

# Track resources for a worker process
with WorkerContext(worker_id="worker-1") as ctx:
    process_batch(data)
    
print(f"Worker {ctx.worker_id} used {ctx.peak_memory_mb}MB")
```

### ML Context

```python
from lzl.sysmon import MLContext

# Specialized monitoring for ML workloads
with MLContext(model_name="resnet50") as ctx:
    train_model(model, data)
    
print(f"Training used {ctx.peak_gpu_memory_mb}MB GPU memory")
print(f"Total training time: {ctx.elapsed_seconds}s")
```

## Features

- **Real-Time Monitoring**: Track system resources in real-time
- **GPU Support**: Monitor NVIDIA GPUs with CUDA
- **Context Managers**: Easy integration with Python context managers
- **Metrics Collection**: Capture peak, average, and current metrics
- **Low Overhead**: Minimal performance impact
- **Cross-Platform**: Works on Linux, macOS, and Windows

## Metrics Tracked

- **CPU**: Utilization percentage, core count, load average
- **Memory**: Used, available, percentage, swap usage
- **GPU**: Memory usage, utilization, temperature (NVIDIA)
- **Disk**: I/O operations, read/write speeds
- **Network**: Bandwidth usage, connections

## Use Cases

- **Performance Profiling**: Identify resource bottlenecks
- **Capacity Planning**: Understand resource requirements
- **ML Training**: Monitor GPU utilization during training
- **Production Monitoring**: Track application resource usage
- **Debugging**: Identify memory leaks and resource issues
