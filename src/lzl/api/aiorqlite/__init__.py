from __future__ import annotations

"""
RQLite API Client based on `rqdb` and uses `aioreq` for the underlying requests

Usage:

```python
>>> from lzl.api import aiorqlite
>>> conn = aiorqlite.connect('http://localhost:4001')
>>> conn.execute('SELECT 1')
<ResultItem object at 0x7f9c0d0c1d10>

```

"""

from .connection import Connection
from .logging import LogConfig

connect = Connection