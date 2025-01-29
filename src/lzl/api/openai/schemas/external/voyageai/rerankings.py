from __future__ import annotations

"""
voyage.ai Reranking Route
"""

from ...rerankings import (
    RerankingRoute as BaseRerankingRoute,
    RerankingObject as BaseRerankingObject,
    RerankingResponse as BaseRerankingResponse,
    logger
)
from lzo.types import (
    validator, 
    model_validator,
    Field,
    eproperty
)
from lzl.api.openai.types.handlers import ModelContextHandler
from lzl.api.openai.types.base import Usage
from typing import Any, Dict, List, Optional, Union, Set, Type, TYPE_CHECKING

class RerankingObject(BaseRerankingObject):
    
    model: Optional[str] = "voyage-rerank-2-lite"
    return_documents: Optional[bool] = Field(False, description = 'If false, the API will return a list of {"index", "relevance_score"} where "index" refers to the index of a document within the input list., If true, the API will return a list of {"index", "document", "relevance_score"} where "document" is the corresponding document from the input list.') 
    truncation: Optional[bool] = Field(True, description = 'Whether to truncate the input text to the maximum context length')

class RerankingResponse(BaseRerankingResponse):

    usage: Optional[Usage] = Field(default_factory = Usage)

    @eproperty
    def consumption(self) -> int:
        """
        Returns the consumption for the reranking
        """
        try:
            return ModelContextHandler.get_consumption_cost(
                model_name = self.input_object.model,
                usage = self.usage,
            )
        except Exception as e:
            logger.error(f"Error getting consumption: {e}")
            return 0


class RerankingRoute(BaseRerankingRoute):
    input_model: Optional[Type[RerankingObject]] = RerankingObject
    response_model: Optional[Type[RerankingResponse]] = RerankingResponse

    @eproperty
    def create_enabled(self):
        """
        Returns whether the Create Route is Enabled
        """
        return True
