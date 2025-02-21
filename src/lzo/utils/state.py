from __future__ import annotations

"""
Global State Objects that can be used to share state across modules
"""

import pathlib
import typing as t
from lzl.proxied import ProxyObject

if t.TYPE_CHECKING:
    from lzl.io import TemporaryData

lib_path = pathlib.Path(__file__).parent

_temporary_data: t.Optional['TemporaryData'] = None

# This temp data will be at lzl/.data

def get_temp_data() -> 'TemporaryData':
    """
    Gets the temporary data object
    """
    global _temporary_data
    if _temporary_data is None:
        from lzl.io.persistence import TemporaryData
        _temporary_data = TemporaryData(lib_path.joinpath('.tmpdata'))
    return _temporary_data


TempData: 'TemporaryData' = ProxyObject(
    obj_getter = get_temp_data
)

