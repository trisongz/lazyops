import pytest
import os
import time
import httpx
# Monkeypatch pydantic for aiokeydb compatibility
try:
    from pydantic import networks
    if not hasattr(networks, 'Url'):
        networks.Url = networks.AnyUrl
    if not hasattr(networks, 'MultiHostUrl'):
        networks.MultiHostUrl = networks.AnyUrl
except ImportError:
    pass

try:
    import redis.connection
    if not hasattr(redis.connection, '_RESP2Parser'):
        redis.connection._RESP2Parser = redis.connection.PythonParser
    if not hasattr(redis.connection, 'AbstractConnection'):
        redis.connection.AbstractConnection = redis.connection.Connection
    
    try:
        import redis.asyncio.connection
        if not hasattr(redis.asyncio.connection, 'AbstractConnection'):
            # In some versions, it might not be exposed, assume Connection is the base or alias it
            if hasattr(redis.asyncio.connection, 'Connection'):
                redis.asyncio.connection.AbstractConnection = redis.asyncio.connection.Connection
        
        if not hasattr(redis.asyncio.connection, '_AsyncRESP2Parser'):
             if hasattr(redis.asyncio.connection, 'PythonParser'):
                redis.asyncio.connection._AsyncRESP2Parser = redis.asyncio.connection.PythonParser

    except ImportError:
        pass
except ImportError:
    pass

from typing import Generator
from lzl.load import lazy_load

@pytest.fixture(scope="session")
def minio_config():
    """
    Returns the MinIO configuration from environment variables.
    """
    return {
        "endpoint_url": os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
        "aws_access_key_id": os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        "aws_secret_access_key": os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        "region_name": None,
    }

@pytest.fixture(scope="session")
def redis_url():
    """
    Returns the Redis URL from environment variables.
    """
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")

@pytest.fixture(scope="session")
def check_services(minio_config, redis_url):
    """
    Verifies that the required services are up and running.
    """
    # Check MinIO
    try:
        # Simple health check for MinIO
        health_url = f"{minio_config['endpoint_url']}/minio/health/live"
        response = httpx.get(health_url, timeout=5)
        if response.status_code != 200:
            pytest.skip(f"MinIO service not healthy at {health_url}: {response.status_code}")
    except Exception as e:
        pytest.skip(f"MinIO service not accessible: {e}")

    # Check Redis
    try:
        # We'll use the lzl.io.persistence backend to check redis or just pure redis client if available
        # But for now, let's assume if env var is set, it's there. 
        # Ideally we'd ping it.
        pass
    except Exception as e:
        pytest.skip(f"Redis service not accessible: {e}")

@pytest.fixture(autouse=True)
def setup_test_env(check_services):
    """
    Ensures environment is ready for each test.
    """

    from lzl.io.file.spec.providers.main import MinioFileSystem, ProviderManager
    
    # Clear cached accessors to force reload (and patch application)
    ProviderManager.accessors.clear()

    
    # Try to close existing session if possible to prevent loop mismatch
    if MinioFileSystem.fs and hasattr(MinioFileSystem.fs, 'session'):
        try:
            # We can't await here as it's sync fixture, but s3fs session might have sync close?
            # aiobotocore session close is async.
            # If we just clear the cache, the session remains open but detached?
            # The loop closure error happens when something TRIES to use it.
            # If we clear it, nothing should use it.
            pass
        except Exception:
            pass

    try:
        import s3fs
        import fsspec
        # Clear internal fsspec/s3fs instance caches to force new loop binding
        s3fs.S3FileSystem.clear_instance_cache()
        fsspec.clear_instance_cache()
    except (ImportError, AttributeError):
        pass

    # Reset the filesystem state to ensure a fresh event loop binding
    # This prevents 'Event loop is closed' errors when running multiple async tests
    MinioFileSystem.fs = None
    MinioFileSystem.fsa = None
    MinioFileSystem.boto = None

# Moved from test_io_file.py to share with test_persistence.py
import uuid
from lzl.io import File

pytest_plugins = ["pytest_asyncio"]

@pytest.fixture(scope="function")
def random_bucket(minio_config):
    """
    Creates a random bucket for testing and cleans it up after.
    Uses boto3 to avoid asyncio loop issues in fixtures.
    """
    import boto3
    from botocore.client import Config
    
    bucket_name = f"test-bucket-{uuid.uuid4().hex}"
    
    # Configure File.settings with MinIO creds (still needed for the test to work)
    region = minio_config.get("region_name")
    if not region or region == "us-east-1":
        region = ""

    if hasattr(File.settings, 'update_config'):
        File.settings.update_config(
            minio_endpoint=minio_config["endpoint_url"],
            minio_access_key=minio_config["aws_access_key_id"],
            minio_secret_key=minio_config["aws_secret_access_key"],
            minio_region=region,
            minio_secure=False,
        )
    elif hasattr(File.settings, 'minio'):
        File.settings.minio.endpoint_url = minio_config["endpoint_url"]
        File.settings.minio.aws_access_key_id = minio_config["aws_access_key_id"]
        File.settings.minio.aws_secret_access_key = minio_config["aws_secret_access_key"]
        File.settings.minio.region_name = region
        File.settings.minio.secure = False
        
    if hasattr(File.settings, 'update_fs'):
        File.settings.update_fs()
    
    # Use boto3 for bucket creation
    s3_client = boto3.client(
        's3',
        endpoint_url=minio_config["endpoint_url"],
        aws_access_key_id=minio_config["aws_access_key_id"],
        aws_secret_access_key=minio_config["aws_secret_access_key"],
        config=Config(signature_version='s3v4'),
        region_name=region or 'us-east-1'
    )
    
    try:
        s3_client.create_bucket(Bucket=bucket_name)
    except Exception as e:
        # Ignore if exists (rare with uuid)
        print(f"Boto3 create bucket warning: {e}")

    yield bucket_name
    
    # Cleanup
    try:
        # Must rely on force delete or recursive delete
        # boto3 doesn't have recursive delete easily, but we can list objects
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in response:
            for obj in response['Contents']:
                s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])
        s3_client.delete_bucket(Bucket=bucket_name)
    except Exception as e:
        print(f"Boto3 cleanup error: {e}")

