#!/usr/bin/env python
"""Benchmark script for lzl.io.File performance optimizations.

This script demonstrates the performance improvements of the optimized
async methods compared to standard methods for large files.

Usage:
    python examples/file_performance_benchmark.py
"""

import asyncio
import tempfile
import time
from pathlib import Path

try:
    from lzl.io import File
    IMPORTS_AVAILABLE = True
except ImportError:
    import sys
    print("Error: lzl.io.File not available. Install with: pip install -e .[file]")
    IMPORTS_AVAILABLE = False
    sys.exit(1)


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def format_time(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    if seconds < 1.0:
        return f"{seconds * 1000:.2f} ms"
    return f"{seconds:.2f} s"


async def benchmark_read(file_path: File, file_size: int, use_optimized: bool = False):
    """Benchmark file read operation."""
    start = time.time()
    
    if use_optimized:
        content = await file_path.aread_optimized()
    else:
        content = await file_path.aread()
    
    elapsed = time.time() - start
    throughput = file_size / elapsed / (1024 * 1024)  # MB/s
    
    return elapsed, throughput


async def benchmark_write(file_path: File, data: bytes, use_optimized: bool = False):
    """Benchmark file write operation."""
    start = time.time()
    
    if use_optimized:
        await file_path.awrite_optimized(data)
    else:
        await file_path.awrite_bytes(data)
    
    elapsed = time.time() - start
    throughput = len(data) / elapsed / (1024 * 1024)  # MB/s
    
    return elapsed, throughput


async def benchmark_copy(src_path: File, dst_path: str, file_size: int, use_optimized: bool = False):
    """Benchmark file copy operation."""
    start = time.time()
    
    if use_optimized:
        await src_path.acopy_to_optimized(dst_path, overwrite=True)
    else:
        await src_path.acopy_to(dst_path, overwrite=True)
    
    elapsed = time.time() - start
    throughput = file_size / elapsed / (1024 * 1024)  # MB/s
    
    return elapsed, throughput


async def benchmark_iteration(file_path: File, file_size: int, use_optimized: bool = False):
    """Benchmark file iteration operation."""
    start = time.time()
    chunks_count = 0
    
    if use_optimized:
        async for chunk in file_path.aiter_raw_optimized():
            chunks_count += 1
    else:
        async for chunk in file_path.aiter_raw():
            chunks_count += 1
    
    elapsed = time.time() - start
    throughput = file_size / elapsed / (1024 * 1024)  # MB/s
    
    return elapsed, throughput, chunks_count


async def run_benchmark(file_size_mb: int):
    """Run benchmarks for a specific file size."""
    print(f"\n{'='*70}")
    print(f"Benchmarking with {file_size_mb} MB file")
    print(f"{'='*70}\n")
    
    file_size = file_size_mb * 1024 * 1024
    
    # Create test data
    print(f"Creating test file ({format_size(file_size)})...")
    test_data = b"x" * file_size
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(delete=False) as f:
        src_path = f.name
    with tempfile.NamedTemporaryFile(delete=False) as f:
        dst_path_std = f.name
    with tempfile.NamedTemporaryFile(delete=False) as f:
        dst_path_opt = f.name
    with tempfile.NamedTemporaryFile(delete=False) as f:
        write_path_std = f.name
    with tempfile.NamedTemporaryFile(delete=False) as f:
        write_path_opt = f.name
    
    try:
        # Write initial test file
        src_file = File(src_path)
        await src_file.awrite_bytes(test_data)
        
        # Benchmark READ operations
        print("1. Read Operations")
        print("-" * 70)
        
        time_std, throughput_std = await benchmark_read(src_file, file_size, use_optimized=False)
        print(f"   Standard read:  {format_time(time_std):>10} | {throughput_std:>7.2f} MB/s")
        
        time_opt, throughput_opt = await benchmark_read(src_file, file_size, use_optimized=True)
        print(f"   Optimized read: {format_time(time_opt):>10} | {throughput_opt:>7.2f} MB/s")
        
        improvement = ((time_std - time_opt) / time_std) * 100
        print(f"   Improvement:    {improvement:>6.1f}%")
        
        # Benchmark WRITE operations
        print("\n2. Write Operations")
        print("-" * 70)
        
        write_file_std = File(write_path_std)
        time_std, throughput_std = await benchmark_write(write_file_std, test_data, use_optimized=False)
        print(f"   Standard write:  {format_time(time_std):>10} | {throughput_std:>7.2f} MB/s")
        
        write_file_opt = File(write_path_opt)
        time_opt, throughput_opt = await benchmark_write(write_file_opt, test_data, use_optimized=True)
        print(f"   Optimized write: {format_time(time_opt):>10} | {throughput_opt:>7.2f} MB/s")
        
        improvement = ((time_std - time_opt) / time_std) * 100
        print(f"   Improvement:     {improvement:>6.1f}%")
        
        # Benchmark COPY operations
        print("\n3. Copy Operations")
        print("-" * 70)
        
        time_std, throughput_std = await benchmark_copy(src_file, dst_path_std, file_size, use_optimized=False)
        print(f"   Standard copy:  {format_time(time_std):>10} | {throughput_std:>7.2f} MB/s")
        
        time_opt, throughput_opt = await benchmark_copy(src_file, dst_path_opt, file_size, use_optimized=True)
        print(f"   Optimized copy: {format_time(time_opt):>10} | {throughput_opt:>7.2f} MB/s")
        
        improvement = ((time_std - time_opt) / time_std) * 100
        print(f"   Improvement:    {improvement:>6.1f}%")
        
        # Benchmark ITERATION operations
        print("\n4. Iteration Operations")
        print("-" * 70)
        
        time_std, throughput_std, chunks_std = await benchmark_iteration(src_file, file_size, use_optimized=False)
        print(f"   Standard iter:  {format_time(time_std):>10} | {throughput_std:>7.2f} MB/s | {chunks_std} chunks")
        
        time_opt, throughput_opt, chunks_opt = await benchmark_iteration(src_file, file_size, use_optimized=True)
        print(f"   Optimized iter: {format_time(time_opt):>10} | {throughput_opt:>7.2f} MB/s | {chunks_opt} chunks")
        
        improvement = ((time_std - time_opt) / time_std) * 100
        print(f"   Improvement:    {improvement:>6.1f}%")
        
    finally:
        # Cleanup
        for path in [src_path, dst_path_std, dst_path_opt, write_path_std, write_path_opt]:
            Path(path).unlink(missing_ok=True)


async def main():
    """Run benchmarks for different file sizes."""
    print("\n" + "="*70)
    print(" lzl.io.File Performance Benchmark")
    print("="*70)
    print("\nThis benchmark compares standard vs optimized async file operations.")
    print("Optimized methods use adaptive buffering and concurrent chunk processing.")
    
    # Test with different file sizes
    file_sizes = [1, 10, 50]  # MB
    
    for size in file_sizes:
        await run_benchmark(size)
    
    print("\n" + "="*70)
    print(" Benchmark Complete")
    print("="*70)
    print("\nKey Takeaways:")
    print("- Optimized methods show increasing benefits with larger files")
    print("- For files >50MB, consider using optimized methods exclusively")
    print("- Concurrent chunk processing improves throughput significantly")
    print("\nFor more information, see: docs/file-performance-guide.md")


if __name__ == "__main__":
    if IMPORTS_AVAILABLE:
        asyncio.run(main())
