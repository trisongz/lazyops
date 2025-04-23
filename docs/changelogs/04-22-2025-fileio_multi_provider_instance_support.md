# Changelog: FileIO Multi-Provider Instance Support

**Date:** April 22, 2025

## Summary

Refactored the `lzl.io.file` subsystem to support configuring and using multiple instances of the same cloud storage provider concurrently (e.g., connecting to two different MinIO servers). This is achieved through environment variable prefixes and custom URI schemes.

## Justification

The previous implementation only allowed a single configuration per provider type (AWS, MinIO, etc.) at a time. This limited use cases requiring interaction with multiple distinct endpoints of the same provider type within a single application instance. This refactoring enables greater flexibility in managing cloud storage connections.

## Usage Examples

### Environment Variable Configuration

To configure multiple MinIO instances:

1.  **Default Instance:** Use standard `MINIO_*` environment variables:
    ```bash
    export MINIO_ENDPOINT="http://minio1.example.com:9000"
    export MINIO_ACCESS_KEY="minioadmin"
    export MINIO_SECRET_KEY="minioadmin"
    ```
    Paths starting with `mc://` (or `minio://`, `mio://`) will use this configuration.

2.  **Additional Instances:** Define a mapping in `FILEIO_MINIO_ENV_PREFIXES`. The format is `ENV_VAR_PREFIX:uri_scheme`, separated by commas. Then, define environment variables using the specified prefixes.

    ```bash
    # Define two additional MinIO instances:
    # - One using prefix MINIO_PROD_ and scheme 'mcp'
    # - One using prefix MINIO_DEV_ and scheme 'mcd'
    export FILEIO_MINIO_ENV_PREFIXES="MINIO_PROD_:mcp,MINIO_DEV_:mcd"

    # Configuration for 'mcp' instance
    export MINIO_PROD_ENDPOINT="http://minio-prod.internal:9000"
    export MINIO_PROD_ACCESS_KEY="prodkey"
    export MINIO_PROD_SECRET_KEY="prodsecret"

    # Configuration for 'mcd' instance
    export MINIO_DEV_ENDPOINT="http://minio-dev.internal:9000"
    export MINIO_DEV_ACCESS_KEY="devkey"
    export MINIO_DEV_SECRET_KEY="devsecret"
    ```

This pattern applies similarly to other supported providers (`AWS`, `S3C`, `R2`) using their respective `FILEIO_*_ENV_PREFIXES` variables (e.g., `FILEIO_AWS_ENV_PREFIXES`).

### Code Usage

The `lzl.io.file.File` function (or direct instantiation of path classes) automatically resolves the correct configuration based on the URI scheme:

```python
from lzl.io.file import File

# Ensure environment variables are set as shown above

# Accesses the default MinIO instance (http://minio1.example.com:9000)
path_default = File("mc://my-bucket/data/file1.txt") 

# Accesses the 'mcp' MinIO instance (http://minio-prod.internal:9000)
path_prod = File("mcp://prod-bucket/config.yaml")

# Accesses the 'mcd' MinIO instance (http://minio-dev.internal:9000)
path_dev = File("mcd://dev-bucket/logs/today.log")

# File operations work transparently
if not path_prod.exists():
    path_prod.write_text("Initial config\n")

content = path_default.read_text()
print(f"Default content: {content}")

await path_dev.write_text("Log entry\n", append=True) 

# You can also get the underlying fsspec filesystem if needed
fs_prod = path_prod.get_filesystem() 
# fs_prod is an fsspec filesystem instance configured for the 'mcp' scheme
```

## Dependency Changes

None.

## Breaking Changes

- The internal structure of `lzl.io.file.configs` and `lzl.io.file.spec` has significantly changed. Direct imports or reliance on previous internal classes/methods (like `CloudFileSystemMeta`, specific provider accessors) will likely break.
- Accessing provider configurations directly via `FileIOConfig` properties (e.g., `fileio_settings.aws`, `fileio_settings.minio`) is removed. Use `fileio_settings.get_provider_config_by_scheme(scheme)` instead.
- Accessing underlying fsspec filesystems or provider-specific clients should now use the methods on the `FileLike` object (e.g., `path.get_filesystem()`, `path.get_async_filesystem()`, `path.get_s3_transfer_manager()`, `path.get_provider_config()`) instead of relying on previous accessor structures. 