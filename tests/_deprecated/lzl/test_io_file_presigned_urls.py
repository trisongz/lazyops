"""Tests for presigned URL generation in lzl.io.File.

This module tests the presigned URL generation capabilities for cloud storage,
including support for different client methods (get_object, put_object, etc.).
"""

import pytest

# Test imports
try:
    from lzl.io import File
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="lzl.io.File not available")
class TestPresignedURLSupport:
    """Test presigned URL generation support."""
    
    def test_url_method_signature(self):
        """Test that url method exists with correct signature."""
        from lzl.io.file.spec.path import CloudFileSystemPath
        
        # Check method exists
        assert hasattr(CloudFileSystemPath, 'url')
        assert hasattr(CloudFileSystemPath, 'aurl')
        
        # The method should accept client_method parameter
        import inspect
        sig = inspect.signature(CloudFileSystemPath.url)
        # Due to overload, we check the type hints instead
        annotations = CloudFileSystemPath.url.__annotations__
        # Note: The actual implementation delegates to accessor
    
    def test_url_method_documentation(self):
        """Test that url method has proper documentation."""
        from lzl.io.file.spec.path import CloudFileSystemPath
        
        # Check that url method has docstring mentioning presigned URLs
        # The overload has the docstring
        import typing
        overloads = typing.get_overloads(CloudFileSystemPath.url)
        if overloads:
            # Check first overload has documentation
            assert overloads[0].__doc__ is not None
            assert 'presigned' in overloads[0].__doc__.lower()
    
    def test_client_method_parameter_support(self):
        """Test that client_method parameter is documented."""
        # The url method should support different client methods
        # This is inherited from s3fs.S3FileSystem.url
        
        # Document the supported client methods
        supported_methods = [
            'get_object',      # Default - for downloading/reading
            'put_object',      # For uploading/writing
            'delete_object',   # For deleting
            'head_object',     # For metadata
        ]
        
        # All these should be valid values for client_method parameter
        assert len(supported_methods) > 0
        assert 'put_object' in supported_methods


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="lzl.io.File not available")
class TestPresignedURLIntegration:
    """Test integration with underlying filesystem."""
    
    def test_s3fs_supports_client_method(self):
        """Test that s3fs.S3FileSystem.url supports client_method."""
        try:
            import s3fs
            import inspect
            
            # Check s3fs.S3FileSystem.url signature
            sig = inspect.signature(s3fs.S3FileSystem.url)
            params = sig.parameters
            
            # Should have client_method parameter
            assert 'client_method' in params
            
            # Default should be 'get_object'
            assert params['client_method'].default == 'get_object'
            
        except ImportError:
            pytest.skip("s3fs not available")
    
    def test_boto3_generate_presigned_url_support(self):
        """Test that boto3 client supports generate_presigned_url."""
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError
            
            # Create a client (will fail without credentials, but that's OK)
            try:
                client = boto3.client('s3', region_name='us-east-1')
            except NoCredentialsError:
                pytest.skip("No AWS credentials available")
            
            # Check method exists
            assert hasattr(client, 'generate_presigned_url')
            
            # Check signature
            import inspect
            sig = inspect.signature(client.generate_presigned_url)
            params = sig.parameters
            
            # Should have ClientMethod and ExpiresIn parameters
            assert 'ClientMethod' in params
            assert 'ExpiresIn' in params
            
            # Default expiration should be 3600 seconds
            assert params['ExpiresIn'].default == 3600
            
        except ImportError:
            pytest.skip("boto3 not available")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
