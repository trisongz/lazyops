#!/usr/bin/env python
"""Example script demonstrating presigned URL generation with lzl.io.File.

This script shows how to generate presigned URLs for both upload (put_object)
and download (get_object) operations.

Usage:
    python examples/presigned_url_example.py
"""

import asyncio
import sys

try:
    from lzl.io import File
    IMPORTS_AVAILABLE = True
except ImportError:
    print("Error: lzl.io.File not available. Install with: pip install -e .[file]")
    IMPORTS_AVAILABLE = False
    sys.exit(1)


def example_download_url():
    """Generate a presigned URL for downloading a file."""
    print("\n" + "="*70)
    print("Example 1: Generate Download URL (get_object)")
    print("="*70)
    
    # Create a file reference (this doesn't require the file to exist)
    file = File('s3://my-bucket/documents/report.pdf')
    
    try:
        # Generate presigned URL for downloading
        # Default client_method is 'get_object'
        download_url = file.url(expires=3600)
        
        print(f"\nFile: {file.string}")
        print(f"Operation: Download (GET)")
        print(f"Expires in: 3600 seconds (1 hour)")
        print(f"\nPresigned URL:")
        print(download_url)
        
        print("\nUsage with curl:")
        print(f'curl -O "{download_url}"')
        
        return download_url
    
    except Exception as e:
        print(f"\nError: {e}")
        print("Note: This requires valid AWS credentials to be configured")
        return None


def example_upload_url():
    """Generate a presigned URL for uploading a file."""
    print("\n" + "="*70)
    print("Example 2: Generate Upload URL (put_object)")
    print("="*70)
    
    # Create a file reference for the upload destination
    file = File('s3://my-bucket/uploads/new-file.txt')
    
    try:
        # Generate presigned URL for uploading
        upload_url = file.url(
            expires=600,  # 10 minutes
            client_method='put_object'
        )
        
        print(f"\nFile: {file.string}")
        print(f"Operation: Upload (PUT)")
        print(f"Expires in: 600 seconds (10 minutes)")
        print(f"\nPresigned URL:")
        print(upload_url)
        
        print("\nUsage with curl:")
        print(f'curl -X PUT --upload-file local-file.txt "{upload_url}"')
        
        return upload_url
    
    except Exception as e:
        print(f"\nError: {e}")
        print("Note: This requires valid AWS credentials to be configured")
        return None


def example_upload_with_metadata():
    """Generate a presigned URL for uploading with custom metadata."""
    print("\n" + "="*70)
    print("Example 3: Upload URL with Custom Metadata")
    print("="*70)
    
    file = File('s3://my-bucket/images/photo.jpg')
    
    try:
        # Generate URL with custom parameters
        upload_url = file.url(
            expires=300,  # 5 minutes
            client_method='put_object',
            Params={
                'ContentType': 'image/jpeg',
                'ServerSideEncryption': 'AES256',
                'Metadata': {
                    'uploaded-by': 'example-script',
                    'category': 'photos'
                }
            }
        )
        
        print(f"\nFile: {file.string}")
        print(f"Operation: Upload (PUT)")
        print(f"Content-Type: image/jpeg")
        print(f"Encryption: AES256")
        print(f"Expires in: 300 seconds (5 minutes)")
        print(f"\nPresigned URL:")
        print(upload_url)
        
        print("\nUsage with curl:")
        print(f'curl -X PUT --upload-file photo.jpg \\\n  -H "Content-Type: image/jpeg" \\\n  "{upload_url}"')
        
        return upload_url
    
    except Exception as e:
        print(f"\nError: {e}")
        print("Note: This requires valid AWS credentials to be configured")
        return None


async def example_async_urls():
    """Generate presigned URLs asynchronously."""
    print("\n" + "="*70)
    print("Example 4: Async Presigned URL Generation")
    print("="*70)
    
    files = [
        ('s3://my-bucket/file1.txt', 'get_object', 'Download'),
        ('s3://my-bucket/file2.txt', 'put_object', 'Upload'),
        ('s3://my-bucket/file3.txt', 'delete_object', 'Delete'),
    ]
    
    print(f"\nGenerating presigned URLs for {len(files)} operations...")
    
    try:
        tasks = []
        for path, method, operation in files:
            file = File(path)
            task = file.aurl(expires=3600, client_method=method)
            tasks.append((path, operation, task))
        
        # Execute all URL generation concurrently
        results = []
        for path, operation, task in tasks:
            try:
                url = await task
                results.append((path, operation, url))
            except Exception as e:
                results.append((path, operation, f"Error: {e}"))
        
        # Display results
        for path, operation, url in results:
            print(f"\n{operation}: {path}")
            if url.startswith("Error:"):
                print(f"  {url}")
            else:
                print(f"  URL: {url[:80]}...")
        
        return results
    
    except Exception as e:
        print(f"\nError: {e}")
        print("Note: This requires valid AWS credentials to be configured")
        return None


def example_different_providers():
    """Generate URLs for different storage providers."""
    print("\n" + "="*70)
    print("Example 5: Different Storage Providers")
    print("="*70)
    
    providers = [
        ('s3://aws-bucket/file.txt', 'AWS S3'),
        ('minio://minio-bucket/file.txt', 'MinIO'),
        ('r2://r2-bucket/file.txt', 'Cloudflare R2'),
    ]
    
    print("\nThe same API works across different S3-compatible providers:")
    
    for path, provider_name in providers:
        print(f"\n{provider_name}:")
        print(f"  Path: {path}")
        
        try:
            file = File(path)
            
            # Generate both upload and download URLs
            download_url = file.url(client_method='get_object')
            upload_url = file.url(client_method='put_object')
            
            print(f"  Download URL: {download_url[:60]}...")
            print(f"  Upload URL: {upload_url[:60]}...")
        
        except Exception as e:
            print(f"  Error: {e}")
            print(f"  Note: Requires {provider_name} credentials")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print(" Presigned URL Examples for lzl.io.File")
    print("="*70)
    print("\nThese examples demonstrate how to generate presigned URLs for:")
    print("- Downloading files (get_object)")
    print("- Uploading files (put_object)")
    print("- Custom metadata and parameters")
    print("- Async operations")
    print("- Different storage providers")
    print("\nNote: These examples require valid AWS/S3 credentials to actually")
    print("generate working URLs. The code will show what would be generated.")
    
    # Run synchronous examples
    example_download_url()
    example_upload_url()
    example_upload_with_metadata()
    example_different_providers()
    
    # Run async example
    print("\n" + "="*70)
    print("Running async example...")
    print("="*70)
    asyncio.run(example_async_urls())
    
    print("\n" + "="*70)
    print(" Examples Complete")
    print("="*70)
    print("\nKey Takeaways:")
    print("- Use client_method='put_object' for upload URLs")
    print("- Default client_method='get_object' for download URLs")
    print("- Set appropriate expiration times for security")
    print("- Use async methods (aurl) for better performance with multiple URLs")
    print("- Same API works across AWS S3, MinIO, and R2")
    print("\nFor more information, see: docs/presigned-urls-guide.md")


if __name__ == "__main__":
    if IMPORTS_AVAILABLE:
        main()
