from lzl.io.file.spec.paths.cached import FileCachedPath
from lzl.io import File

def test_cached_joinpath():
    # Mocking behavior without actual filesystem access if possible, 
    # or using a dummy protocol string that we can inspect.
    
    # We use 'simplecache::s3://bucket/key'
    # This triggers FileCachedPath
    
    try:
        p = File("simplecache::s3://mybucket/mykey")
        print(f"Parent protocol: {getattr(p, '_protocol', 'N/A')}")
        print(f"Parent accessor: {p._accessor}")
        
        child = p / "child"
        print(f"Child path: {child}")
        print(f"Child class: {type(child)}")
        print(f"Child protocol: {getattr(child, '_protocol', 'N/A')}")
        
        # Check if accessor matches (or is present)
        print(f"Child accessor: {getattr(child, '_accessor', 'N/A')}")
        
        assert child._protocol == p._protocol
        assert "simplecache::s3" in str(child) or "simplecache::s3" == getattr(child, '_protocol', '')
        
        print("SUCCESS: Protocol preserved.")
    except Exception as e:
        print(f"FAILURE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_cached_joinpath()