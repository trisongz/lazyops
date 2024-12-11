from __future__ import annotations

import typing as t
from ._pydantic import pydantic_data_converter
from ._pydantic_json import pydantic_data_converter as pydantic_json_data_converter
from ._serialized import serialized_data_converter, get_serialized_data_converter

if t.TYPE_CHECKING:
    from temporalio.converter import DataConverter


def get_default_data_converter(
    converter: t.Optional[str] = None,
    jsonlib: t.Optional[str] = None,
    compression: t.Optional[str] = None,
    compression_level: t.Optional[int] = None,
    **kwargs
) -> 'DataConverter':
    """
    Returns the default data converter
    """
    if converter == "serialized":
        return get_serialized_data_converter(jsonlib = jsonlib, compression = compression, compression_level = compression_level, **kwargs)
    if converter == "pydantic":
        return pydantic_data_converter
    if converter == "pydantic_json":
        return pydantic_json_data_converter
    from temporalio.converter import DataConverter
    return DataConverter.default
    # raise ValueError(f"Invalid converter: {converter}")