import threading

from lzl.proxied import LockedSingleton, ProxyObject, proxied
from lzl.proxied.base import empty
from lzl.proxied.types import ProxyDict


def test_proxyobject_lazily_initialises() -> None:
    calls = []

    class Widget:
        def __init__(self) -> None:
            calls.append("init")
            self.value = 42

        def read(self) -> int:
            return self.value

    proxy = ProxyObject(obj_cls=Widget)
    assert proxy._wrapped is empty
    assert proxy.read() == 42
    assert isinstance(proxy._wrapped, Widget)
    assert calls == ["init"]


def test_proxied_decorator_returns_proxy() -> None:
    @proxied
    class Service:
        def __init__(self) -> None:
            self.ready = True

    service_proxy = Service
    assert service_proxy.ready is True


def test_proxydict_lazy_initialisation() -> None:
    class LocalProxyDict(ProxyDict[str, object]):
        pass

    store = LocalProxyDict()
    LocalProxyDict._dict["pi"] = "math.pi"
    LocalProxyDict._initialized.pop("pi", None)

    value = store.pi
    import math

    assert value == math.pi
    assert LocalProxyDict._initialized.get("pi") is True


def test_locked_singleton_returns_same_instance_across_threads() -> None:
    results: list[int] = []

    class ExampleSingleton(LockedSingleton):
        counter = 0

    def worker() -> None:
        instance = ExampleSingleton()
        results.append(id(instance))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len({*results}) == 1
