
import asyncio
import pytest
from lzl.io.persistence import PersistentDict

# Mock or use local backend for testing
def test_persistent_dict_nested_changes():
    """
    Verify that nested changes are tracked and saved correctly in both sync and async contexts.
    """
    async def _run_test():
        # Initialize PersistentDict with local backend (default)
        # Using a unique name to avoid collisions
        pdict = PersistentDict(name="test_persistence", backend_type="local", async_enabled=True)
        try:
            pdict.clear()

            # 1. Sync setdefault with nested list
            key = "nested_sync"
            pdict.setdefault(key, {"items": []})
            
            # Modify nested object
            with pdict.track_changes(key, 'get') as data:
                data["items"].append("item1")
            
            # Verify change is persisted in memory/tracker
            assert "item1" in pdict.get(key)["items"]
            
            # Force flush/save (though track_changes should have handled it if hash changed)
            # We re-fetch to see if it stuck
            assert "item1" in pdict.get(key)["items"]

            # 2. Async asetdefault with nested list
            key_async = "nested_async"
            await pdict.asetdefault(key_async, {"items": []})
            
            # Modify nested object async
            async with pdict.atrack_changes(key_async, 'aget') as data:
                data["items"].append("item2")
            
            # Verify change is persisted
            val = await pdict.aget(key_async)
            assert "item2" in val["items"]
            
            # 3. Test multiple modifications
            async with pdict.atrack_changes(key_async, 'aget') as data:
                data["items"].append("item3")
                
            val = await pdict.aget(key_async)
            assert "item2" in val["items"]
            assert "item3" in val["items"]
        finally:
            # Clean up
            await pdict.aclear()
    
    asyncio.run(_run_test())

if __name__ == "__main__":
    asyncio.run(test_persistent_dict_nested_changes())
