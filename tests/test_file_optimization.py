
import os
import time
import pytest
import asyncio
from lzl.io import File

# Configuration for Minio1 (Default 'bench://')
os.environ['MINIO_BENCH_ENDPOINT'] = 'http://localhost:9000'
os.environ['MINIO_BENCH_ACCESS_KEY'] = 'minioadmin'
os.environ['MINIO_BENCH_SECRET_KEY'] = 'minioadmin'
os.environ['MINIO_BENCH_REGION'] = 'us-east-1'
os.environ['MINIO_BENCH_SECURE'] = 'False'

# Configuration for Minio2 (Secondary 'bench2://')
os.environ['MINIO_BENCH2_ENDPOINT'] = 'http://localhost:9001'
os.environ['MINIO_BENCH2_ACCESS_KEY'] = 'minioadmin'
os.environ['MINIO_BENCH2_SECRET_KEY'] = 'minioadmin'
os.environ['MINIO_BENCH2_REGION'] = 'us-east-1'
os.environ['MINIO_BENCH2_SECURE'] = 'False'

# Register protocols
try:
    File.register_protocol('bench', 'minio', env_prefix='MINIO_BENCH_')
except ValueError: pass

try:
    File.register_protocol('bench2', 'minio', env_prefix='MINIO_BENCH2_')
except ValueError: pass

BENCHMARK_FILE_SIZE = 50 * 1024 * 1024 # 50MB for noticeable difference

@pytest.fixture
def available_minio():
    """Checks if minio is available"""
    path = File("bench://test-bucket/check")
    try:
        # Simple verify
        if not path.parent.exists():
            # Create bucket logic usually manual in Minio unless configured
            # LazyOps might not auto-create bucket on exists check
            # Try to create bucket via boto3/minio client if possible
            # But here we just assume docker-compose works
            pass
        return True
    except Exception:
        return False

@pytest.fixture(scope="module", autouse=True)
def setup_buckets():
    """Ensures buckets exist using boto3"""
    import boto3
    from botocore.client import Config
    
    # Minio 1
    s3_1 = boto3.client('s3',
        endpoint_url='http://localhost:9000',
        aws_access_key_id='minioadmin',
        aws_secret_access_key='minioadmin',
        region_name='us-east-1',
        config=Config(signature_version='s3v4')
    )
    try:
        s3_1.create_bucket(Bucket='test-bucket')
    except Exception as e:
        # Ignore if exists
        pass

    # Minio 2
    s3_2 = boto3.client('s3',
        endpoint_url='http://localhost:9001',
        aws_access_key_id='minioadmin',
        aws_secret_access_key='minioadmin',
        region_name='us-east-1',
        config=Config(signature_version='s3v4')
    )
    try:
        s3_2.create_bucket(Bucket='test-bucket-2')
    except Exception as e:
        pass

@pytest.fixture
def benchmark_file(setup_buckets):
    """Creates a temporary 50MB file in Minio/S3 for testing using boto3"""
    import boto3
    from botocore.client import Config
    
    protocol = 'bench'
    filename = f"bench-src-{int(time.time())}.bin"
    # Ensure we use the correct path structure
    # bench:// maps to Minio1
    
    # Create random data
    data = os.urandom(BENCHMARK_FILE_SIZE)
    
    # Upload via boto3 to avoid lzl.io/s3transfer issues during setup
    s3 = boto3.client('s3',
        endpoint_url='http://localhost:9000',
        aws_access_key_id='minioadmin',
        aws_secret_access_key='minioadmin',
        region_name='us-east-1',
        config=Config(signature_version='s3v4')
    )
    
    s3.put_object(Bucket='test-bucket', Key=filename, Body=data)
    
    path = File(f"{protocol}://test-bucket/{filename}")
    
    yield path
    
    # Cleanup
    try:
        path.delete()
    except:
        pass

def test_optimized_copy_intra_provider(benchmark_file):
    """
    Test copy within same provider (Should be fast/server-side)
    Minio1 -> Minio1
    """
    src = benchmark_file
    dst = File(f"{src.parent}/dst-intra.bin")
    
    start_time = time.time()
    src.copy_to(dst, overwrite=True)
    duration = time.time() - start_time
    
    print(f"\n[Intra-Provider] Time taken for 50MB copy: {duration:.4f}s")
    print(f"Speed: {BENCHMARK_FILE_SIZE / 1024 / 1024 / duration:.2f} MB/s")
    
    assert dst.exists()
    assert dst.size() == BENCHMARK_FILE_SIZE
    
    # Verify optimization (heuristic: excessively fast for local loopback)
    # 50MB transfer locally takes ~0.5-1s? Server side copy should be < 0.2s
    if duration < 0.5:
        print(">> Optimization Likely Active (Fast Transfer)")
    
    dst.delete()

def test_unoptimized_copy_inter_provider(benchmark_file):
    """
    Test copy between different providers (Must stream)
    Minio1 -> Minio2
    """
    src = benchmark_file
    dst = File(f"bench2://test-bucket-2/dst-inter.bin")
    
    start_time = time.time()
    src.copy_to(dst, overwrite=True)
    duration = time.time() - start_time
    
    print(f"\n[Inter-Provider] Time taken for 50MB copy: {duration:.4f}s")
    print(f"Speed: {BENCHMARK_FILE_SIZE / 1024 / 1024 / duration:.2f} MB/s")
    
    assert dst.exists()
    assert dst.size() == BENCHMARK_FILE_SIZE
    dst.delete()

@pytest.mark.asyncio
async def test_async_optimized_copy(benchmark_file):
    """
    Test async copy intra-provider
    """
    src = benchmark_file
    dst = File(f"{src.parent}/dst-async.bin")
    
    start_time = time.time()
    await src.acopy_to(dst, overwrite=True)
    duration = time.time() - start_time
    
    print(f"\n[Async Intra] Time taken for 50MB copy: {duration:.4f}s")
    
    assert await dst.aexists()
    await dst.adelete()

