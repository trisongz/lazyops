"""Compatibility aliases for typing features across Python versions."""

import sys

if sys.version_info >= (3, 8):
    from typing import Final, Literal
else:  # pragma: no cover - legacy Python support
    from typing_extensions import Final, Literal

__all__ = ['Final', 'Literal']
