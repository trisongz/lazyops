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