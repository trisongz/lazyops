from __future__ import annotations

"""Performance configuration for File I/O operations.

This module provides adaptive configuration for optimizing file operations
based on file size, operation type, and system resources.
"""

import typing as t
from lzo.types import BaseSettings
from pydantic_settings import SettingsConfigDict

# Size thresholds for different optimization strategies
SMALL_FILE_THRESHOLD = 1024 * 1024  # 1 MB
MEDIUM_FILE_THRESHOLD = 10 * 1024 * 1024  # 10 MB
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50 MB
HUGE_FILE_THRESHOLD = 500 * 1024 * 1024  # 500 MB


class PerformanceConfig(BaseSettings):
    """Configuration for file I/O performance optimization.
    
    Provides adaptive chunk sizes and concurrency settings based on file size
    and operation type to optimize performance for both small and large files.
    """
    
    # Small files (< 1MB) - optimize for latency
    small_file_chunk_size: int = 8 * 1024  # 8 KB
    small_file_buffer_size: int = 64 * 1024  # 64 KB
    
    # Medium files (1MB - 10MB) - balance latency and throughput
    medium_file_chunk_size: int = 64 * 1024  # 64 KB
    medium_file_buffer_size: int = 256 * 1024  # 256 KB
    
    # Large files (10MB - 50MB) - optimize for throughput
    large_file_chunk_size: int = 256 * 1024  # 256 KB
    large_file_buffer_size: int = 1024 * 1024  # 1 MB
    
    # Huge files (50MB+) - maximum throughput
    huge_file_chunk_size: int = 1024 * 1024  # 1 MB
    huge_file_buffer_size: int = 4 * 1024 * 1024  # 4 MB
    
    # Concurrency settings for async operations
    max_concurrent_chunks: int = 8  # Maximum concurrent chunk operations
    max_concurrent_transfers: int = 4  # Maximum concurrent file transfers
    
    # Multipart upload/download settings (for cloud storage)
    multipart_threshold: int = 50 * 1024 * 1024  # 50 MB
    multipart_chunk_size: int = 8 * 1024 * 1024  # 8 MB
    
    # Memory management
    max_memory_buffer: int = 100 * 1024 * 1024  # 100 MB max buffered data
    enable_memory_mapping: bool = True  # Use mmap for large local files
    
    # Retry and timeout settings
    max_retries: int = 3
    retry_delay: float = 1.0  # seconds
    connection_timeout: int = 30  # seconds
    read_timeout: int = 300  # seconds (5 minutes for large files)

    model_config = SettingsConfigDict(
        env_prefix = "FILEIO_PERF_",
        case_sensitive = False,
        extra = 'allow',
        populate_by_name = True,
        validate_by_name = True,
        # allow_population_by_field_name = True,
    )
    
    # class Config:
    #     env_prefix = "FILEIO_PERF_"
    #     case_sensitive = False
    
    def get_optimal_chunk_size(self, file_size: t.Optional[int] = None) -> int:
        """Get optimal chunk size based on file size.
        
        Args:
            file_size: Size of the file in bytes. If None, returns default.
        
        Returns:
            Optimal chunk size in bytes.
        """
        if file_size is None:
            return self.medium_file_chunk_size
        
        if file_size < SMALL_FILE_THRESHOLD:
            return self.small_file_chunk_size
        elif file_size < MEDIUM_FILE_THRESHOLD:
            return self.medium_file_chunk_size
        elif file_size < LARGE_FILE_THRESHOLD:
            return self.large_file_chunk_size
        else:
            return self.huge_file_chunk_size
    
    def get_optimal_buffer_size(self, file_size: t.Optional[int] = None) -> int:
        """Get optimal buffer size based on file size.
        
        Args:
            file_size: Size of the file in bytes. If None, returns default.
        
        Returns:
            Optimal buffer size in bytes.
        """
        if file_size is None:
            return self.medium_file_buffer_size
        
        if file_size < SMALL_FILE_THRESHOLD:
            return self.small_file_buffer_size
        elif file_size < MEDIUM_FILE_THRESHOLD:
            return self.medium_file_buffer_size
        elif file_size < LARGE_FILE_THRESHOLD:
            return self.large_file_buffer_size
        else:
            return self.huge_file_buffer_size
    
    def should_use_multipart(self, file_size: int) -> bool:
        """Determine if multipart upload/download should be used.
        
        Args:
            file_size: Size of the file in bytes.
        
        Returns:
            True if multipart should be used, False otherwise.
        """
        return file_size >= self.multipart_threshold
    
    def get_concurrent_chunks(self, file_size: t.Optional[int] = None) -> int:
        """Get optimal number of concurrent chunk operations.
        
        Args:
            file_size: Size of the file in bytes. If None, returns default.
        
        Returns:
            Number of concurrent chunks to process.
        """
        if file_size is None or file_size < MEDIUM_FILE_THRESHOLD:
            return 2  # Minimal concurrency for small files
        elif file_size < LARGE_FILE_THRESHOLD:
            return 4  # Moderate concurrency
        else:
            return self.max_concurrent_chunks  # Maximum concurrency for large files
