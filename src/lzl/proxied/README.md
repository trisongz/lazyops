# `lzl.proxied`

The `lzl.proxied` package provides lightweight wrappers for deferring object
construction.  Use these helpers when creating expensive instances (clients,
API adapters, etc.) that should only be initialised once the application
actually needs them.

## Core Building Blocks
- **`ProxyObject`** – Generic proxy that instantiates the target class on first
  use while guarding access with optional locking.
- **`proxied` decorator** – Sugar for wrapping classes/functions with
  `ProxyObject` without changing call sites.
- **`ProxyDict`** – Mutable mapping that lazily imports or instantiates values
  when accessed.
- **Singleton helpers** – `Singleton` and `LockedSingleton` implement simple
  process-wide singletons, the latter using a re-entrant lock.

## Example
```python
from lzl.proxied import proxied

@proxied
class HeavyClient:
    def __init__(self) -> None:
        print("initialising…")

client = HeavyClient  # No construction yet
print(client())       # Triggers initialisation on first call
```

## Testing Notes
- Use dedicated proxy subclasses in tests to avoid clashing with global
  `ProxyDict` caches.
- Reset class-level maps (`_dict`, `_initialized`) when asserting lazy-loading
  behaviour across multiple tests.
