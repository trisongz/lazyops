# Tests for FileIO multi-provider instance support

import os
import pytest
from unittest.mock import patch, MagicMock

# Assuming necessary imports from lzl.io.file can be made
from lzl.io.file import File
from lzl.io.file.configs.main import FileIOConfig
from lzl.io.file.configs.providers import MinioConfig, S3CompatConfig
from lzl.io.file.spec.cloudfs import cloud_file_manager
from lzl.io.file.spec.main import populate_scheme_map, SCHEME_TO_PATH_CLASS
from lzl.io.file.spec.paths.minio import FileMinioPath
from lzl.io.file.spec.paths.s3c import FileS3CPath

# --- Fixtures ---

@pytest.fixture(autouse=True)
def clear_environment_and_caches(monkeypatch):
    """Clears relevant env vars and internal caches before each test."""
    # Clear potentially conflicting env vars
    vars_to_clear = [
        'MINIO_ENDPOINT', 'MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY',
        'MINIO_1_ENDPOINT', 'MINIO_1_ACCESS_KEY', 'MINIO_1_SECRET_KEY',
        'MINIO_2_ENDPOINT', 'MINIO_2_ACCESS_KEY', 'MINIO_2_SECRET_KEY',
        'S3C_ENDPOINT', 'S3C_ACCESS_KEY', 'S3C_SECRET_KEY',
        'FILEIO_MINIO_ENV_PREFIXES', 'FILEIO_S3C_ENV_PREFIXES',
    ]
    for var in vars_to_clear:
        monkeypatch.delenv(var, raising=False)
    
    # Reset FileIOConfig singleton/cache if necessary (implementation specific)
    # This might involve reloading settings or clearing cached instances.
    # For simplicity, we assume creating a new FileIOConfig instance works, 
    # but a dedicated reset function might be better.
    # Example: FileIOConfig.reset_instance()
    
    # Reset CloudFileManager instances
    cloud_file_manager._instances = {}
    cloud_file_manager._settings = None
    cloud_file_manager._creating = set()

    # Reset scheme map population flag
    global _SCHEME_MAP_POPULATED
    _SCHEME_MAP_POPULATED = False
    # You might need to reset the SCHEME_TO_PATH_CLASS dict itself if it persists
    # global SCHEME_TO_PATH_CLASS 
    # SCHEME_TO_PATH_CLASS = { ... base definition ... }
    
    yield # Run the test
    
    # Cleanup after test (optional, autouse fixture handles setup mostly)
    cloud_file_manager._instances = {}
    cloud_file_manager._settings = None
    _SCHEME_MAP_POPULATED = False


@pytest.fixture
def mock_minio_configs(monkeypatch):
    """Sets up environment variables for default and two prefixed MinIO configs."""
    # Default MinIO
    monkeypatch.setenv('MINIO_ENDPOINT', 'http://default.minio:9000')
    monkeypatch.setenv('MINIO_ACCESS_KEY', 'default_key')
    monkeypatch.setenv('MINIO_SECRET_KEY', 'default_secret')

    # Prefixed MinIO instances
    monkeypatch.setenv('FILEIO_MINIO_ENV_PREFIXES', 'MINIO_1_:mc1,MINIO_2_:mc2')
    monkeypatch.setenv('MINIO_1_ENDPOINT', 'http://minio1.example.com:9001')
    monkeypatch.setenv('MINIO_1_ACCESS_KEY', 'key1')
    monkeypatch.setenv('MINIO_1_SECRET_KEY', 'secret1')
    monkeypatch.setenv('MINIO_2_ENDPOINT', 'http://minio2.internal:9000')
    monkeypatch.setenv('MINIO_2_ACCESS_KEY', 'key2')
    monkeypatch.setenv('MINIO_2_SECRET_KEY', 'secret2')


# --- Test Cases ---

def test_config_loading_from_env(mock_minio_configs):
    """Verify FileIOConfig loads default and prefixed configs from environment."""
    settings = FileIOConfig() # Should trigger loading from env

    # Check default Minio config ('mc' scheme)
    mc_config = settings.get_provider_config_by_scheme('mc')
    assert isinstance(mc_config, MinioConfig)
    assert mc_config.minio_endpoint == 'http://default.minio:9000'
    assert mc_config.minio_access_key == 'default_key'
    assert mc_config.minio_secret_key == 'default_secret'
    assert mc_config._uri_scheme == 'mc'
    assert mc_config._env_prefix == 'MINIO_'

    # Check first prefixed Minio config ('mc1' scheme)
    mc1_config = settings.get_provider_config_by_scheme('mc1')
    assert isinstance(mc1_config, MinioConfig)
    assert mc1_config.minio_endpoint == 'http://minio1.example.com:9001'
    assert mc1_config.minio_access_key == 'key1'
    assert mc1_config.minio_secret_key == 'secret1'
    assert mc1_config._uri_scheme == 'mc1'
    assert mc1_config._env_prefix == 'MINIO_1_'

    # Check second prefixed Minio config ('mc2' scheme)
    mc2_config = settings.get_provider_config_by_scheme('mc2')
    assert isinstance(mc2_config, MinioConfig)
    assert mc2_config.minio_endpoint == 'http://minio2.internal:9000'
    assert mc2_config.minio_access_key == 'key2'
    assert mc2_config.minio_secret_key == 'secret2'
    assert mc2_config._uri_scheme == 'mc2'
    assert mc2_config._env_prefix == 'MINIO_2_'

    # Check that scheme map was populated correctly
    populate_scheme_map() # Ensure it runs if not already
    assert SCHEME_TO_PATH_CLASS.get('mc') is FileMinioPath
    assert SCHEME_TO_PATH_CLASS.get('mc1') is FileMinioPath
    assert SCHEME_TO_PATH_CLASS.get('mc2') is FileMinioPath

# More tests needed for path resolution and file operations using mocks

# Example structure for mocking file operations
@patch('lzl.io.file.spec.cloudfs.CloudFileManager._create_bundle')
def test_path_resolution_and_mocked_ops(mock_create_bundle, mock_minio_configs):
    """Test that paths resolve to correct classes and ops use the right mock FS."""
    
    # --- Setup Mocks ---
    # Mock file systems for each scheme
    mock_fs_mc = MagicMock()
    mock_fs_mc1 = MagicMock()
    mock_fs_mc2 = MagicMock()

    # Configure mock_create_bundle to provide mocks when called for specific schemes
    def side_effect_create_bundle(scheme):
        bundle = None
        if scheme == 'mc':
            bundle = cloud_file_manager.FilesystemBundle(
                scheme='mc', fs=mock_fs_mc, fsa=MagicMock() # Mock async too if needed
            )
        elif scheme == 'mc1':
            bundle = cloud_file_manager.FilesystemBundle(
                scheme='mc1', fs=mock_fs_mc1, fsa=MagicMock()
            )
        elif scheme == 'mc2':
            bundle = cloud_file_manager.FilesystemBundle(
                scheme='mc2', fs=mock_fs_mc2, fsa=MagicMock()
            )
        
        if bundle:
             cloud_file_manager._instances[scheme] = bundle
        else:
             cloud_file_manager._instances[scheme] = None # Simulate config not found
        # No return value needed as it modifies _instances directly

    mock_create_bundle.side_effect = side_effect_create_bundle

    # --- Test Path Resolution and Operations ---
    settings = FileIOConfig() # Load configs
    populate_scheme_map() # Populate scheme map

    # Test default scheme
    path_mc = File("mc://bucketA/file1.txt")
    assert isinstance(path_mc, FileMinioPath)
    assert path_mc.scheme == 'mc'
    path_mc.write_text("content_mc")
    mock_fs_mc.open.assert_called_once_with('bucketA/file1.txt', mode='w', encoding='utf-8')
    # Check call args on the file handle mock returned by open

    # Test first custom scheme
    path_mc1 = File("mc1://bucketB/file2.yaml")
    assert isinstance(path_mc1, FileMinioPath)
    assert path_mc1.scheme == 'mc1'
    path_mc1.read_text()
    mock_fs_mc1.open.assert_called_once_with('bucketB/file2.yaml', mode='r', encoding='utf-8')

    # Test second custom scheme
    path_mc2 = File("mc2://bucketC/data.json")
    assert isinstance(path_mc2, FileMinioPath)
    assert path_mc2.scheme == 'mc2'
    path_mc2.exists()
    mock_fs_mc2.exists.assert_called_once_with('bucketC/data.json')

    # Verify create_bundle was called for each scheme when needed
    assert mock_create_bundle.call_count >= 3 # Called at least once per scheme
    mock_create_bundle.assert_any_call('mc')
    mock_create_bundle.assert_any_call('mc1')
    mock_create_bundle.assert_any_call('mc2')


# TODO: Add tests for:
# - Other providers (S3C, R2, AWS, GCP when added)
# - Edge cases in path parsing
# - Async file operations (mocking async methods)
# - Error handling (e.g., config not found, invalid scheme)
# - Interaction with s3 transfer manager (if mocking allows) 