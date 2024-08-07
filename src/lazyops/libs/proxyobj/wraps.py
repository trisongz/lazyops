from __future__ import annotations

"""
This module contains a wrapper function that allows you to wrap an object class to create a proxy object.


@proxied
class DummyClass(abc.ABC):

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        print('DummyClass initialized')

    def hi(self, *args, **kwargs):
        print('DummyClass called')
        return 'hi'
        

# Testing a proxy object wrapper with arguments
x = DummyClass
>> DummyClass initialized

print(x.hi())
>> DummyClass called
>> hi
"""

from typing import Type, TypeVar, Optional, Union, Any, Callable, List, Dict, overload, TYPE_CHECKING
from .main import ProxyObject

ObjT = TypeVar('ObjT')
ProxyObjT = Type[ObjT]


@overload
def proxied(
    obj_cls: Optional[ProxyObjT] = None,
    obj_getter: Optional[Union[Callable, str]] = None,
    obj_args: Optional[List[Any]] = None,
    obj_kwargs: Optional[Dict[str, Any]] = None,
    obj_initialize: Optional[bool] = True,
    threadsafe: Optional[bool] = True,
) -> Union[ObjT, ProxyObjT]: 
    """
    Lazily initialize an object as a proxy object

    Args:
    - obj_cls: The object class
    - obj_getter: The object getter. This can be a callable or a string which will lazily import the object
    - obj_args: The object arguments. This can be a list or a callable that returns a list, or a string that lazily imports a function/list
    - obj_kwargs: The object keyword arguments. This can be a dictionary or a callable that returns a dictionary, or a string that lazily imports a function/dictionary
    - obj_initialize: The object initialization flag
    - threadsafe: The thread safety flag

    Returns:
    - Type[OT]: The proxy object

    Usage:
    @proxied
    class DummyClass(abc.ABC):

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            print('DummyClass initialized')
    
    x = DummyClass
    >> DummyClass initialized

    # Note that if you initialize the object directly, it will raise an error
    y = DummyClass() # Raises an error

    def dummy_args_getter() -> Iterable:
        return [1, 2]

    # @proxied(obj_args=(1, 2), obj_kwargs={'a': 1, 'b': 2})
    @proxied(obj_args=dummy_args_getter, obj_kwargs={'a': 1, 'b': 2})
    class DummyClass(abc.ABC):

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            print('DummyClass initialized', args, kwargs)
    
    x = DummyClass
    >> DummyClass initialized (1, 2) {'a': 1, 'b': 2}
    """
    ...


@overload
def proxied(
    **kwargs: Any,
) -> Callable[..., Union[ObjT, ProxyObjT]]:
    """
    Lazily initialize an object as a proxy object

    Args:
    - obj_cls: The object class
    - obj_getter: The object getter. This can be a callable or a string which will lazily import the object
    - obj_args: The object arguments. This can be a list or a callable that returns a list, or a string that lazily imports a function/list
    - obj_kwargs: The object keyword arguments. This can be a dictionary or a callable that returns a dictionary, or a string that lazily imports a function/dictionary
    - obj_initialize: The object initialization flag
    - threadsafe: The thread safety flag

    Returns:
    - Type[OT]: The proxy object

    Usage:
    @proxied
    class DummyClass(abc.ABC):

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            print('DummyClass initialized')
    
    x = DummyClass
    >> DummyClass initialized

    # Note that if you initialize the object directly, it will raise an error
    y = DummyClass() # Raises an error

    def dummy_args_getter() -> Iterable:
        return [1, 2]

    # @proxied(obj_args=(1, 2), obj_kwargs={'a': 1, 'b': 2})
    @proxied(obj_args=dummy_args_getter, obj_kwargs={'a': 1, 'b': 2})
    class DummyClass(abc.ABC):

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            print('DummyClass initialized', args, kwargs)
    
    x = DummyClass
    >> DummyClass initialized (1, 2) {'a': 1, 'b': 2}
    """
    def wrapper(obj_cls: ProxyObjT) -> Union[ObjT, ProxyObjT]:
        ...
    return wrapper



def proxied(
    obj_cls: Optional[ProxyObjT] = None,
    obj_getter: Optional[Union[Callable, str]] = None,
    obj_args: Optional[List[Any]] = None,
    obj_kwargs: Optional[Dict[str, Any]] = None,
    obj_initialize: Optional[bool] = True,
    threadsafe: Optional[bool] = True,
) -> Union[Callable[..., Union[ObjT, ProxyObjT]], Union[ObjT, ProxyObjT]]:
    """
    Lazily initialize an object as a proxy object

    Args:
    - obj_cls: The object class
    - obj_getter: The object getter. This can be a callable or a string which will lazily import the object
    - obj_args: The object arguments. This can be a list or a callable that returns a list, or a string that lazily imports a function/list
    - obj_kwargs: The object keyword arguments. This can be a dictionary or a callable that returns a dictionary, or a string that lazily imports a function/dictionary
    - obj_initialize: The object initialization flag
    - threadsafe: The thread safety flag

    Returns:
    - Type[OT]: The proxy object

    Usage:
    @proxied
    class DummyClass(abc.ABC):

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            print('DummyClass initialized')
    
    x = DummyClass
    >> DummyClass initialized

    # Note that if you initialize the object directly, it will raise an error
    y = DummyClass() # Raises an error

    def dummy_args_getter() -> Iterable:
        return [1, 2]

    # @proxied(obj_args=(1, 2), obj_kwargs={'a': 1, 'b': 2})
    @proxied(obj_args=dummy_args_getter, obj_kwargs={'a': 1, 'b': 2})
    class DummyClass(abc.ABC):

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            print('DummyClass initialized', args, kwargs)
    
    x = DummyClass
    >> DummyClass initialized (1, 2) {'a': 1, 'b': 2}
    """

    if obj_cls is not None:
        return ProxyObject(
            obj_cls = obj_cls,
            obj_getter = obj_getter,
            obj_args = obj_args,
            obj_kwargs = obj_kwargs,
            obj_initialize = obj_initialize,
            threadsafe = threadsafe,
        )
    
    def wrapper(obj_cls: ProxyObjT) -> Union[ObjT, ProxyObjT]:
        return ProxyObject(
            obj_cls = obj_cls,
            obj_getter = obj_getter,
            obj_args = obj_args,
            obj_kwargs = obj_kwargs,
            obj_initialize = obj_initialize,
            threadsafe = threadsafe,
        )
    
    return wrapper
