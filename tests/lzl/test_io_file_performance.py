"""Tests for lzl.io.File performance optimizations.

This module tests the enhanced async methods and performance configurations
for handling large files and concurrent operations.
"""

import asyncio
import tempfile
import pytest
from pathlib import Path

# Test imports
try:
    from lzl.io import File
    from lzl.io.file.configs.performance import PerformanceConfig
    from lzl.io.file.utils.async_helpers import (
        ConcurrentChunkProcessor,
        AsyncBatchProcessor,
        with_retry,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="lzl.io.File not available")
class TestPerformanceConfig:
    """Test performance configuration."""
    
    def test_performance_config_creation(self):
        """Test creating a performance config."""
        config = PerformanceConfig()
        assert config.small_file_chunk_size == 8 * 1024
        assert config.huge_file_chunk_size == 1024 * 1024
        assert config.max_concurrent_chunks == 8
    
    def test_optimal_chunk_size(self):
        """Test chunk size selection based on file size."""
        config = PerformanceConfig()
        
        # Small file
        assert config.get_optimal_chunk_size(500 * 1024) == config.small_file_chunk_size
        
        # Medium file
        assert config.get_optimal_chunk_size(5 * 1024 * 1024) == config.medium_file_chunk_size
        
        # Large file
        assert config.get_optimal_chunk_size(25 * 1024 * 1024) == config.large_file_chunk_size
        
        # Huge file
        assert config.get_optimal_chunk_size(100 * 1024 * 1024) == config.huge_file_chunk_size
    
    def test_optimal_buffer_size(self):
        """Test buffer size selection based on file size."""
        config = PerformanceConfig()
        
        # Small file
        assert config.get_optimal_buffer_size(500 * 1024) == config.small_file_buffer_size
        
        # Huge file
        assert config.get_optimal_buffer_size(100 * 1024 * 1024) == config.huge_file_buffer_size
    
    def test_multipart_decision(self):
        """Test multipart upload/download decision."""
        config = PerformanceConfig()
        
        # Below threshold
        assert not config.should_use_multipart(10 * 1024 * 1024)
        
        # Above threshold
        assert config.should_use_multipart(100 * 1024 * 1024)
    
    def test_concurrent_chunks(self):
        """Test concurrent chunk count selection."""
        config = PerformanceConfig()
        
        # Small file - minimal concurrency
        assert config.get_concurrent_chunks(5 * 1024 * 1024) == 2
        
        # Large file - maximum concurrency
        assert config.get_concurrent_chunks(100 * 1024 * 1024) == config.max_concurrent_chunks


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="lzl.io.File not available")
class TestAsyncHelpers:
    """Test async helper utilities."""
    
    @pytest.mark.asyncio
    async def test_concurrent_chunk_processor(self):
        """Test concurrent chunk processor."""
        processor = ConcurrentChunkProcessor(max_concurrent=3)
        
        # Simple chunk processor that returns the chunk size
        async def process_chunk(chunk: bytes, index: int) -> int:
            await asyncio.sleep(0.01)  # Simulate I/O
            return len(chunk)
        
        # Create test chunks
        async def chunk_generator():
            for i in range(5):
                yield (b'test' * 100, i)
        
        results = await processor.process_chunks(chunk_generator(), process_chunk)
        assert len(results) == 5
        assert all(r == 400 for r in results)  # 'test' * 100 = 400 bytes
    
    @pytest.mark.asyncio
    async def test_async_batch_processor(self):
        """Test async batch processor."""
        processor = AsyncBatchProcessor(batch_size=3, max_concurrent_batches=2)
        
        # Simple processor that doubles the input
        async def double(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2
        
        items = list(range(10))
        results = await processor.process_items(items, double)
        
        assert len(results) == 10
        assert results == [i * 2 for i in items]
    
    @pytest.mark.asyncio
    async def test_retry_decorator(self):
        """Test retry decorator with exponential backoff."""
        
        call_count = 0
        
        @with_retry(max_retries=3, delay=0.01, backoff_factor=2.0)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Simulated error")
            return "success"
        
        result = await flaky_function()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_decorator_failure(self):
        """Test retry decorator when all retries fail."""
        
        @with_retry(max_retries=2, delay=0.01)
        async def always_fails():
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError, match="Always fails"):
            await always_fails()


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="lzl.io.File not available")
class TestOptimizedFileOperations:
    """Test optimized file operations."""
    
    @pytest.mark.asyncio
    async def test_aread_optimized_small_file(self):
        """Test optimized read for small files."""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            test_data = b"Small file content"
            f.write(test_data)
            temp_path = f.name
        
        try:
            file_path = File(temp_path)
            content = await file_path.aread_optimized()
            assert content == test_data
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_awrite_optimized_small_file(self):
        """Test optimized write for small files."""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            temp_path = f.name
        
        try:
            file_path = File(temp_path)
            test_data = b"Test data to write"
            bytes_written = await file_path.awrite_optimized(test_data)
            
            assert bytes_written == len(test_data)
            
            # Verify content
            content = await file_path.aread_optimized()
            assert content == test_data
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_acopy_to_optimized(self):
        """Test optimized file copy."""
        # Create source file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            test_data = b"Content to copy" * 1000
            f.write(test_data)
            src_path = f.name
        
        # Create destination path
        with tempfile.NamedTemporaryFile(delete=False) as f:
            dst_path = f.name
        
        try:
            src_file = File(src_path)
            dst_file = await src_file.acopy_to_optimized(dst_path, overwrite=True)
            
            # Verify copy
            dst_content = await dst_file.aread_optimized()
            assert dst_content == test_data
        finally:
            Path(src_path).unlink(missing_ok=True)
            Path(dst_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_aiter_raw_optimized(self):
        """Test optimized raw iteration."""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            test_data = b"x" * 10000
            f.write(test_data)
            temp_path = f.name
        
        try:
            file_path = File(temp_path)
            chunks = []
            
            async for chunk in file_path.aiter_raw_optimized(chunk_size=1000):
                chunks.append(chunk)
            
            reconstructed = b''.join(chunks)
            assert reconstructed == test_data
            assert len(chunks) > 1  # Should be chunked
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_large_file_simulation(self):
        """Test with larger file to trigger optimizations."""
        # Create a file that's large enough to trigger optimizations
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            # Create 2MB file
            test_data = b"x" * (2 * 1024 * 1024)
            f.write(test_data)
            temp_path = f.name
        
        try:
            file_path = File(temp_path)
            
            # Test optimized read
            content = await file_path.aread_optimized()
            assert len(content) == len(test_data)
            
            # Test optimized iteration with larger chunks
            chunk_count = 0
            async for chunk in file_path.aiter_raw_optimized(chunk_size=256*1024):
                chunk_count += 1
            
            # Should be chunked into multiple pieces
            assert chunk_count > 1
        finally:
            Path(temp_path).unlink(missing_ok=True)


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="lzl.io.File not available")
class TestFileIOConfigIntegration:
    """Test integration with FileIOConfig."""
    
    def test_performance_config_in_fileio_config(self):
        """Test that performance config is accessible from FileIOConfig."""
        from lzl.io.file.configs.main import FileIOConfig
        
        config = FileIOConfig()
        perf_config = config.performance
        
        assert isinstance(perf_config, PerformanceConfig)
        assert perf_config.max_concurrent_chunks > 0
        assert perf_config.multipart_threshold > 0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
