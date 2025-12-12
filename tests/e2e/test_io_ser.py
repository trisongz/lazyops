import pytest
from lzl.io.ser import get_serializer

def test_json_serializer():
    """
    Test JSON serialization.
    """
    ser = get_serializer('json')
    data = {"a": 1, "b": "test"}
    encoded = ser.dumps(data)
    assert isinstance(encoded, (str, bytes))
    decoded = ser.loads(encoded)
    assert decoded == data

def test_pickle_serializer():
    """
    Test Pickle serialization.
    """
    ser = get_serializer('pickle')
    data = {"a": set([1, 2])}
    encoded = ser.dumps(data)
    decoded = ser.loads(encoded)
    assert decoded == data


def test_msgpack_serializer():
    """
    Test MsgPack serialization if available.
    """
    try:
        ser = get_serializer('msgpack')
        data = {"a": 1}
        encoded = ser.dumps(data)
        decoded = ser.loads(encoded)
        assert decoded == data
    except (ImportError, ValueError):
        pytest.skip("msgpack not available")
