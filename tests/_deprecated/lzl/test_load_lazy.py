import types

from lzl.load import (
    LazyLoad,
    import_from_string,
    import_function,
    lazy_function_wrapper,
    lazy_import,
    load,
)


def test_lazy_load_defers_until_attribute_access(monkeypatch):
    lazy_math = LazyLoad("math", install_missing=False)
    assert lazy_math.__module__ is None

    sqrt = lazy_math.sqrt
    import math

    assert lazy_math.__module__ is math
    assert sqrt is math.sqrt
    assert load(lazy_math) is math


def test_lazy_import_caches_objects():
    first = lazy_import("math.sqrt")
    second = lazy_import("math.sqrt")
    assert first is second


def test_import_from_string_returns_attribute():
    pi = import_from_string("math:pi")
    import math

    assert pi == math.pi


def test_import_function_accepts_string_path():
    resolved = import_function("math.sqrt")
    import math

    assert resolved is math.sqrt
    assert import_function("math.sqrt") is resolved  # cached via lru_cache


def test_lazy_function_wrapper_initialises_once():
    calls: list[str] = []

    def initializer(multiplier: int):
        calls.append("init")

        def binder(func):
            def wrapped(*args, **kwargs):
                return multiplier * func(*args, **kwargs)

            return wrapped

        return binder

    @lazy_function_wrapper(initializer, 2)
    def target(value: int) -> int:
        return value

    assert target(3) == 6
    assert target(5) == 10
    assert calls == ["init"]
