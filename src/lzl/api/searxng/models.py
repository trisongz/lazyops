from __future__ import annotations

import typing as t
from lzo.types import BaseModel, Field, eproperty

class ResultItem(BaseModel):
    """
    The Single Search Result Item
    """
    url: str = Field(..., description="The URL of the search result")
    title: str = Field(..., description="The title of the search result")
    query: str = Field(..., description="The query used to obtain this search result")
    content: t.Optional[str] = Field(None, description="The content snippet of the search result")

