
import os
import boto3
import pytest
from lzl.io import File
from lzl.io.persistence import PersistentDict

# Mock values for Minio/S3
os.environ['MINIO2_ENDPOINT'] = 'http://localhost:9001' # Local Minio Container 2
os.environ['MINIO2_ACCESS_KEY'] = 'minioadmin'
os.environ['MINIO2_SECRET_KEY'] = 'minioadmin'
os.environ['MINIO2_REGION'] = 'us-east-1'

def test_dynamic_minio_registration():
    """
    Test registering a dynamic minio protocol `mc2://`
    """
    # 1. Register Protocol
    # We use 'minio' kind, and 'MINIO2_' prefix
    File.register_protocol('mc2', 'minio', env_prefix='MINIO2_')
    
    # 2. Check Configuration
    from lzl.io.file.utils.registry import fileio_settings
    assert 'mc2' in fileio_settings._custom_providers
    config = fileio_settings._custom_providers['mc2']
    
    # Validation of loading from env
    # Note: If env vars are not actually set in the shell running this, 
    # we set them above in python. ConfigMixin.from_env_prefix should pick them up.
    
    assert config.minio_endpoint == 'http://localhost:9001'
    assert config.minio_access_key == 'minioadmin'
    
    # 3. Instantiate File
    path = File('mc2://test-bucket/hello.txt')
    
    # Verify Path Class
    assert path._prefix == 'mc2'
    # assert path.scheme == 'mc2' where did I get this from?
    
    # Verify Accessor Retrieval (which triggers FS build)
    # This might fail if the endpoint is not reachable, but we checking instantiation logic first
    try:
        accessor = path._accessor
        assert accessor is not None
        # Check if accessor definition matches
        # Accessor is a class in this architecture
        assert accessor.__name__ == 'Mc2Accessor'
        assert accessor.CloudFileSystem.__name__ == 'Mc2FileSystem'
        
        # Check fs_name
        assert accessor.CloudFileSystem.fs_name == 'mc2'
        
    except Exception as e:
        pytest.fail(f"Failed to initialize accessor: {e}")

def test_dynamic_registration_with_kwargs():
    """
    Test registering with explicit kwargs overrides
    """
    File.register_protocol(
        'mc3', 
        'minio', 
        minio_endpoint='http://localhost:9001',
        minio_access_key='test',
        minio_secret_key='test'
    )
    
    path = File('mc3://bucket/file')
    assert path._accessor.fsconfig.minio_endpoint == 'http://localhost:9001'

def test_failure_modes():
    """
    Test invalid registrations
    """
    with pytest.raises(ValueError):
        File.register_protocol('mc4', 'invalid_kind')

if __name__ == "__main__":
    test_dynamic_minio_registration()
    test_dynamic_registration_with_kwargs()
    test_failure_modes()
    print("All tests passed!")
