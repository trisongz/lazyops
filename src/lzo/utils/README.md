# `lzo.utils`

Utility helpers are grouped here so higher-level packages can compose functionality
without pulling in large dependency chains.  The submodules exposed through
`lzo.utils.__all__` include logging shims, dictionary/formatting helpers, and
cryptographic key generators.

```python
from lzo.utils.helpers.base import retryable
from lzo.utils.keygen import Generate

@retryable(limit=3, delay=0)
def fetch_config():
    ...

api_key = Generate.alphanumeric_passcode(length=24)
```

Each helper module aims to provide pure-Python, dependency-light utilities so
Mintlify can surface concise documentation with working examples.
