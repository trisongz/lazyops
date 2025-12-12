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

def test_minio_file_ops(random_bucket):
    """
    Test MinIO file operations using mc:// scheme.
    """
    async def _test():
        bucket_path = File(f"mc://{random_bucket}")
        # Force create bucket
        if not await bucket_path.aexists():
            await bucket_path.amkdir(parents=True, exist_ok=True)


        file_path = bucket_path / f"test-{uuid.uuid4().hex}.txt"
        content = "MinIO Content"
        
        # Write
        await file_path.awrite_text(content)
        assert await file_path.aexists()
        
        # Read
        read_content = await file_path.aread_text()
        assert read_content == content
        
        # Delete
        await file_path.aunlink()
        assert not await file_path.aexists()

    import anyio
    anyio.run(_test)

def test_multiple_minio_configs(minio_config):
    """
    Test registering multiple MinIO configurations.
    """
    async def _test():
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

    import anyio
    anyio.run(_test)
