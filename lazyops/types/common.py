"""
Base Types from Typing
"""

__all__ = (
    'PathLike',
    'TYPE_CHECKING',
    'List', 'Dict', 'AnyStr', 'Any', 'Set',
    'Optional', 'Union', 'Tuple', 'Mapping', 'Sequence', 'TypeVar', 'Type',
    'Callable', 'Coroutine', 'Generator', 'AsyncGenerator', 'IO', 'Iterable', 'Iterator', 'AsyncIterator',
    'cast', 'overload',
    'Final', 'Literal',
    'Data', 'AnyMany', 'TextMany', 'TextList',
    'DictList', 'DictMany', 'DictAny', 'DictAny',
    'aobject',
    'StrEnum',
    'UpperStrEnum',
)

import sys

from os import PathLike
from typing import TYPE_CHECKING
from typing import List, Dict, AnyStr, Any, Set
from typing import Optional, Union, Tuple, Mapping, Sequence, TypeVar, Type
from typing import Callable, Coroutine, Generator, AsyncGenerator, IO, Iterable, Iterator, AsyncIterator
from typing import cast, overload


if sys.version_info >= (3, 8):
    from typing import Final, Literal
else:
    from typing_extensions import Final, Literal

Data = TypeVar('Data', str, List[str], Dict[str, Union[str, List[str]]])
AnyMany = TypeVar('AnyMany', Any, List[Any])

TextMany = TypeVar('TextMany', str, List[str])
TextList = List[str]

DictList = List[Dict[str, Any]]
DictMany = TypeVar('DictMany', Dict[str, Any], List[Dict[str, Any]])
DictAny = Dict[str, Any]
DictText = Dict[str, str]
NoneType = type(None)



class aobject(object):
    """Inheriting this class allows you to define an async __init__.

    So you can create objects by doing something like `await MyClass(params)`
    """
    async def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        await instance.__init__(*args, **kwargs)
        return instance

    async def __init__(self, *args, **kwargs):
        pass

# borrowed from 
# https://github.com/pydantic/pydantic/issues/1439
def construct_union(modules: List):  
    # modules is a list of class constructors and has to be accessible in the current global scope
    eval_string = ', '.join([f'{i.__module__}.{i.__name__}' for i in modules])
    return eval(f'Union[{eval_string}]')

# def construct_union(modules: List):
#     return Union[tuple(modules)]

from enum import Enum, EnumMeta
from functools import singledispatchmethod

class StrEnumMeta(EnumMeta):

    @singledispatchmethod
    def __getitem__(self, key):
        return super().__getitem__(key)

    @__getitem__.register
    def _(self, index: int):
        return list(self)[index]

class StrEnum(str, Enum, metaclass=StrEnumMeta):
    """
    StrEnum is a string enum that allows for case-insensitive comparisons
    """

    def __eq__(self, other: Any) -> bool:
        return self.value.lower() == other.lower() if \
            isinstance(other, str) else \
                super().__eq__(other)
    
    def __ne__(self, other: Any) -> bool:
        return self.value.lower() != other.lower() if \
            isinstance(other, str) else \
                super().__ne__(other)

    def __str__(self) -> str:
        return str.__str__(self)
    
    def __hash__(self) -> int:
        return id(self)


class UpperStrEnum(StrEnum):
    """
    UpperStrEnum is a string enum that allows for case-insensitive comparisons
    """

    def __eq__(self, other: Any) -> bool:
        return self.value.upper() == other.upper() if \
            isinstance(other, str) else \
                super().__eq__(other)
    
    def __ne__(self, other: Any) -> bool:
        return self.value.upper() != other.upper() if \
            isinstance(other, str) else \
                super().__ne__(other)
    

    def __str__(self) -> str:
        return str.__str__(self)
    
    def __hash__(self) -> int:
        return id(self)



if TYPE_CHECKING:
    ListStr = List[str]

else:

    class ListStr(list):
        """
        Returns List[str] by splitting on delimiter ','
        """

        @classmethod
        def __get_validators__(cls):
            yield cls.validate

        @classmethod
        def validate(cls, value: Optional[Any]) -> Optional[List[str]]:
            """
            Validates the value and returns a List[str]
            """
            if v is None: return None
            from lazyops.utils.serialization import parse_list_str
            return parse_list_str(value)



        
