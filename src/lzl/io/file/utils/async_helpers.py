from __future__ import annotations

"""Async utilities for high-performance file I/O operations.

This module provides utilities for concurrent chunk processing, batch operations,
and optimized async I/O for large files.
"""

import asyncio
import typing as t
from functools import wraps

if t.TYPE_CHECKING:
    from ..types.base import FilePath
    from ..configs.performance import PerformanceConfig


class ConcurrentChunkProcessor:
    """Process file chunks concurrently with controlled concurrency.
    
    This class manages concurrent processing of file chunks with semaphore-based
    concurrency control to prevent resource exhaustion while maximizing throughput.
    """
    
    def __init__(self, max_concurrent: int = 8):
        """Initialize the concurrent chunk processor.
        
        Args:
            max_concurrent: Maximum number of concurrent chunk operations.
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
    
    async def process_chunk(
        self,
        chunk_processor: t.Callable[[bytes, int], t.Awaitable[t.Any]],
        chunk: bytes,
        index: int,
    ) -> t.Any:
        """Process a single chunk with concurrency control.
        
        Args:
            chunk_processor: Async function to process the chunk.
            chunk: The data chunk to process.
            index: Index of the chunk in the sequence.
        
        Returns:
            Result from the chunk processor.
        """
        async with self.semaphore:
            return await chunk_processor(chunk, index)
    
    async def process_chunks(
        self,
        chunks: t.AsyncIterable[t.Tuple[bytes, int]],
        chunk_processor: t.Callable[[bytes, int], t.Awaitable[t.Any]],
    ) -> t.List[t.Any]:
        """Process multiple chunks concurrently.
        
        Args:
            chunks: Async iterable of (chunk_data, index) tuples.
            chunk_processor: Async function to process each chunk.
        
        Returns:
            List of results from processing all chunks.
        """
        tasks = []
        async for chunk, index in chunks:
            task = asyncio.create_task(
                self.process_chunk(chunk_processor, chunk, index)
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks)


class AsyncBatchProcessor:
    """Process multiple file operations in batches.
    
    This class manages batched processing of file operations to optimize
    throughput when working with many files.
    """
    
    def __init__(self, batch_size: int = 10, max_concurrent_batches: int = 4):
        """Initialize the batch processor.
        
        Args:
            batch_size: Number of operations per batch.
            max_concurrent_batches: Maximum concurrent batches.
        """
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrent_batches)
    
    async def process_batch(
        self,
        batch: t.List[t.Any],
        processor: t.Callable[[t.Any], t.Awaitable[t.Any]],
    ) -> t.List[t.Any]:
        """Process a batch of items.
        
        Args:
            batch: List of items to process.
            processor: Async function to process each item.
        
        Returns:
            List of results from processing the batch.
        """
        async with self.semaphore:
            tasks = [asyncio.create_task(processor(item)) for item in batch]
            return await asyncio.gather(*tasks)
    
    async def process_items(
        self,
        items: t.Iterable[t.Any],
        processor: t.Callable[[t.Any], t.Awaitable[t.Any]],
    ) -> t.List[t.Any]:
        """Process items in batches.
        
        Args:
            items: Iterable of items to process.
            processor: Async function to process each item.
        
        Returns:
            Flattened list of all results.
        """
        results = []
        batch = []
        
        for item in items:
            batch.append(item)
            if len(batch) >= self.batch_size:
                batch_results = await self.process_batch(batch, processor)
                results.extend(batch_results)
                batch = []
        
        # Process remaining items
        if batch:
            batch_results = await self.process_batch(batch, processor)
            results.extend(batch_results)
        
        return results


async def read_file_chunks_concurrent(
    file_path: 'FilePath',
    chunk_size: t.Optional[int] = None,
    max_concurrent: int = 8,
) -> t.AsyncIterator[bytes]:
    """Read file in chunks with concurrent I/O operations.
    
    This function reads a file in chunks and buffers multiple chunks ahead
    to improve throughput for large files.
    
    Args:
        file_path: Path to the file to read.
        chunk_size: Size of each chunk. If None, determined automatically.
        max_concurrent: Maximum number of chunks to buffer ahead.
    
    Yields:
        Bytes chunks from the file.
    """
    from ..utils.registry import fileio_settings
    
    # Determine optimal chunk size if not specified
    if chunk_size is None:
        try:
            file_size = file_path.size()
            chunk_size = fileio_settings.performance.get_optimal_chunk_size(file_size)
        except Exception:
            chunk_size = fileio_settings.performance.medium_file_chunk_size
    
    # Use a queue to buffer chunks
    chunk_queue: asyncio.Queue = asyncio.Queue(maxsize=max_concurrent)
    
    async def read_chunks():
        """Read chunks and place them in the queue."""
        try:
            async with file_path.aopen('rb') as f:
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    await chunk_queue.put(chunk)
        finally:
            await chunk_queue.put(None)  # Sentinel to signal completion
    
    # Start reading chunks in background
    read_task = asyncio.create_task(read_chunks())
    
    try:
        # Yield chunks from the queue
        while True:
            chunk = await chunk_queue.get()
            if chunk is None:
                break
            yield chunk
    finally:
        # Ensure the read task completes
        await read_task


async def write_file_chunks_concurrent(
    file_path: 'FilePath',
    chunks: t.AsyncIterable[bytes],
    max_concurrent: int = 8,
) -> int:
    """Write chunks to file with concurrent buffering.
    
    This function writes chunks to a file with buffering to improve
    throughput for large files.
    
    Args:
        file_path: Path to the file to write.
        chunks: Async iterable of byte chunks to write.
        max_concurrent: Maximum number of chunks to buffer.
    
    Returns:
        Total number of bytes written.
    """
    total_bytes = 0
    chunk_queue: asyncio.Queue = asyncio.Queue(maxsize=max_concurrent)
    write_task = None
    
    async def write_chunks():
        """Write chunks from the queue."""
        nonlocal total_bytes
        try:
            async with file_path.aopen('wb') as f:
                while True:
                    chunk = await chunk_queue.get()
                    if chunk is None:
                        break
                    await f.write(chunk)
                    total_bytes += len(chunk)
        except Exception:
            # Drain queue on error to unblock producers
            while not chunk_queue.empty():
                try:
                    chunk_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            raise
    
    try:
        # Start writing chunks in background
        write_task = asyncio.create_task(write_chunks())
        
        # Put chunks in the queue
        async for chunk in chunks:
            await chunk_queue.put(chunk)
    finally:
        # Signal completion
        await chunk_queue.put(None)
        # Ensure write task completes
        if write_task:
            await write_task
    
    return total_bytes


def with_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: t.Tuple[t.Type[Exception], ...] = (Exception,),
):
    """Decorator to retry async functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts.
        delay: Initial delay between retries in seconds.
        backoff_factor: Multiplier for delay after each retry.
        exceptions: Tuple of exception types to catch and retry.
    
    Returns:
        Decorated function with retry logic.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        raise
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


async def copy_file_concurrent(
    src_path: 'FilePath',
    dst_path: 'FilePath',
    chunk_size: t.Optional[int] = None,
    max_concurrent: int = 8,
    overwrite: bool = False,
) -> 'FilePath':
    """Copy file with concurrent chunk processing.
    
    This function copies a file using concurrent chunk reading and writing
    to improve throughput for large files.
    
    Args:
        src_path: Source file path.
        dst_path: Destination file path.
        chunk_size: Size of each chunk. If None, determined automatically.
        max_concurrent: Maximum number of concurrent chunk operations.
        overwrite: Whether to overwrite existing destination file.
    
    Returns:
        The destination file path.
    
    Raises:
        FileExistsError: If destination exists and overwrite is False.
    """
    # Note: This check is not atomic with the write operation, but provides
    # a reasonable guard against accidental overwrites in most cases.
    # For truly atomic operations, consider using file locks or O_EXCL flag.
    if not overwrite and await dst_path.aexists():
        raise FileExistsError(f"Destination file {dst_path} exists and overwrite is False")
    
    # Read chunks concurrently from source
    chunks = read_file_chunks_concurrent(src_path, chunk_size, max_concurrent)
    
    # Write chunks concurrently to destination
    await write_file_chunks_concurrent(dst_path, chunks, max_concurrent)
    
    return dst_path
