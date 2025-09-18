# `lzo.registry`

The registry helpers expose a lightweight mechanism for tracking lazily
constructed objects across the LazyOps ecosystem.  Each registry stores three
maps: declared callables/classes (`mregistry`), dotted import paths destined for
lazy loading (`uninit_registry`), and hydrated instances (`init_registry`).

```python
from lzo.registry.base import MRegistry

registry = MRegistry('example')
registry['example.client'] = SomeClient
registry.register_prehook('example.client', lambda payload=None: {'payload': payload or 'default'})

client = registry.get('example.client')
```

Higher-level helpers such as `lzo.registry.clients.register_client` build on top
of `MRegistry` to add standardised metadata for clients, objects, and settings.
These wrappers keep the public API deterministic so documentation generators
can surface consistent entry points.
