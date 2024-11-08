"""
Miscellaneous Types
"""


import typing as t
from lzl.types import PYDANTIC_VERSION
from pydantic.types import ByteSize
try:
    import dill as pickle
except ImportError:
    import pickle

class ObjectSize(ByteSize):
    """
    Returns the size of an object
    """

    @classmethod
    def _dump_(cls, obj: t.Any) -> float:
        """
        Returns the size of the object
        """
        return len(obj) if isinstance(obj, (bytes, bytearray)) else len(pickle.dumps(obj))

    if PYDANTIC_VERSION == 2:
        from pydantic_core import core_schema

        @classmethod
        def _validate(cls, input_value: t.Any, /, _: core_schema.ValidationInfo) -> 'ObjectSize':
            """
            Validator for Pydantic v2
            """
            if not isinstance(input_value, (int, float)):
                input_value = cls._dump_(input_value)
            return super()._validate(input_value, _)

    else:
        @classmethod
        def __get_validators__(cls):
            yield cls.validate
        
        @classmethod
        def validate(cls, input_value: t.Any) -> 'ObjectSize':
            """
            Validator for Pydantic v1
            """
            if not isinstance(input_value, (int, float)):
                input_value = cls._dump_(input_value)
            return super()._validate(input_value)

    def __new__(cls, obj: t.Any):
        """
        Returns the size of the object
        """
        if not isinstance(obj, (int, float)):
            obj = cls._dump_(obj)
        return super().__new__(cls, obj)