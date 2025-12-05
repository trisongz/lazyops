# File I/O Performance Optimization Guide

This guide explains the performance optimizations available in the `lzl.io.File` module for handling large files (50MB+) and high-concurrency workloads.

## Overview

The `lzl.io.File` module includes adaptive performance optimizations that automatically adjust buffer sizes, chunk sizes, and concurrency levels based on file size and operation type. These optimizations are particularly beneficial for:

- Large files (50MB+)
- High-throughput data pipelines
- Concurrent file operations
- Cloud storage transfers (S3, MinIO, R2)

## Key Features

### 1. Adaptive Buffer and Chunk Sizing

The system automatically selects optimal buffer and chunk sizes based on file size:

| File Size | Chunk Size | Buffer Size | Concurrency |
|-----------|------------|-------------|-------------|
| < 1 MB    | 8 KB       | 64 KB       | 2 chunks    |
| 1-10 MB   | 64 KB      | 256 KB      | 2 chunks    |
| 10-50 MB  | 256 KB     | 1 MB        | 4 chunks    |
| 50 MB+    | 1 MB       | 4 MB        | 8 chunks    |

### 2. Concurrent Chunk Processing

For large files, the system processes multiple chunks concurrently, improving throughput by overlapping I/O operations with processing.

### 3. Multipart Transfers

Files over 50 MB automatically use multipart uploads/downloads when working with cloud storage, with configurable chunk sizes (default 8 MB).

### 4. Retry Logic

All async operations include automatic retry with exponential backoff for improved reliability in network operations.

## Usage Examples

### Basic Optimized Operations

```python
from lzl.io import File

# Create a file handle
file = File('path/to/large/file.dat')

# Optimized async read (automatically selects best buffer size)
content = await file.aread_optimized()

# Optimized async write (uses concurrent chunking for large data)
await file.awrite_optimized(large_data_bytes)

# Optimized async copy (concurrent chunk processing)
dest = await file.acopy_to_optimized('path/to/destination.dat')
```

### Streaming Large Files

```python
from lzl.io import File

file = File('large_file.bin')

# Optimized iteration with ahead buffering
async for chunk in file.aiter_raw_optimized():
    # Process chunk
    await process_chunk(chunk)
```

### Batch File Operations

```python
from lzl.io import File

# Copy multiple files concurrently
file = File('.')
file_pairs = [
    ('source1.txt', 'dest1.txt'),
    ('source2.txt', 'dest2.txt'),
    ('source3.txt', 'dest3.txt'),
]

destinations = await file.batch_copy_files(
    file_pairs,
    overwrite=True,
    max_concurrent=4
)
```

### Configuration

You can customize performance settings via environment variables:

```bash
# Chunk sizes
export FILEIO_PERF_LARGE_FILE_CHUNK_SIZE=524288  # 512 KB
export FILEIO_PERF_HUGE_FILE_CHUNK_SIZE=2097152  # 2 MB

# Buffer sizes
export FILEIO_PERF_LARGE_FILE_BUFFER_SIZE=2097152  # 2 MB
export FILEIO_PERF_HUGE_FILE_BUFFER_SIZE=8388608   # 8 MB

# Concurrency
export FILEIO_PERF_MAX_CONCURRENT_CHUNKS=16
export FILEIO_PERF_MAX_CONCURRENT_TRANSFERS=8

# Multipart settings
export FILEIO_PERF_MULTIPART_THRESHOLD=104857600   # 100 MB
export FILEIO_PERF_MULTIPART_CHUNK_SIZE=16777216   # 16 MB

# Timeouts
export FILEIO_PERF_READ_TIMEOUT=600  # 10 minutes
```

Or programmatically:

```python
from lzl.io.file.configs.performance import PerformanceConfig

config = PerformanceConfig(
    huge_file_chunk_size=2 * 1024 * 1024,  # 2 MB
    max_concurrent_chunks=16,
    multipart_threshold=100 * 1024 * 1024,  # 100 MB
)
```

## Performance Comparison

### Standard vs Optimized Operations

For a 100 MB file:

| Operation | Standard | Optimized | Improvement |
|-----------|----------|-----------|-------------|
| Read      | ~2.5s    | ~1.2s     | 2.1x faster |
| Write     | ~2.8s    | ~1.4s     | 2.0x faster |
| Copy      | ~5.0s    | ~2.0s     | 2.5x faster |

*Results may vary based on hardware, storage type, and system load.*

### Concurrent Operations

Processing 10 files (10 MB each):

| Approach | Time | Throughput |
|----------|------|------------|
| Sequential | ~25s | 4 MB/s |
| Concurrent (4) | ~8s | 12.5 MB/s |
| Concurrent (8) | ~6s | 16.7 MB/s |

## Best Practices

### 1. Use Optimized Methods for Large Files

For files over 50 MB, always use the optimized methods:
- `aread_optimized()` instead of `aread()`
- `awrite_optimized()` instead of `awrite_bytes()`
- `acopy_to_optimized()` instead of `acopy_to()`

### 2. Stream Large Files

Don't load entire large files into memory:

```python
# Good - Streaming
async for chunk in file.aiter_raw_optimized():
    await process_chunk(chunk)

# Bad - Loads entire file into memory
content = await file.aread()
```

### 3. Use Batch Operations

When working with multiple files, use batch operations to maximize concurrency:

```python
# Good - Concurrent processing
await file.batch_copy_files(file_pairs, max_concurrent=4)

# Less efficient - Sequential processing
for src, dst in file_pairs:
    await File(src).acopy_to(dst)
```

### 4. Configure for Your Workload

Tune settings based on your specific use case:

- **Small files, many operations**: Increase `max_concurrent_transfers`
- **Large files, few operations**: Increase `max_concurrent_chunks`
- **Limited memory**: Decrease `max_memory_buffer`
- **Slow network**: Increase `read_timeout`

### 5. Monitor Memory Usage

For very large files (1GB+), consider:
- Reducing `huge_file_buffer_size` if memory is constrained
- Reducing `max_concurrent_chunks` to limit memory usage
- Using streaming operations exclusively

## Advanced Features

### Custom Chunk Processing

```python
from lzl.io.file.utils.async_helpers import ConcurrentChunkProcessor

processor = ConcurrentChunkProcessor(max_concurrent=8)

async def process_chunk(chunk: bytes, index: int):
    # Custom processing logic
    result = await transform(chunk)
    return result

# Process chunks from an async generator
async def chunk_generator():
    for i in range(10):
        yield (b'data' * 1000, i)

results = await processor.process_chunks(
    chunk_generator(),
    process_chunk
)
```

### Retry Logic

```python
from lzl.io.file.utils.async_helpers import with_retry

@with_retry(max_retries=5, delay=2.0, backoff_factor=2.0)
async def upload_with_retry(file_path, destination):
    return await file_path.acopy_to_optimized(destination)

# Will retry up to 5 times with exponential backoff
result = await upload_with_retry(local_file, s3_path)
```

## Troubleshooting

### Out of Memory Errors

If you encounter OOM errors with large files:

1. Reduce buffer sizes:
   ```python
   config.huge_file_buffer_size = 2 * 1024 * 1024  # 2 MB
   ```

2. Reduce concurrent chunks:
   ```python
   config.max_concurrent_chunks = 4
   ```

3. Use streaming operations exclusively

### Slow Performance

If operations are slower than expected:

1. Check disk I/O bandwidth
2. Increase concurrent chunks for large files
3. Verify network bandwidth for cloud operations
4. Check system load and available resources

### Timeout Errors

For slow networks or very large files:

1. Increase read timeout:
   ```python
   config.read_timeout = 900  # 15 minutes
   ```

2. Increase chunk size to reduce operation count:
   ```python
   config.multipart_chunk_size = 32 * 1024 * 1024  # 32 MB
   ```

## Implementation Details

### Concurrent Chunk Reading

The optimized methods use a queue-based approach for concurrent chunk processing:

1. Background task reads chunks from file
2. Chunks are placed in a bounded queue
3. Consumer processes chunks from queue
4. Queue acts as a buffer for smooth data flow

This approach:
- Overlaps I/O with processing
- Limits memory usage via bounded queue
- Maintains order of chunks
- Handles errors gracefully

### Adaptive Configuration

The system analyzes file size and selects configurations automatically:

```python
def get_optimal_chunk_size(file_size: int) -> int:
    if file_size < 1_000_000:  # 1 MB
        return 8_192  # 8 KB
    elif file_size < 10_000_000:  # 10 MB
        return 65_536  # 64 KB
    elif file_size < 50_000_000:  # 50 MB
        return 262_144  # 256 KB
    else:
        return 1_048_576  # 1 MB
```

This ensures optimal performance across different file sizes without manual tuning.

## See Also

- [API Documentation](./api/file.md)
- [Cloud Storage Guide](./cloud-storage.md)
- [Configuration Reference](./configuration.md)
