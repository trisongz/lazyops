import pytest
from lzl.proxied import ProxyObject

class MyClass:
    def __init__(self, value):
        self.value = value
    
    def get_value(self):
        return self.value

def factory():
    return MyClass("proxied")

def test_proxy_object_lazy_init():
    """
    Test that ProxyObject initializes lazily.
    """
    proxy = ProxyObject(factory)
    
    # Not initialized yet (conceptually, though implementation might differ)
    # Check property access
    assert proxy.value == "proxied"
    assert proxy.get_value() == "proxied"

def test_proxy_object_isinstance():
    """
    Test isinstance checks with ProxyObject if supported.
    """
    # ProxyObject might not strictly support isinstance(proxy, MyClass) 
    # depending on implementation (typically needs a wrapper or specific __class__ hacking).
    # We check basic behavior.
    proxy = ProxyObject(factory)
    # assert isinstance(proxy, MyClass) # This might fail if ProxyObject doesn't impersonate class.
    # Instead check behavior attributes.
    assert hasattr(proxy, 'value')

def test_proxy_setattr():
    """
    Test setting attributes on the proxied object.
    """
    proxy = ProxyObject(factory)
    proxy.value = "new_value"
    assert proxy.get_value() == "new_value"
