from __future__ import annotations

"""Enhanced async file operations with performance optimizations.

This module provides performance-optimized methods that can be mixed into
the FilePath class for improved handling of large files and concurrent operations.
"""

import typing as t
import asyncio

if t.TYPE_CHECKING:
    from .base import FilePath
    from ..main import PathLike
    from ..configs.performance import PerformanceConfig


class EnhancedAsyncMixin:
    """Mixin providing enhanced async file operations.
    
    This mixin adds optimized async methods to FilePath for better
    performance with large files and high-concurrency workloads.
    """
    
    async def aread_optimized(
        self: 'FilePath',
        mode: str = 'rb',
        chunk_size: t.Optional[int] = None,
        use_concurrent: bool = True,
        **kwargs
    ) -> t.Union[str, bytes]:
        """Optimized async file read with adaptive buffering.
        
        This method automatically selects optimal buffer sizes based on file size
        and can use concurrent chunk reading for improved throughput.
        
        Args:
            mode: File open mode ('rb' for binary, 'r' for text).
            chunk_size: Override automatic chunk size selection.
            use_concurrent: Use concurrent chunk reading for large files.
            **kwargs: Additional arguments passed to aopen.
        
        Returns:
            File contents as bytes or string.
        """
        from ..utils.registry import fileio_settings
        
        # Get file size for optimization
        try:
            file_size = await self.asize()
            perf_config = fileio_settings.performance
            
            # Determine optimal settings
            if chunk_size is None:
                chunk_size = perf_config.get_optimal_chunk_size(file_size)
            buffer_size = perf_config.get_optimal_buffer_size(file_size)
            
            # Use concurrent reading for large files
            if use_concurrent and file_size >= perf_config.multipart_threshold:
                return await self._aread_concurrent(mode, chunk_size)
            
            # Standard async read with optimized buffer
            async with self.aopen(mode, buffering=buffer_size, **kwargs) as f:
                return await f.read()
        
        except Exception:
            # Fallback to standard read if optimization fails
            return await self.aread(mode, **kwargs)
    
    async def _aread_concurrent(
        self: 'FilePath',
        mode: str = 'rb',
        chunk_size: int = 1024 * 1024,
    ) -> t.Union[str, bytes]:
        """Read file using concurrent chunk operations.
        
        Args:
            mode: File open mode.
            chunk_size: Size of each chunk.
        
        Returns:
            File contents.
        """
        from ..utils.async_helpers import read_file_chunks_concurrent
        
        chunks = []
        async for chunk in read_file_chunks_concurrent(self, chunk_size):
            chunks.append(chunk)
        
        result = b''.join(chunks)
        
        if 'b' not in mode:
            return result.decode('utf-8')
        return result
    
    async def awrite_optimized(
        self: 'FilePath',
        data: t.Union[bytes, str],
        mode: str = 'wb',
        chunk_size: t.Optional[int] = None,
        use_concurrent: bool = True,
        **kwargs
    ) -> int:
        """Optimized async file write with adaptive buffering.
        
        This method automatically selects optimal buffer sizes and can use
        concurrent chunk writing for improved throughput.
        
        Args:
            data: Data to write (bytes or string).
            mode: File open mode ('wb' for binary, 'w' for text).
            chunk_size: Override automatic chunk size selection.
            use_concurrent: Use concurrent chunk writing for large data.
            **kwargs: Additional arguments passed to aopen.
        
        Returns:
            Number of bytes written.
        """
        from ..utils.registry import fileio_settings
        
        # Convert string to bytes if needed
        if isinstance(data, str) and 'b' in mode:
            data = data.encode('utf-8')
        elif isinstance(data, bytes) and 'b' not in mode:
            data = data.decode('utf-8')
        
        data_size = len(data)
        perf_config = fileio_settings.performance
        
        # Determine optimal settings
        if chunk_size is None:
            chunk_size = perf_config.get_optimal_chunk_size(data_size)
        buffer_size = perf_config.get_optimal_buffer_size(data_size)
        
        # Use concurrent writing for large data
        if use_concurrent and data_size >= perf_config.multipart_threshold:
            return await self._awrite_concurrent(data, mode, chunk_size)
        
        # Standard async write with optimized buffer
        async with self.aopen(mode, buffering=buffer_size, **kwargs) as f:
            return await f.write(data)
    
    async def _awrite_concurrent(
        self: 'FilePath',
        data: t.Union[bytes, str],
        mode: str = 'wb',
        chunk_size: int = 1024 * 1024,
    ) -> int:
        """Write data using concurrent chunk operations.
        
        Args:
            data: Data to write.
            mode: File open mode.
            chunk_size: Size of each chunk.
        
        Returns:
            Number of bytes written.
        """
        from ..utils.async_helpers import write_file_chunks_concurrent
        
        # Ensure data is bytes
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Create async iterator of chunks
        async def chunk_generator():
            for i in range(0, len(data), chunk_size):
                yield data[i:i + chunk_size]
        
        return await write_file_chunks_concurrent(
            self,
            chunk_generator(),
        )
    
    async def acopy_to_optimized(
        self: 'FilePath',
        dest: 'PathLike',
        overwrite: bool = False,
        chunk_size: t.Optional[int] = None,
        use_concurrent: bool = True,
        **kwargs
    ) -> 'FilePath':
        """Optimized async file copy with concurrent chunk processing.
        
        This method uses concurrent chunk reading and writing for improved
        throughput when copying large files.
        
        Args:
            dest: Destination path.
            overwrite: Whether to overwrite existing file.
            chunk_size: Override automatic chunk size selection.
            use_concurrent: Use concurrent operations for large files.
            **kwargs: Additional arguments.
        
        Returns:
            Destination file path.
        
        Raises:
            FileExistsError: If destination exists and overwrite is False.
        """
        from ..utils.registry import fileio_settings
        from ..utils.async_helpers import copy_file_concurrent
        
        dst = self.get_pathlike_(dest)
        
        if not overwrite and await dst.aexists():
            raise FileExistsError(
                f"Destination file {dst} exists and overwrite is False"
            )
        
        # Get file size for optimization
        try:
            file_size = await self.asize()
            perf_config = fileio_settings.performance
            
            # Determine optimal settings
            if chunk_size is None:
                chunk_size = perf_config.get_optimal_chunk_size(file_size)
            
            # Use concurrent copy for large files
            if use_concurrent and file_size >= perf_config.multipart_threshold:
                max_concurrent = perf_config.get_concurrent_chunks(file_size)
                return await copy_file_concurrent(
                    self,
                    dst,
                    chunk_size=chunk_size,
                    max_concurrent=max_concurrent,
                    overwrite=overwrite,
                )
        
        except Exception:
            pass  # Fall through to standard copy
        
        # Standard async copy with optimized chunk size
        async with dst.aopen('wb') as f:
            async for chunk in self.aiter_raw(chunk_size=chunk_size):
                await f.write(chunk)
        
        return dst
    
    async def aiter_raw_optimized(
        self: 'FilePath',
        chunk_size: t.Optional[int] = None,
        use_concurrent: bool = True,
    ) -> t.AsyncIterator[bytes]:
        """Optimized async iteration over file bytes.
        
        This method uses adaptive chunk sizing and can buffer chunks ahead
        for improved throughput.
        
        Args:
            chunk_size: Override automatic chunk size selection.
            use_concurrent: Use concurrent buffering for large files.
        
        Yields:
            Byte chunks from the file.
        """
        from ..utils.registry import fileio_settings
        from ..utils.async_helpers import read_file_chunks_concurrent
        
        # Get file size for optimization
        try:
            file_size = await self.asize()
            perf_config = fileio_settings.performance
            
            # Determine optimal settings
            if chunk_size is None:
                chunk_size = perf_config.get_optimal_chunk_size(file_size)
            
            # Use concurrent reading for large files
            if use_concurrent and file_size >= perf_config.large_file_chunk_size:
                max_concurrent = perf_config.get_concurrent_chunks(file_size)
                async for chunk in read_file_chunks_concurrent(
                    self, chunk_size, max_concurrent
                ):
                    yield chunk
                return
        
        except Exception:
            pass  # Fall through to standard iteration
        
        # Standard iteration with optimized chunk size
        async for chunk in self.aiter_raw(chunk_size=chunk_size):
            yield chunk
    
    async def batch_copy_files(
        self: 'FilePath',
        file_pairs: t.List[t.Tuple['PathLike', 'PathLike']],
        overwrite: bool = False,
        max_concurrent: t.Optional[int] = None,
    ) -> t.List['FilePath']:
        """Copy multiple files concurrently in batches.
        
        This method efficiently copies multiple files using batched concurrent
        operations to maximize throughput.
        
        Args:
            file_pairs: List of (source, destination) path tuples.
            overwrite: Whether to overwrite existing files.
            max_concurrent: Maximum concurrent copy operations.
        
        Returns:
            List of destination file paths.
        """
        from ..utils.registry import fileio_settings
        from ..utils.async_helpers import AsyncBatchProcessor
        
        if max_concurrent is None:
            max_concurrent = fileio_settings.performance.max_concurrent_transfers
        
        # Create batch processor
        processor = AsyncBatchProcessor(
            batch_size=10,
            max_concurrent_batches=max_concurrent,
        )
        
        # Define copy function
        async def copy_file(pair: t.Tuple['PathLike', 'PathLike']) -> 'FilePath':
            src, dst = pair
            src_path = self.get_pathlike_(src)
            return await src_path.acopy_to_optimized(dst, overwrite=overwrite)
        
        # Process all copy operations
        return await processor.process_items(file_pairs, copy_file)


# Helper function to add enhanced methods to FilePath instances
def enhance_filepath_instance(instance: 'FilePath') -> 'FilePath':
    """Add enhanced async methods to a FilePath instance.
    
    Args:
        instance: FilePath instance to enhance.
    
    Returns:
        The enhanced instance.
    """
    # Bind methods to the instance
    for name in dir(EnhancedAsyncMixin):
        if not name.startswith('_') or name.startswith('_a'):
            attr = getattr(EnhancedAsyncMixin, name)
            if callable(attr):
                setattr(instance, name, attr.__get__(instance, type(instance)))
    
    return instance
