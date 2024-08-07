"""
Persistence Module that supports both
local and remote persistence

The PersistentDict offers a dict-like interface with some powerful features:
- Mutability: Changes to the dict are automatically persisted
- Serialization: Values are automatically serialized and deserialized
  - Supports JSON, Pickle, MsgPack, and Custom Serializers
- Compression: Values are automatically compressed and decompressed
    - Supports Zlib Compression
- Remote Persistence: Supports Redis as a remote persistence backend
- Local Persistence: Supports Local Filesystem as a local persistence backend
- Supports async operations


Usage:

    from lazyops.libs.persistence import PersistentDict

    # Create a new PersistentDict
    # with default settings

    cache = PersistentDict("my_cache")

    # Set a key
    cache["foo"] = "bar"
    cache["x"] = 1

    # Get a key
    print(cache["foo"])
    print(cache["x"])

    # Mutate a key
    cache["x"] += 1
    print(cache["x"])

    # Delete a key
    del cache["foo"]
    print(cache["foo"])

    # Check if a key exists
    print("foo" in cache)

    # Get all keys
    print(cache.keys())

    # Get all values
    print(cache.values())

    # Get all items
    print(cache.items())

    # Get the length of the cache
    print(len(cache))

    # Clear the cache
    cache.clear()
 
"""


from .main import PersistentDict
from .backends import (
    LocalStatefulBackend, 
    RedisStatefulBackend, 
    StatefulBackendT,
)
from .serializers import (
    JsonSerializer, PickleSerializer, MsgPackSerializer, BaseSerializer,
    SerializerT, get_serializer
)