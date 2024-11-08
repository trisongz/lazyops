from __future__ import annotations

import os
import inspect


def iscoroutinefunction(obj):
    if inspect.iscoroutinefunction(obj): return True
    return bool(hasattr(obj, '__call__') and inspect.iscoroutinefunction(obj.__call__))


# def encode_string_to_bytes(s: str, )

# def decode(s, encodings=('ascii', 'utf8', 'latin1')):
#     for encoding in encodings:
#         try:
#             return s.decode(encoding)
#         except UnicodeDecodeError:
#             pass
#     return s.decode('ascii', 'ignore')