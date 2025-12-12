
import pytest
import uuid
import os
from lzl.io import File
from lzl.io.file.spec.providers.main import MinioFileSystem

@pytest.mark.asyncio
async def test_mkdir_creates_bucket(minio_config):
    """
    Verify that amkdir creates the bucket if it doesn't exist.
    """
    bucket_name = f"test-bucket-create-{uuid.uuid4().hex}"
    # Use mc:// prefix as per environment setup
    # Path: mc://new-bucket/
    # Or mc://new-bucket/new-dir/
    
    # CASE 1: Create bucket via root path
    root_path = File(f"mc://{bucket_name}/")
    print(f"DEBUG: Root path: {root_path}")
    
    # Assert bucket does not exist
    exists = await root_path.aexists()
    # aexists on a non-existent bucket root might return False
    assert not exists, "Bucket should not exist yet"
    
    # Try to create bucket
    print("DEBUG: Calling amkdir on root")
    await root_path.amkdir()
    
    # Verify existence
    exists_after = await root_path.aexists()
    assert exists_after, "Bucket should exist after amkdir"
    
    # CASE 2: Create bucket via subdirectory path
    bucket_name_2 = f"test-bucket-create-sub-{uuid.uuid4().hex}"
    sub_path = File(f"mc://{bucket_name_2}/subdir/")
    
    # Try to create bucket + subdir
    print(f"DEBUG: Calling amkdir on sub_path: {sub_path}")
    await sub_path.amkdir(parents=True)
    
    # Verify bucket exists
    root_path_2 = File(f"mc://{bucket_name_2}/")
    assert await root_path_2.aexists(), "Bucket 2 should exist"

