import pytest
import os
import uuid
import asyncio
from lzl.io import File


def test_local_file_ops(tmp_path):
    """
    Test basic local file operations.
    """
    async def _test():
        test_file = File(tmp_path) / "test.txt"
        content = "Hello World"
        
        # Write
        await test_file.awrite_text(content)
        assert test_file.exists()
        
        # Read
        read_content = await test_file.aread_text()
        assert read_content == content
        
        # Delete
        test_file.unlink()
        assert not test_file.exists()

    import anyio
    anyio.run(_test)

@pytest.mark.asyncio
async def test_minio_file_ops(random_bucket, minio_config):
    """
    Test MinIO file operations.
    """
    from lzl.io.file.spec.providers.main import MinioFileSystem
    
    # Verify we are on a fresh loop
    import asyncio
    print(f"DEBUG: test_minio_file_ops loop: {id(asyncio.get_running_loop())}")
    
    bucket_name = random_bucket
    filename = f"test-file-{uuid.uuid4().hex}.txt"
    file_path = File(f"mc://{bucket_name}/{filename}")
    
    data = "Hello MinIO"
    await file_path.awrite_text(data)
    
    # Verify write
    assert await file_path.aexists()
    
    # Verify read
    read_data = await file_path.aread_text()
    assert read_data == data
    
    # Verify delete
    await file_path.aunlink()
    assert not await file_path.aexists()

async def test_multiple_minio_configs(minio_config):
    """
    Test registering multiple MinIO configurations.
    """
    protocol = "mc2"
    
    region = minio_config["region_name"]
    if region == "us-east-1":
        region = ""

    File.register_protocol(
        protocol=protocol,
        kind="minio",
        minio_endpoint=minio_config["endpoint_url"],
        minio_access_key=minio_config["aws_access_key_id"],
        minio_secret_key=minio_config["aws_secret_access_key"],
        minio_region=region,
        minio_secure=False,
        env_prefix="MINIO2",
    )
    
    # Now use mc2://
    bucket_name = f"test-bucket-2-{uuid.uuid4().hex}"
    bucket_path = File(f"{protocol}://{bucket_name}")
    
    # Force create bucket
    if not await bucket_path.aexists():
        await bucket_path.amkdir(parents=True, exist_ok=True)

        
    file_path = bucket_path / "test2.txt"
    content = "Multi Config Content"
    
    await file_path.awrite_text(content)
    assert await file_path.aexists()
    assert await file_path.aread_text() == content
    
    await file_path.aunlink()
