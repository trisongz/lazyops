import pickle
from typing import Any, Dict, Optional, Union, Type
from lazyops.utils.lazy import lazy_import
from .base import BinaryBaseSerializer, ObjectValue, SchemaType, BaseModel, logger

try:
    import cloudpickle
    _cloudpicke_available = True
except ImportError:
    _cloudpicke_available = False

try:
    import dill
    _dill_available = True
except ImportError:
    _dill_available = False

if _cloudpicke_available:
    default_pickle = cloudpickle
elif _dill_available:
    default_pickle = dill
else:
    default_pickle = pickle

class PickleSerializer(BinaryBaseSerializer):
    name: Optional[str] = "pickle"
    encoding: Optional[str] = "utf-8"
    picklelib: Any = default_pickle

    def __init__(
        self, 
        picklelib: Optional[Union[str, Any]] = None,
        compression: Optional[str] = None,
        compression_level: int | None = None, 
        encoding: str | None = None, 
        **kwargs
    ):
        super().__init__(compression, compression_level, encoding, **kwargs)
        if picklelib is not None:
            if isinstance(picklelib, str):
                picklelib = lazy_import(picklelib)
            assert hasattr(picklelib, "dumps") and hasattr(picklelib, "loads"), f"Invalid Pickle Library: {picklelib}"
            self.picklelib = picklelib
        self.picklelib_name = self.picklelib.__name__
    
    def encode_value(self, value: Union[Any, SchemaType], **kwargs) -> bytes:
        """
        Encode the value with the Pickle Library
        """
        try:
            return self.picklelib.dumps(value, **kwargs)
        except Exception as e:
            logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {value}', colored = True, prefix = self.picklelib_name)
            if self.raise_errors: raise e
        return None

    def decode_value(self, value: bytes, **kwargs) -> Union[SchemaType, Dict, Any]:
        """
        Decode the value with the Pickle Library
        """
        try:
            if self.picklelib_name == 'cloudpickle':
                if 'encoding' not in kwargs:
                    kwargs['encoding'] = self.encoding
                if 'fix_imports' not in kwargs:
                    kwargs['fix_imports'] = False
            return self.picklelib.loads(value, **kwargs)
        except Exception as e:
            logger.info(f'Error Decoding Value: |r|({type(value)}) {e}|e| {value}', colored = True, prefix = self.picklelib_name)
            if self.raise_errors: raise e
        return None