# Presigned URLs Guide for lzl.io.File

This guide explains how to generate presigned URLs for cloud storage operations, including upload (put_object) and download (get_object) operations.

## Overview

The `lzl.io.File` module supports generating presigned URLs for S3-compatible storage systems (AWS S3, MinIO, Cloudflare R2, etc.) through the `url()` and `aurl()` methods. These methods leverage the underlying `s3fs` library and boto3 client to generate secure, temporary URLs.

## Supported Operations

Presigned URLs can be generated for various S3 operations:

| Client Method | Purpose | Use Case |
|---------------|---------|----------|
| `get_object` | Download/Read | Default - retrieve file contents via HTTP GET |
| `put_object` | Upload/Write | Upload file contents via HTTP PUT |
| `delete_object` | Delete | Remove a file via HTTP DELETE |
| `head_object` | Metadata | Retrieve file metadata via HTTP HEAD |

## Basic Usage

### Download URL (get_object)

```python
from lzl.io import File

# Create a file reference to S3 object
file = File('s3://my-bucket/path/to/file.txt')

# Generate presigned URL for downloading (default)
download_url = file.url(expires=3600)  # Valid for 1 hour

# Or explicitly specify get_object
download_url = file.url(expires=3600, client_method='get_object')

print(f"Download URL: {download_url}")
# URL can be used with curl, wget, or any HTTP client
# curl -O "{download_url}"
```

### Upload URL (put_object)

```python
from lzl.io import File

# Create a file reference for upload destination
file = File('s3://my-bucket/path/to/new-file.txt')

# Generate presigned URL for uploading
upload_url = file.url(expires=3600, client_method='put_object')

print(f"Upload URL: {upload_url}")
# URL can be used to upload via HTTP PUT
# curl -X PUT --upload-file local-file.txt "{upload_url}"
```

### Async Usage

```python
from lzl.io import File
import asyncio

async def generate_urls():
    file = File('s3://my-bucket/path/to/file.txt')
    
    # Async download URL
    download_url = await file.aurl(expires=3600)
    
    # Async upload URL
    upload_url = await file.aurl(expires=3600, client_method='put_object')
    
    return download_url, upload_url

# Run async function
download_url, upload_url = asyncio.run(generate_urls())
```

## Advanced Usage

### Custom Expiration

```python
from lzl.io import File

file = File('s3://my-bucket/file.txt')

# Short-lived URL (5 minutes)
short_url = file.url(expires=300, client_method='put_object')

# Long-lived URL (12 hours)
long_url = file.url(expires=43200, client_method='put_object')
```

### Additional Parameters

The `url()` method accepts additional keyword arguments that are passed to the boto3 `generate_presigned_url` method:

```python
from lzl.io import File

file = File('s3://my-bucket/file.txt')

# Generate URL with custom request parameters
upload_url = file.url(
    expires=3600,
    client_method='put_object',
    Params={
        'ContentType': 'application/json',
        'ServerSideEncryption': 'AES256',
    }
)
```

### Different Storage Providers

The same API works across different S3-compatible providers:

```python
from lzl.io import File

# AWS S3
aws_file = File('s3://my-bucket/file.txt')
aws_url = aws_file.url(client_method='put_object')

# MinIO
minio_file = File('minio://my-bucket/file.txt')
minio_url = minio_file.url(client_method='put_object')

# Cloudflare R2
r2_file = File('r2://my-bucket/file.txt')
r2_url = r2_file.url(client_method='put_object')
```

## Common Use Cases

### 1. Direct Browser Upload

Generate an upload URL and use it in a web application:

```python
from lzl.io import File
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/upload-url/<filename>')
def get_upload_url(filename):
    # Generate presigned URL for upload
    file = File(f's3://uploads-bucket/{filename}')
    upload_url = file.url(
        expires=300,  # 5 minutes
        client_method='put_object',
        Params={
            'ContentType': 'application/octet-stream',
        }
    )
    
    return jsonify({
        'upload_url': upload_url,
        'method': 'PUT',
        'expires_in': 300
    })
```

JavaScript client:
```javascript
async function uploadFile(file) {
    // Get presigned URL from backend
    const response = await fetch(`/api/upload-url/${file.name}`);
    const { upload_url } = await response.json();
    
    // Upload directly to S3
    await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: {
            'Content-Type': 'application/octet-stream'
        }
    });
}
```

### 2. Secure Download Links

Generate temporary download links for users:

```python
from lzl.io import File

def generate_download_link(file_path, user_id):
    """Generate a secure, temporary download link."""
    file = File(f's3://secure-files/{file_path}')
    
    # Generate URL that expires in 15 minutes
    download_url = file.url(
        expires=900,
        client_method='get_object'
    )
    
    # Log access for audit
    log_file_access(user_id, file_path, download_url)
    
    return download_url
```

### 3. Batch Operations

Generate multiple URLs efficiently:

```python
from lzl.io import File
import asyncio

async def generate_batch_urls(file_paths, operation='get_object'):
    """Generate presigned URLs for multiple files."""
    tasks = []
    
    for path in file_paths:
        file = File(path)
        task = file.aurl(expires=3600, client_method=operation)
        tasks.append(task)
    
    urls = await asyncio.gather(*tasks)
    return dict(zip(file_paths, urls))

# Usage
file_paths = [
    's3://my-bucket/file1.txt',
    's3://my-bucket/file2.txt',
    's3://my-bucket/file3.txt',
]

urls = asyncio.run(generate_batch_urls(file_paths, operation='put_object'))
```

### 4. Upload with Validation

Generate upload URL with content type and size restrictions:

```python
from lzl.io import File

def generate_validated_upload_url(filename, content_type, max_size_mb=10):
    """Generate upload URL with validation."""
    file = File(f's3://uploads/{filename}')
    
    # Generate URL with constraints
    upload_url = file.url(
        expires=600,  # 10 minutes
        client_method='put_object',
        Params={
            'ContentType': content_type,
            'ContentLengthRange': [0, max_size_mb * 1024 * 1024],
        }
    )
    
    return upload_url

# Example: Allow only images up to 5MB
image_upload_url = generate_validated_upload_url(
    'user-avatar.jpg',
    'image/jpeg',
    max_size_mb=5
)
```

## Implementation Details

### How It Works

1. The `url()` method delegates to the underlying S3 filesystem accessor
2. The accessor uses `s3fs.S3FileSystem.url()` method
3. `s3fs` internally calls boto3's `generate_presigned_url()`
4. The boto3 client signs the request with AWS credentials
5. A time-limited URL is returned that includes the signature

### Security Considerations

1. **Expiration Time**: Always set appropriate expiration times. Shorter is more secure.
2. **HTTPS**: Presigned URLs support HTTPS by default
3. **Credentials**: The boto3 client must have appropriate permissions
4. **URL Sharing**: URLs grant temporary access - share carefully
5. **Logging**: Consider logging URL generation for audit trails

### Provider-Specific Notes

**AWS S3:**
- Standard boto3 client methods supported
- Signature version 4 (SigV4) used by default
- Region-specific endpoints

**MinIO:**
- Compatible with S3 API
- Same client methods supported
- Custom endpoint configuration required

**Cloudflare R2:**
- S3-compatible API
- Supports standard presigned URLs
- No egress charges for presigned URLs

## Troubleshooting

### Common Issues

**Issue: "NoCredentialsError"**
```
Solution: Ensure AWS credentials are configured via:
- Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
- ~/.aws/credentials file
- IAM role (for EC2/Lambda)
```

**Issue: "SignatureDoesNotMatch"**
```
Solution: Check that:
- System clock is synchronized
- Credentials are correct
- Region matches the bucket region
```

**Issue: "URL expired"**
```
Solution: Generate a new URL with appropriate expiration time
```

### Debugging

Enable debug logging to troubleshoot issues:

```python
import logging

# Enable debug logging for boto3
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('boto3').setLevel(logging.DEBUG)
logging.getLogger('botocore').setLevel(logging.DEBUG)

# Generate URL
file = File('s3://my-bucket/file.txt')
url = file.url(client_method='put_object')
```

## Testing

Test presigned URL generation without actual S3 credentials:

```python
import pytest
from lzl.io import File

def test_url_method_exists():
    """Test that url method is available."""
    file = File('s3://test-bucket/test-file.txt')
    assert hasattr(file, 'url')
    assert hasattr(file, 'aurl')

def test_url_signature():
    """Test url method signature."""
    import inspect
    from lzl.io.file.spec.path import CloudFileSystemPath
    
    # Check method accepts client_method parameter
    sig = inspect.signature(CloudFileSystemPath.url)
    # Note: Due to overload decorator, check via typing
```

## See Also

- [Performance Guide](./file-performance-guide.md) - For large file operations
- [Cloud Storage Guide](./cloud-storage.md) - General cloud storage usage
- [AWS S3 Presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html)
- [boto3 generate_presigned_url](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.generate_presigned_url)

## API Reference

### File.url()

```python
def url(
    self, 
    expires: int = 3600, 
    client_method: str = 'get_object', 
    **kwargs
) -> str
```

**Parameters:**
- `expires` (int): Number of seconds until URL expires. Default: 3600 (1 hour)
- `client_method` (str): S3 client method to generate URL for. Default: 'get_object'
  - Common values: 'get_object', 'put_object', 'delete_object', 'head_object'
- `**kwargs`: Additional parameters passed to boto3's `generate_presigned_url()`

**Returns:**
- `str`: Presigned URL for the specified operation

### File.aurl()

```python
async def aurl(
    self, 
    expires: int = 3600, 
    client_method: str = 'get_object', 
    **kwargs
) -> str
```

Async version of `url()`. Same parameters and return type.
