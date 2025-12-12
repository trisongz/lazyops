"""
Testing the Proxied Object Module
"""

import abc
from lzl.proxied import proxied
from lzl.proxied.types import ProxyDict
from typing import Dict, Union, TYPE_CHECKING

class DummyType(abc.ABC):

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        print('DummyType initialized')

    def hi(self, *args, **kwargs):
        print('DummyType called', args, kwargs)
        return 'hi'


@proxied
class DummyClass(abc.ABC):

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        print('DummyClass initialized')

    def hi(self, *args, **kwargs):
        print('DummyClass called', args, kwargs)
        return 'hi'

print(DummyClass.hi())

def test_dummy(x: DummyClass):
    print(x.hi())

test_dummy(DummyClass)


class DummyDict(ProxyDict[str, Union[DummyClass, DummyType]]):

    _dict: Dict[str, DummyClass] = {
        'x': DummyClass,
        'y': DummyType,
    }

    if TYPE_CHECKING:
        @property
        def x(self) -> DummyClass:
            ...
    @property
    def y(self) -> DummyType:
        return self.get_or_init('y')
        

d = DummyDict()

print(d.x.hi('helloooo'))
print(d.y.hi('helloooo'))
print(d.y.hi('helloooo'))
print(d.x.hi('helloooo'))
