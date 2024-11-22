from __future__ import annotations

"""
Registry of SQL Functions that can be lazily loaded
"""

import abc
import typing as t
from lzo.registry.base import MRegistry


class SQLFunction(abc.ABC):
    """
    Abstract Base Class for SQL Functions
    """

    _rxtra: t.Dict[str, t.Any] = {}

    def __init_subclass__(cls) -> None:

        return super().__init_subclass__()
    

SQLFunctionT = t.TypeVar('SQLFunctionT', bound = SQLFunction)

class SQLFunctionRegistry(MRegistry[SQLFunctionT]):
    """
    Registry of SQL Functions
    """

    # def re
    
