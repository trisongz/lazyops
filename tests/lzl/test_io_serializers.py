from lzl.io.ser import JsonSerializer, PickleSerializer, get_serializer


def test_get_serializer_returns_json_by_default() -> None:
    serializer = get_serializer()
    assert isinstance(serializer, JsonSerializer)


def test_get_serializer_caches_instances() -> None:
    first = get_serializer("json")
    second = get_serializer("json")
    assert first is second


def test_get_serializer_pickle_roundtrip() -> None:
    serializer = get_serializer("pickle")
    assert isinstance(serializer, PickleSerializer)
