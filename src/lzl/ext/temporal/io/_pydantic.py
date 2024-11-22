from __future__ import annotations


import typing as t
import functools
from temporalio.api.common.v1 import Payload
from temporalio.converter import (
    CompositePayloadConverter,
    DataConverter,
    DefaultPayloadConverter,
    JSONPlainPayloadConverter,
)
from .utils import get_json_meta, _json


class PydanticJSONPayloadConverter(JSONPlainPayloadConverter):
    """Pydantic JSON payload converter.

    This extends the :py:class:`JSONPlainPayloadConverter` to override
    :py:meth:`to_payload` using the Pydantic encoder.
    """

    def to_payload(self, value: t.Any) -> t.Optional[Payload]:
        """Convert all values with Pydantic encoder or fail.

        Like the base class, we fail if we cannot convert. This payload
        converter is expected to be the last in the chain, so it can fail if
        unable to convert.
        """
        # We let JSON conversion errors be thrown to caller
        return Payload(
            metadata = get_json_meta(self.encoding, "serialized"),
            data = _json.dumps(
                value, 
                separators = (",", ":"), 
                sort_keys = True, 
            ),
        )
    
    def from_payload(self, payload: Payload, type_hint: t.Optional[t.Type] = None) -> t.Any:
        """
        Converts the payload to the type hint
        """
        return _json.loads(payload.data)


class PydanticPayloadConverter(CompositePayloadConverter):
    """Payload converter that replaces Temporal JSON conversion with Pydantic
    JSON conversion.
    """

    def __init__(self) -> None:
        super().__init__(
            *(
                PydanticJSONPayloadConverter() if isinstance(c, JSONPlainPayloadConverter) else c
                for c in DefaultPayloadConverter.default_encoding_payload_converters
            )
        )



pydantic_data_converter = DataConverter(
    payload_converter_class = PydanticPayloadConverter
)
"""Data converter using Pydantic JSON conversion."""