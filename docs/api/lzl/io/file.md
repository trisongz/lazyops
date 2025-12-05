# lzl.io.file - Unified File Operations

The `lzl.io.file` module provides a powerful, unified abstraction for file system operations, supporting both local and cloud storage (S3, MinIO, R2) with synchronous and asynchronous APIs. It automatically selects the appropriate backend based on the file path scheme.

## Overview

The `File` class is the main entry point. It acts as a factory that instantiates the correct concrete path object (e.g., `Path` for local files, `FileS3Path` for S3).

::: lzl.io.file
    options:
      members:
        - File

## Supported Schemes

- **Local Files**: `/path/to/file`, `relative/path`
- **AWS S3**: `s3://bucket/key`
- **MinIO**: `minio://bucket/key`
- **Cloudflare R2**: `r2://bucket/key`
- **SMB/CIFS**: `smb://host/share/path`

## Usage Examples

### Basic File I/O

```python
from lzl.io import File

# Write text (sync)
File("data.txt").write_text("Hello World")

# Read text (async)
content = await File("data.txt").async_read_text()

# Check existence
if await File("data.txt").async_exists():
    print("File exists!")
```

### Cloud Storage (S3)

```python
from lzl.io import File

# Working with S3 paths
s3_file = File("s3://my-bucket/data.csv")

# Read bytes
data = await s3_file.read_bytes()

# Get metadata
size = s3_file.size
last_modified = s3_file.stat().st_mtime
```

### SMB/CIFS Shares

You can access SMB shares using the `smb://` scheme. Configure credentials via environment variables (`SMB_HOST`, `SMB_USERNAME`, `SMB_PASSWORD`) or the registry.

```python
from lzl.io import File

# Access an SMB share
smb_file = File("smb://share/data/report.csv")
content = await smb_file.aread_text()
```

### Pydantic Integration

`File` is fully compatible with Pydantic v1 and v2, making it ideal for configuration models.

```python
from pydantic import BaseModel
from lzl.io import File

class Config(BaseModel):
    dataset_path: File
    output_dir: File

# Validates and converts strings to File objects
config = Config(
    dataset_path="s3://data/sets/train.parquet",
    output_dir="/tmp/output"
)

print(config.dataset_path.scheme) # 's3'
```

### Custom Loaders

You can register custom loaders for specific file extensions.

```python
from lzl.io import File
import json

def load_json(file: File):
    return json.loads(file.read_text())

# Register the loader
File.register_loader(".json", load_json)

# Now you can load directly (implementation dependent on registered hooks)
# data = File("config.json").load() 
```

## Performance Optimization

The `lzl.io.File` module includes performance optimizations for handling large files, particularly with object storage.

### Optimized I/O

Standard methods (`aread`, `awrite_bytes`, `acopy_to`, `aiter_raw`) support an `optimized` argument to enable adaptive buffering and concurrent chunk transfers.

- `optimized=True`: Always use the optimized implementation.
- `optimized=False`: Always use the standard implementation.
- `optimized='auto'` (default): Automatically switch to optimized methods for files larger than 5MB.

```python
# Explicitly enable optimization
data = await File("s3://bucket/large-file.dat").aread(optimized=True)

# 'auto' handles it for you
await File("local-large.iso").acopy_to("s3://bucket/backup.iso", optimized="auto")
```

## Batch Operations

When working with multiple files, especially on cloud storage where latency is high, use batch operations to perform actions concurrently.

```python
files = [File(f"s3://bucket/logs/log_{i}.txt") for i in range(100)]

# Check existence concurrently
existence_map = await File(".").batch_exists(files)

# Delete concurrently
await File(".").batch_delete(files)
```

## Advanced Features

### Directory Management

```python
# Get the parent directory
parent = File.get_dir("path/to/file.txt")

# Check object size
size = File.get_object_size("some data")
print(f"Size: {size.human_readable}")
```

## Spec and Path Types

Deep dive into the underlying path implementations and specifications.

::: lzl.io.file.spec.main
::: lzl.io.file.path

## Configuration

Configure storage backends and behavior.

::: lzl.io.file.configs

## Utilities

Helper functions for file operations.

::: lzl.io.file.utils