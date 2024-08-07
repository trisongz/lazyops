from __future__ import annotations

"""
FastAPI Responses
"""

import yaml
from fastapi.responses import (
    JSONResponse as BaseJSONResponse,
    Response,
)
from .utils import serializer
from typing import Any, Optional


class JSONResponse(BaseJSONResponse):

    indention: Optional[int] = None

    def render(self, content: Any) -> bytes:
        return serializer.dumps(
            content,
            ensure_ascii = False,
            allow_nan = False,
            indent = self.indention,
            separators=(",", ":"),
        ).encode("utf-8")


class PrettyJSONResponse(JSONResponse):
    indention = 4


class YAMLResponse(Response):

    content_type: str = "application/yaml"
    indention: int = 2

    def render(self, content: Any) -> bytes:
        return yaml.safe_dump(
            content,
            default_flow_style = False,
            indent = self.indention,
        ).encode("utf-8")