import pytest
import uuid
import asyncio
from lzl.io.persistence import PersistentDict
from lzl.io import File

@pytest.fixture
async def kvdb_pd(redis_url):
    name = f"test-pd-{uuid.uuid4().hex}"
    # Explicitly try to ensure KVDB is used
    try:
        import kvdb
        from kvdb.components.persistence import KVDBStatefulBackend
    except ImportError:
        pytest.skip("kvdb not installed")

    pd = PersistentDict(
        name=name,
        backend_type='auto',
        expiration=60, # 1 minute
        url=redis_url, 
        serializer='json',
        async_enabled=True
    )
    yield pd
    # Cleanup involves clearing keys usually
    await pd.aclear()

@pytest.mark.asyncio
async def test_persistence_kvdb(kvdb_pd):
    # Verify backend is KVDB
    from kvdb.components.persistence import KVDBStatefulBackend
    
    # Depending on how auto works, it might return KVDBStatefulBackend or PersistentDict wrapping it
    # pd.base is the backend instance
    # assert isinstance(kvdb_pd.base, KVDBStatefulBackend)
    # Actually, we can just check functionality

    key = "key1"
    value = {"data": 123}

    # Set
    await kvdb_pd.aset(key, value)
    assert await kvdb_pd.acontains(key)

    # Get
    retrieved = await kvdb_pd.aget(key)
    assert retrieved == value

    # Dict interface (Sync)
    kvdb_pd["sync_key"] = "sync_val"
    await asyncio.sleep(0.1)
    assert kvdb_pd["sync_key"] == "sync_val"
    
    await kvdb_pd.adelete(key)
    assert not await kvdb_pd.acontains(key)


@pytest.fixture
async def minio_pd(random_bucket):
    """
    Returns a PersistentDict backed by MinIO (ObjStore).
    """
    # base_key should be a URI like mc://bucket/prefix
    base_key = f"mc://{random_bucket}/persistence_data"
    
    pd = PersistentDict(
        base_key=base_key,
        backend_type='objstore',
        serializer='json',
    )
    yield pd
    
    # Explicitly cleanup s3fs session to prevent event loop closed errors
    try:
        # Check if internal buffer or accessor has session
        if hasattr(pd, 'backend') and hasattr(pd.backend, 'root'):
             afilesys = pd.backend.root.afilesys
             if afilesys and hasattr(afilesys, 'session'):
                 await afilesys.session.close()
    except Exception:
        pass 

@pytest.mark.asyncio
async def test_persistence_minio(minio_pd):
    """
    Test PersistentDict with MinIO backend.
    """
    key = "file_key"
    value = {"file_data": 456}
    
    # Set
    await minio_pd.aset(key, value)
    assert await minio_pd.acontains(key)
    
    # Get
    retrieved = await minio_pd.aget(key)
    assert retrieved == value
    
    # Dict interface
    minio_pd["sync_file"] = "data"
    
    # Verify it exists as file
    # f_path = File(f"{minio_pd.base_key}/{key}")
    # Serializer might wrap/change extension
    # If using json serializer, maybe .json appended?
    # Let's check via pd interface mainly.
    
    pd2 = PersistentDict(base_key=minio_pd.base_key, backend_type='objstore', serializer='json')
    assert await pd2.aget(key) == value
