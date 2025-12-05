# lzl.io.ser - Serialization

High-performance serialization utilities supporting JSON, Pickle, MsgPack, and compression.

## Main Interface

::: lzl.io.ser.base

## Formatters

::: lzl.io.ser._json
::: lzl.io.ser._pickle
::: lzl.io.ser._msgpack

## Usage

```python
from lzl.io.ser import serialize, deserialize

data = {"complex": "object"}

# Auto-detect format based on context or configuration
s = serialize(data, format="json")
d = deserialize(s, format="json")
```
